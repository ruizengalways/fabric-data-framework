"""Production-reference FULL -> REPLACE dataset execution semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from uuid import UUID, uuid4

from ..apply.replace import (
    InMemoryReplaceTarget,
    ReplaceGuardError,
    ReplaceGuardPolicy,
    plan_replace,
)
from ..bronze import BronzeRecord, normalize_bronze
from ..capture.full import (
    FullSnapshotEvidence,
    FullSnapshotEvidenceError,
    capture_full_snapshot,
)
from ..config import ApplyStrategy, CaptureStrategy, DatasetStatus, RunMode
from ..data_plane.staging import StagedBatch, stage_rows
from ..operations import (
    DatasetRunAudit,
    MutationCounts,
    QuarantineBatch,
    QuarantineScope,
    ReconciliationResult,
    ReconciliationStatus,
    RowAccounting,
    StepRunAudit,
    StepStatus,
)
from ..quality import QuarantinedRecord, RowRule, reconcile_full_replace, validate_records
from ..control_plane.repository import ControlPlaneRepository


@dataclass(frozen=True)
class FullReplaceExecutionResult:
    dataset_run_id: UUID
    pipeline_run_id: UUID
    status: DatasetStatus
    bronze: tuple[BronzeRecord, ...]
    quarantined: tuple[QuarantinedRecord, ...]
    staged: StagedBatch | None
    reconciliation: ReconciliationResult | None
    target_rows: tuple[dict[str, Any], ...]
    error_code: str | None = None
    error_message: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _record_step(
    repository: ControlPlaneRepository,
    *,
    dataset_run_id: UUID,
    step_name: str,
    status: StepStatus,
) -> None:
    now = _utcnow()
    repository.record_step_run(
        StepRunAudit(
            dataset_run_id=dataset_run_id,
            step_name=step_name,
            status=status,
            started_at=now,
            completed_at=now,
        )
    )


def _record_failure(
    repository: ControlPlaneRepository,
    *,
    dataset_run_id: UUID,
    pipeline_run_id: UUID,
    dataset_id: str,
    run_mode: RunMode,
    effective_config_hash: str,
    error_code: str,
    error_message: str,
    accounting: RowAccounting | None = None,
) -> None:
    repository.record_dataset_run(
        DatasetRunAudit(
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=dataset_id,
            attempt=1,
            run_mode=run_mode,
            status=DatasetStatus.FAILED,
            effective_config_hash=effective_config_hash,
            row_accounting=accounting,
            mutations=MutationCounts(),
            error_code=error_code,
            error_message=error_message,
            retryable=False,
        )
    )


def execute_full_replace(
    *,
    repository: ControlPlaneRepository,
    target: InMemoryReplaceTarget,
    dataset_id: str,
    source_rows: Sequence[Mapping[str, Any]],
    snapshot_evidence: FullSnapshotEvidence,
    rules: tuple[RowRule, ...] = (),
    mapper: Callable[[dict[str, Any]], dict[str, Any]] = dict,
    guard_policy: ReplaceGuardPolicy | None = None,
    pipeline_run_id: UUID | None = None,
    dataset_run_id: UUID | None = None,
    run_mode: RunMode = RunMode.NORMAL,
    effective_config_hash: str | None = None,
    force_reconciliation_failure: bool = False,
) -> FullReplaceExecutionResult:
    """Execute a guarded FULL -> REPLACE without mutating target before gates pass."""

    config = repository.get_dataset(dataset_id)
    if config.load.capture_strategy is not CaptureStrategy.FULL:
        raise ValueError("FULL -> REPLACE executor requires FULL capture")
    if config.load.apply_strategy is not ApplyStrategy.REPLACE:
        raise ValueError("FULL -> REPLACE executor requires REPLACE apply")

    pipeline_run_id = pipeline_run_id or uuid4()
    dataset_run_id = dataset_run_id or uuid4()
    config_hash = effective_config_hash or config.config_hash
    guard_policy = guard_policy or ReplaceGuardPolicy()

    try:
        capture = capture_full_snapshot(source_rows, evidence=snapshot_evidence)
    except FullSnapshotEvidenceError as exc:
        _record_step(
            repository,
            dataset_run_id=dataset_run_id,
            step_name="CAPTURE_FULL",
            status=StepStatus.FAILED,
        )
        _record_failure(
            repository,
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=dataset_id,
            run_mode=run_mode,
            effective_config_hash=config_hash,
            error_code="FULL_SNAPSHOT_EVIDENCE_INVALID",
            error_message=str(exc),
        )
        return FullReplaceExecutionResult(
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            status=DatasetStatus.FAILED,
            bronze=(),
            quarantined=(),
            staged=None,
            reconciliation=None,
            target_rows=target.read(),
            error_code="FULL_SNAPSHOT_EVIDENCE_INVALID",
            error_message=str(exc),
        )

    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="CAPTURE_FULL",
        status=StepStatus.SUCCEEDED,
    )

    bronze = normalize_bronze(
        capture.rows,
        pipeline_run_id=pipeline_run_id,
        dataset_run_id=dataset_run_id,
        source_system=config.source.system,
        source_object=config.source.object,
        event_time_column=config.load.event_time_column,
    )
    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="BRONZE_NORMALIZE",
        status=StepStatus.SUCCEEDED,
    )

    validation = validate_records(bronze, rules)
    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="VALIDATE",
        status=StepStatus.SUCCEEDED,
    )

    for item in validation.quarantined:
        repository.record_quarantine(
            QuarantineBatch(
                dataset_run_id=dataset_run_id,
                dataset_id=dataset_id,
                scope=QuarantineScope.ROW,
                row_count=1,
                reason_code="|".join(item.reason_codes),
                reason_detail=" | ".join(item.reason_messages),
                source_reference=snapshot_evidence.snapshot_id,
            )
        )
    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="QUARANTINE",
        status=StepStatus.SUCCEEDED,
    )

    mapped = tuple(mapper(dict(record.data)) for record in validation.accepted)
    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="TRANSFORM",
        status=StepStatus.SUCCEEDED,
    )

    staged = stage_rows(mapped, dataset_run_id=dataset_run_id)
    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="STAGE",
        status=StepStatus.SUCCEEDED,
    )

    accounting = RowAccounting(
        rows_read=len(bronze),
        rows_accepted=len(validation.accepted),
        rows_quarantined=len(validation.quarantined),
        rows_filtered=0,
    )

    try:
        replace_plan = plan_replace(
            target.read(),
            staged,
            evidence=snapshot_evidence,
            policy=guard_policy,
        )
    except ReplaceGuardError as exc:
        _record_step(
            repository,
            dataset_run_id=dataset_run_id,
            step_name="PUBLICATION_GUARD",
            status=StepStatus.FAILED,
        )
        _record_failure(
            repository,
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=dataset_id,
            run_mode=run_mode,
            effective_config_hash=config_hash,
            error_code="FULL_REPLACE_GUARD_FAILED",
            error_message=str(exc),
            accounting=accounting,
        )
        return FullReplaceExecutionResult(
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            status=DatasetStatus.FAILED,
            bronze=bronze,
            quarantined=validation.quarantined,
            staged=staged,
            reconciliation=None,
            target_rows=target.read(),
            error_code="FULL_REPLACE_GUARD_FAILED",
            error_message=str(exc),
        )

    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="PUBLICATION_GUARD",
        status=StepStatus.SUCCEEDED,
    )

    reconciliation = reconcile_full_replace(
        dataset_run_id=dataset_run_id,
        dataset_id=dataset_id,
        policy_name=config.reconciliation.policy_name,
        accounting=accounting,
        candidate_row_count=replace_plan.candidate_count,
        evidence=snapshot_evidence,
        force_fail=force_reconciliation_failure,
    )
    repository.record_reconciliation(reconciliation)
    passed = reconciliation.status is ReconciliationStatus.PASS
    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="RECONCILE",
        status=StepStatus.SUCCEEDED if passed else StepStatus.FAILED,
    )

    if not passed:
        _record_failure(
            repository,
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=dataset_id,
            run_mode=run_mode,
            effective_config_hash=config_hash,
            error_code="RECONCILIATION_FAILED",
            error_message="required FULL -> REPLACE reconciliation gate failed",
            accounting=accounting,
        )
        _record_step(
            repository,
            dataset_run_id=dataset_run_id,
            step_name="PUBLISH",
            status=StepStatus.SKIPPED,
        )
        return FullReplaceExecutionResult(
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            status=DatasetStatus.FAILED,
            bronze=bronze,
            quarantined=validation.quarantined,
            staged=staged,
            reconciliation=reconciliation,
            target_rows=target.read(),
            error_code="RECONCILIATION_FAILED",
            error_message="required FULL -> REPLACE reconciliation gate failed",
        )

    target.publish(replace_plan.rows)
    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="PUBLISH",
        status=StepStatus.SUCCEEDED,
    )

    repository.record_dataset_run(
        DatasetRunAudit(
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=dataset_id,
            attempt=1,
            run_mode=run_mode,
            status=DatasetStatus.SUCCEEDED,
            effective_config_hash=config_hash,
            row_accounting=accounting,
            mutations=replace_plan.mutations,
        )
    )

    return FullReplaceExecutionResult(
        dataset_run_id=dataset_run_id,
        pipeline_run_id=pipeline_run_id,
        status=DatasetStatus.SUCCEEDED,
        bronze=bronze,
        quarantined=validation.quarantined,
        staged=staged,
        reconciliation=reconciliation,
        target_rows=target.read(),
    )
