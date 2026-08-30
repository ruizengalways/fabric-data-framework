"""Production-reference SNAPSHOT -> SNAPSHOT_DIFF execution semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from uuid import UUID, uuid4

from ..apply.replace import InMemoryReplaceTarget
from ..apply.snapshot_diff import (
    SnapshotDiffError,
    SnapshotDiffPlan,
    SnapshotDiffPolicy,
    plan_snapshot_diff,
)
from fabric_data_framework.data_plane.bronze import BronzeRecord, normalize_bronze
from ..capture.snapshot import SnapshotEvidence, SnapshotEvidenceError, capture_snapshot
from ..config import ApplyStrategy, CaptureStrategy, DatasetStatus, RunMode
from ..data_plane.staging import StagedBatch, stage_rows
from fabric_data_framework.contracts.audit import (
    DatasetRunAudit,
    MutationCounts,
    RowAccounting,
    StepRunAudit,
    StepStatus,
)
from fabric_data_framework.contracts.quarantine import (
    QuarantineBatch,
    QuarantineScope,
)
from fabric_data_framework.contracts.reconciliation import (
    ReconciliationResult,
    ReconciliationStatus,
)
from ..quality import QuarantinedRecord, RowRule, validate_records
from ..quality.snapshot_diff import reconcile_snapshot_diff
from ..control_plane.repository import ControlPlaneRepository


@dataclass(frozen=True)
class SnapshotDiffExecutionResult:
    dataset_run_id: UUID
    pipeline_run_id: UUID
    status: DatasetStatus
    bronze: tuple[BronzeRecord, ...]
    quarantined: tuple[QuarantinedRecord, ...]
    staged: StagedBatch | None
    diff: SnapshotDiffPlan | None
    reconciliation: ReconciliationResult | None
    target_rows: tuple[dict[str, Any], ...]
    error_code: str | None = None
    error_message: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _record_step(
    repository: ControlPlaneRepository,
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


def execute_snapshot_diff(
    *,
    repository: ControlPlaneRepository,
    target: InMemoryReplaceTarget,
    dataset_id: str,
    source_rows: Sequence[Mapping[str, Any]],
    snapshot_evidence: SnapshotEvidence,
    rules: tuple[RowRule, ...] = (),
    mapper: Callable[[dict[str, Any]], dict[str, Any]] = dict,
    diff_policy: SnapshotDiffPolicy | None = None,
    pipeline_run_id: UUID | None = None,
    dataset_run_id: UUID | None = None,
    run_mode: RunMode = RunMode.NORMAL,
    effective_config_hash: str | None = None,
    force_reconciliation_failure: bool = False,
) -> SnapshotDiffExecutionResult:
    config = repository.get_dataset(dataset_id)
    if config.load.capture_strategy is not CaptureStrategy.SNAPSHOT:
        raise ValueError("SNAPSHOT_DIFF executor requires SNAPSHOT capture")
    if config.load.apply_strategy is not ApplyStrategy.SNAPSHOT_DIFF:
        raise ValueError("SNAPSHOT_DIFF executor requires SNAPSHOT_DIFF apply")

    pipeline_run_id = pipeline_run_id or uuid4()
    dataset_run_id = dataset_run_id or uuid4()
    config_hash = effective_config_hash or config.config_hash
    diff_policy = diff_policy or SnapshotDiffPolicy()

    try:
        capture = capture_snapshot(source_rows, evidence=snapshot_evidence)
    except SnapshotEvidenceError as exc:
        _record_step(repository, dataset_run_id, "CAPTURE_SNAPSHOT", StepStatus.FAILED)
        _record_failure(
            repository,
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=dataset_id,
            run_mode=run_mode,
            effective_config_hash=config_hash,
            error_code="SNAPSHOT_EVIDENCE_INVALID",
            error_message=str(exc),
        )
        return SnapshotDiffExecutionResult(
            dataset_run_id,
            pipeline_run_id,
            DatasetStatus.FAILED,
            (),
            (),
            None,
            None,
            None,
            target.read(),
            "SNAPSHOT_EVIDENCE_INVALID",
            str(exc),
        )

    _record_step(repository, dataset_run_id, "CAPTURE_SNAPSHOT", StepStatus.SUCCEEDED)
    bronze = normalize_bronze(
        capture.rows,
        pipeline_run_id=pipeline_run_id,
        dataset_run_id=dataset_run_id,
        source_system=config.source.system,
        source_object=config.source.object,
        event_time_column=config.load.event_time_column,
    )
    validation = validate_records(bronze, rules)
    _record_step(repository, dataset_run_id, "VALIDATE", StepStatus.SUCCEEDED)

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

    mapped = tuple(mapper(dict(record.data)) for record in validation.accepted)
    staged = stage_rows(mapped, dataset_run_id=dataset_run_id)
    accounting = RowAccounting(
        rows_read=len(bronze),
        rows_accepted=len(validation.accepted),
        rows_quarantined=len(validation.quarantined),
        rows_filtered=0,
    )

    try:
        diff = plan_snapshot_diff(
            target.read(),
            staged.rows,
            evidence=snapshot_evidence,
            merge_key=config.load.merge_key,
            tracked_columns=config.load.tracked_columns,
            quarantined_count=len(validation.quarantined),
            policy=diff_policy,
        )
    except SnapshotDiffError as exc:
        _record_step(repository, dataset_run_id, "SNAPSHOT_DIFF_GUARD", StepStatus.FAILED)
        _record_failure(
            repository,
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=dataset_id,
            run_mode=run_mode,
            effective_config_hash=config_hash,
            error_code="SNAPSHOT_DIFF_GUARD_FAILED",
            error_message=str(exc),
            accounting=accounting,
        )
        return SnapshotDiffExecutionResult(
            dataset_run_id,
            pipeline_run_id,
            DatasetStatus.FAILED,
            bronze,
            validation.quarantined,
            staged,
            None,
            None,
            target.read(),
            "SNAPSHOT_DIFF_GUARD_FAILED",
            str(exc),
        )

    _record_step(repository, dataset_run_id, "SNAPSHOT_DIFF_GUARD", StepStatus.SUCCEEDED)
    reconciliation = reconcile_snapshot_diff(
        dataset_run_id=dataset_run_id,
        dataset_id=dataset_id,
        policy_name=config.reconciliation.policy_name,
        accounting=accounting,
        candidate_row_count=len(staged.rows),
        target_after_count=len(diff.rows),
        force_fail=force_reconciliation_failure,
    )
    repository.record_reconciliation(reconciliation)
    passed = reconciliation.status is ReconciliationStatus.PASS
    _record_step(
        repository,
        dataset_run_id,
        "RECONCILE",
        StepStatus.SUCCEEDED if passed else StepStatus.FAILED,
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
            error_message="required SNAPSHOT_DIFF reconciliation gate failed",
            accounting=accounting,
        )
        return SnapshotDiffExecutionResult(
            dataset_run_id,
            pipeline_run_id,
            DatasetStatus.FAILED,
            bronze,
            validation.quarantined,
            staged,
            diff,
            reconciliation,
            target.read(),
            "RECONCILIATION_FAILED",
            "required SNAPSHOT_DIFF reconciliation gate failed",
        )

    target.publish(diff.rows)
    _record_step(repository, dataset_run_id, "PUBLISH", StepStatus.SUCCEEDED)
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
            mutations=diff.mutations,
        )
    )
    return SnapshotDiffExecutionResult(
        dataset_run_id,
        pipeline_run_id,
        DatasetStatus.SUCCEEDED,
        bronze,
        validation.quarantined,
        staged,
        diff,
        reconciliation,
        target.read(),
    )
