"""Reference WATERMARK -> Bronze -> DQ -> SCD2 dataset runner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from uuid import UUID, uuid4

from ..bronze import BronzeRecord, normalize_bronze
from ..config import ApplyStrategy, CaptureStrategy, DatasetStatus, RunMode
from fabric_data_framework.contracts.audit import (
    DatasetRunAudit,
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
from ..reconciliation import reconcile_scd2_batch
from ..control_plane.repository import ControlPlaneRepository
from ..runtime import StateCommitGate, WatermarkPosition, WatermarkTransition
from ..scd2 import InMemorySCD2Target, SCD2ApplyResult, apply_scd2
from ..watermark import WatermarkBatch, plan_watermark_batch


@dataclass(frozen=True)
class DatasetExecutionResult:
    dataset_run_id: UUID
    pipeline_run_id: UUID
    status: DatasetStatus
    bronze: tuple[BronzeRecord, ...]
    quarantined: tuple[QuarantinedRecord, ...]
    reconciliation: ReconciliationResult
    watermark_before: WatermarkPosition | None
    watermark_after: WatermarkPosition | None
    target_rows: tuple[dict[str, Any], ...]


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


def execute_watermark_scd2(
    *,
    repository: ControlPlaneRepository,
    target: InMemorySCD2Target,
    dataset_id: str,
    source_rows: Sequence[Mapping[str, Any]],
    rules: tuple[RowRule, ...],
    mapper: Callable[[dict[str, Any]], dict[str, Any]],
    pipeline_run_id: UUID | None = None,
    dataset_run_id: UUID | None = None,
    run_mode: RunMode = RunMode.NORMAL,
    effective_config_hash: str | None = None,
    force_reconciliation_failure: bool = False,
) -> DatasetExecutionResult:
    """Execute the first reference strategy combination atomically in memory.

    Proposed SCD2 target rows are calculated before reconciliation, but target and
    watermark commits occur only after the required reconciliation passes. Row-level
    quarantine is treated as handled input and can advance state; batch quarantine is
    a different state that blocks commit.
    """

    config = repository.get_dataset(dataset_id)
    if config.load.capture_strategy is not CaptureStrategy.WATERMARK:
        raise ValueError("reference executor requires WATERMARK capture")
    if config.load.apply_strategy is not ApplyStrategy.SCD2:
        raise ValueError("reference executor requires SCD2 apply")
    if config.load.watermark is None:
        raise ValueError("WATERMARK configuration missing")
    if not config.load.event_time_column:
        raise ValueError("SCD2 reference executor requires event_time_column")

    pipeline_run_id = pipeline_run_id or uuid4()
    dataset_run_id = dataset_run_id or uuid4()
    config_hash = effective_config_hash or config.config_hash
    before = repository.get_watermark(dataset_id)

    capture: WatermarkBatch = plan_watermark_batch(source_rows, config.load.watermark, before)
    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="CAPTURE",
        status=StepStatus.SUCCEEDED,
    )

    bronze = normalize_bronze(
        capture.rows,
        pipeline_run_id=pipeline_run_id,
        dataset_run_id=dataset_run_id,
        source_system=config.source.system,
        source_object=config.source.object,
        event_time_column=config.load.event_time_column,
        source_sequence_columns=config.load.watermark.tie_breaker,
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
                source_reference=str(item.record.source_sequence),
            )
        )
    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="QUARANTINE",
        status=StepStatus.SUCCEEDED,
    )

    mapped = tuple(mapper(record.data) for record in validation.accepted)
    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="TRANSFORM",
        status=StepStatus.SUCCEEDED,
    )

    proposed: SCD2ApplyResult = apply_scd2(
        target.read(),
        mapped,
        business_key=config.load.business_key,
        tracked_columns=config.load.tracked_columns,
        effective_time_column=config.load.event_time_column,
        dataset_run_id=dataset_run_id,
    )
    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="APPLY_PLAN",
        status=StepStatus.SUCCEEDED,
    )

    accounting = RowAccounting(
        rows_read=len(bronze),
        rows_accepted=len(validation.accepted),
        rows_quarantined=len(validation.quarantined),
        rows_filtered=0,
    )
    reconciliation = reconcile_scd2_batch(
        dataset_run_id=dataset_run_id,
        dataset_id=dataset_id,
        policy_name=config.reconciliation.policy_name,
        accounting=accounting,
        proposed_rows=proposed.rows,
        business_key=config.load.business_key,
        force_fail=force_reconciliation_failure,
    )
    repository.record_reconciliation(reconciliation)
    _record_step(
        repository,
        dataset_run_id=dataset_run_id,
        step_name="RECONCILE",
        status=(
            StepStatus.SUCCEEDED
            if reconciliation.status is ReconciliationStatus.PASS
            else StepStatus.FAILED
        ),
    )

    passed = reconciliation.status is ReconciliationStatus.PASS
    gate = StateCommitGate(
        target_committed=passed,
        reconciliation_required=config.reconciliation.required_for_state_commit,
        reconciliation_passed=passed,
        batch_quarantined=False,
    )

    status: DatasetStatus
    if passed:
        target.replace(proposed.rows)
        if capture.after is not None:
            WatermarkTransition(before=before, after=capture.after, gate=gate)
            repository.commit_watermark(dataset_id, capture.after)
        status = DatasetStatus.SUCCEEDED
        _record_step(
            repository,
            dataset_run_id=dataset_run_id,
            step_name="COMMIT_STATE",
            status=StepStatus.SUCCEEDED,
        )
    else:
        status = DatasetStatus.FAILED
        _record_step(
            repository,
            dataset_run_id=dataset_run_id,
            step_name="COMMIT_STATE",
            status=StepStatus.SKIPPED,
        )

    repository.record_dataset_run(
        DatasetRunAudit(
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=dataset_id,
            attempt=1,
            run_mode=run_mode,
            status=status,
            effective_config_hash=config_hash,
            row_accounting=accounting,
            mutations=(
                proposed.mutations
                if passed
                else proposed.mutations.model_copy(
                    update={"inserted": 0, "updated": 0, "deleted": 0}
                )
            ),
            error_code=None if passed else "RECONCILIATION_FAILED",
            error_message=None if passed else "required reconciliation gate failed",
            retryable=False if not passed else None,
        )
    )

    return DatasetExecutionResult(
        dataset_run_id=dataset_run_id,
        pipeline_run_id=pipeline_run_id,
        status=status,
        bronze=bronze,
        quarantined=validation.quarantined,
        reconciliation=reconciliation,
        watermark_before=before,
        watermark_after=repository.get_watermark(dataset_id),
        target_rows=target.read(),
    )
