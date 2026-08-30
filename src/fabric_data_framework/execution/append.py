"""Capture-neutral production-reference APPEND batch execution semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from uuid import UUID, uuid4

from ..apply.append import (
    AppendApplyError,
    AppendApplyResult,
    InMemoryAppendTarget,
    apply_append,
)
from fabric_data_framework.data_plane.bronze import BronzeRecord, normalize_bronze
from fabric_data_framework.metadata.config import ApplyStrategy, DatasetStatus, RunMode
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
from ..quality import QuarantinedRecord, RowRule, reconcile_append, validate_records
from ..control_plane.repository import ControlPlaneRepository


@dataclass(frozen=True)
class AppendExecutionResult:
    dataset_run_id: UUID
    pipeline_run_id: UUID
    status: DatasetStatus
    bronze: tuple[BronzeRecord, ...]
    quarantined: tuple[QuarantinedRecord, ...]
    staged: StagedBatch | None
    append_result: AppendApplyResult | None
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


def execute_append_batch(
    *,
    repository: ControlPlaneRepository,
    target: InMemoryAppendTarget,
    dataset_id: str,
    source_rows: Sequence[Mapping[str, Any]],
    source_reference: str | None = None,
    rules: tuple[RowRule, ...] = (),
    mapper: Callable[[dict[str, Any]], dict[str, Any]] = dict,
    pipeline_run_id: UUID | None = None,
    dataset_run_id: UUID | None = None,
    run_mode: RunMode = RunMode.NORMAL,
    effective_config_hash: str | None = None,
    force_reconciliation_failure: bool = False,
) -> AppendExecutionResult:
    """Validate/map/stage/reconcile one already-captured APPEND batch before publication.

    Capture and source-progress ownership intentionally remain outside this executor.
    A WATERMARK/CDC/native capture coordinator can therefore feed the same APPEND
    semantic path while retaining its own source-range/checkpoint protocol.
    """

    config = repository.get_dataset(dataset_id)
    if config.load.apply_strategy is not ApplyStrategy.APPEND:
        raise ValueError("APPEND executor requires APPEND apply strategy")

    pipeline_run_id = pipeline_run_id or uuid4()
    dataset_run_id = dataset_run_id or uuid4()
    config_hash = effective_config_hash or config.config_hash

    bronze = normalize_bronze(
        tuple(dict(row) for row in source_rows),
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
                source_reference=source_reference,
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
        append_result = apply_append(
            target.read(),
            staged.rows,
            append_identity=config.load.append_identity,
        )
    except AppendApplyError as exc:
        _record_step(
            repository,
            dataset_run_id=dataset_run_id,
            step_name="APPEND_GUARD",
            status=StepStatus.FAILED,
        )
        _record_failure(
            repository,
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=dataset_id,
            run_mode=run_mode,
            effective_config_hash=config_hash,
            error_code="APPEND_IDENTITY_CONFLICT",
            error_message=str(exc),
            accounting=accounting,
        )
        return AppendExecutionResult(
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            status=DatasetStatus.FAILED,
            bronze=bronze,
            quarantined=validation.quarantined,
            staged=staged,
            append_result=None,
            reconciliation=None,
            target_rows=target.read(),
            error_code="APPEND_IDENTITY_CONFLICT",
            error_message=str(exc),
        )

    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="APPEND_GUARD",
        status=StepStatus.SUCCEEDED,
    )

    reconciliation = reconcile_append(
        dataset_run_id=dataset_run_id,
        dataset_id=dataset_id,
        policy_name=config.reconciliation.policy_name,
        accounting=accounting,
        inserted=append_result.inserted,
        replayed=append_result.replayed,
        duplicate_incoming=append_result.duplicate_incoming,
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
            error_message="required APPEND reconciliation gate failed",
            accounting=accounting,
        )
        _record_step(
            repository,
            dataset_run_id=dataset_run_id,
            step_name="PUBLISH",
            status=StepStatus.SKIPPED,
        )
        return AppendExecutionResult(
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            status=DatasetStatus.FAILED,
            bronze=bronze,
            quarantined=validation.quarantined,
            staged=staged,
            append_result=append_result,
            reconciliation=reconciliation,
            target_rows=target.read(),
            error_code="RECONCILIATION_FAILED",
            error_message="required APPEND reconciliation gate failed",
        )

    target.replace(append_result.rows)
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
            mutations=MutationCounts(inserted=append_result.inserted),
        )
    )

    return AppendExecutionResult(
        dataset_run_id=dataset_run_id,
        pipeline_run_id=pipeline_run_id,
        status=DatasetStatus.SUCCEEDED,
        bronze=bronze,
        quarantined=validation.quarantined,
        staged=staged,
        append_result=append_result,
        reconciliation=reconciliation,
        target_rows=target.read(),
    )


__all__ = ["AppendExecutionResult", "execute_append_batch"]
