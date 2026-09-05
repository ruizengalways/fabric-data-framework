"""Reference WATERMARK -> Bronze -> DQ -> SCD2 dataset runner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from uuid import UUID, uuid4

from fabric_data_framework.data_plane.bronze import BronzeRecord, normalize_bronze
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DatasetStatus,
    QuarantineDetailMode,
    RunMode,
)
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
from ..quality.rules import QuarantinedRecord, RowRule, ValidationOutcome, validate_records
from ..quality.quarantine_store import QuarantinePayloadWriter
from fabric_data_framework.quality.reconciliation import reconcile_scd2_batch
from ..control_plane.repository import ControlPlaneRepository
from fabric_data_framework.contracts.runtime import StateCommitGate, WatermarkPosition, WatermarkTransition
from fabric_data_framework.apply.scd2 import InMemorySCD2Target, SCD2ApplyResult, apply_scd2
from fabric_data_framework.capture.watermark import WatermarkBatch, plan_watermark_batch


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
    details: dict[str, object] | None = None,
) -> None:
    now = _utcnow()
    repository.record_step_run(
        StepRunAudit(
            dataset_run_id=dataset_run_id,
            step_name=step_name,
            status=status,
            started_at=now,
            completed_at=now,
            details=details,
        )
    )


def _reason_summary(rows: tuple[QuarantinedRecord, ...]) -> tuple[str, str]:
    codes = sorted({code for item in rows for code in item.reason_codes})
    messages = sorted({message for item in rows for message in item.reason_messages})
    return "|".join(codes), " | ".join(messages)


def _record_row_quarantine(
    repository: ControlPlaneRepository,
    *,
    dataset_run_id: UUID,
    dataset_id: str,
    quarantined: tuple[QuarantinedRecord, ...],
    detail_mode: QuarantineDetailMode,
    quarantine_store: QuarantinePayloadWriter | None,
) -> None:
    if not quarantined:
        return

    if detail_mode is QuarantineDetailMode.FULL:
        if quarantine_store is None:
            raise RuntimeError(
                "FULL row quarantine requires a governed QuarantinePayloadWriter"
            )
        quarantine_id = uuid4()
        source_reference = quarantine_store.write_payload(
            quarantine_id=quarantine_id,
            dataset_run_id=dataset_run_id,
            dataset_id=dataset_id,
            rows=quarantined,
        )
        reason_code, reason_detail = _reason_summary(quarantined)
        repository.record_quarantine(
            QuarantineBatch(
                quarantine_id=quarantine_id,
                dataset_run_id=dataset_run_id,
                dataset_id=dataset_id,
                scope=QuarantineScope.ROW,
                row_count=len(quarantined),
                reason_code=reason_code,
                reason_detail=reason_detail,
                source_reference=source_reference,
            )
        )
        return

    # Backward-compatible reference-only mode. It deliberately does not claim durable
    # full-row detail; each row retains the best source sequence reference available.
    for item in quarantined:
        repository.record_quarantine(
            QuarantineBatch(
                dataset_run_id=dataset_run_id,
                dataset_id=dataset_id,
                scope=QuarantineScope.ROW,
                row_count=1,
                reason_code="|".join(item.reason_codes),
                reason_detail=" | ".join(item.reason_messages),
                source_reference=(
                    str(item.record.source_sequence)
                    if item.record.source_sequence is not None
                    else None
                ),
            )
        )


def _quarantine_threshold_breaches(config, *, invalid_rows: int, total_rows: int) -> tuple[str, ...]:
    if invalid_rows == 0 or not config.quality.quarantine_enabled:
        return ()
    breaches: list[str] = []
    if (
        config.quality.max_quarantine_rows is not None
        and invalid_rows > config.quality.max_quarantine_rows
    ):
        breaches.append(
            f"rows={invalid_rows}>{config.quality.max_quarantine_rows}"
        )
    fraction = invalid_rows / total_rows if total_rows else 0.0
    if (
        config.quality.max_quarantine_fraction is not None
        and fraction > config.quality.max_quarantine_fraction
    ):
        breaches.append(
            "fraction="
            f"{fraction:.6f}>{config.quality.max_quarantine_fraction:.6f}"
        )
    return tuple(breaches)


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
    quarantine_store: QuarantinePayloadWriter | None = None,
    force_reconciliation_failure: bool = False,
) -> DatasetExecutionResult:
    """Execute the first reference strategy combination atomically in memory.

    Proposed SCD2 target rows are calculated before reconciliation, but target and
    watermark commits occur only after the required gates pass. Data-quality behavior
    comes from ``config.quality``:

    - DQ disabled: validation rules are skipped and all captured rows continue.
    - DQ enabled + quarantine enabled: bad rows are isolated; valid rows continue.
      FULL detail requires a governed data-plane payload writer and Control Plane keeps
      only summary/reference evidence.
    - DQ enabled + quarantine disabled: any invalid row fails this dataset and blocks
      target/state commit, while the parent dispatcher can still run sibling datasets.
    - Quarantine thresholds: invalid rows are still durably quarantined, but exceeding
      the configured absolute or fractional budget fails the dataset before state commit.
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

    if config.quality.enabled:
        validation = validate_records(bronze, rules)
        invalid_fraction = len(validation.quarantined) / len(bronze) if bronze else 0.0
        _record_step(
            repository,
            dataset_run_id=dataset_run_id,
            step_name="VALIDATE",
            status=StepStatus.SUCCEEDED,
            details={
                "rows_accepted": len(validation.accepted),
                "rows_invalid": len(validation.quarantined),
                "invalid_fraction": invalid_fraction,
            },
        )
    else:
        validation = ValidationOutcome(accepted=bronze, quarantined=())
        _record_step(
            repository,
            dataset_run_id=dataset_run_id,
            step_name="VALIDATE",
            status=StepStatus.SKIPPED,
            details={"reason": "data_quality_disabled"},
        )

    threshold_breaches = _quarantine_threshold_breaches(
        config,
        invalid_rows=len(validation.quarantined),
        total_rows=len(bronze),
    )
    hard_dq_failure = bool(validation.quarantined) and (
        not config.quality.quarantine_enabled or bool(threshold_breaches)
    )

    if validation.quarantined and config.quality.quarantine_enabled:
        _record_row_quarantine(
            repository,
            dataset_run_id=dataset_run_id,
            dataset_id=dataset_id,
            quarantined=validation.quarantined,
            detail_mode=config.quality.quarantine_detail_mode,
            quarantine_store=quarantine_store,
        )
        _record_step(
            repository,
            dataset_run_id=dataset_run_id,
            step_name="QUARANTINE",
            status=StepStatus.SUCCEEDED,
            details={
                "rows_quarantined": len(validation.quarantined),
                "detail_mode": config.quality.quarantine_detail_mode.value,
                "threshold_breached": bool(threshold_breaches),
                "threshold_breaches": list(threshold_breaches),
            },
        )
    elif hard_dq_failure:
        _record_step(
            repository,
            dataset_run_id=dataset_run_id,
            step_name="QUARANTINE",
            status=StepStatus.SKIPPED,
            details={
                "reason": "quarantine_disabled",
                "rows_invalid": len(validation.quarantined),
            },
        )
    else:
        _record_step(
            repository,
            dataset_run_id=dataset_run_id,
            step_name="QUARANTINE",
            status=StepStatus.SKIPPED,
            details={"reason": "no_invalid_rows_or_dq_disabled"},
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

    reconciliation_passed = reconciliation.status is ReconciliationStatus.PASS
    passed = reconciliation_passed and not hard_dq_failure
    gate = StateCommitGate(
        target_committed=passed,
        reconciliation_required=config.reconciliation.required_for_state_commit,
        reconciliation_passed=reconciliation_passed,
        batch_quarantined=hard_dq_failure,
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
            details={"reason": "dataset_gate_failed"},
        )

    if validation.quarantined and not config.quality.quarantine_enabled:
        error_code = "DATA_QUALITY_FAILED_QUARANTINE_DISABLED"
        reason_code, reason_detail = _reason_summary(validation.quarantined)
        error_message = (
            f"{len(validation.quarantined)} row(s) failed data quality while quarantine "
            f"was disabled; rules={reason_code}; detail={reason_detail}"
        )
    elif threshold_breaches:
        error_code = "DATA_QUALITY_QUARANTINE_THRESHOLD_EXCEEDED"
        error_message = (
            f"{len(validation.quarantined)} quarantined row(s) exceeded configured DQ budget: "
            + ", ".join(threshold_breaches)
        )
    elif not reconciliation_passed:
        error_code = "RECONCILIATION_FAILED"
        error_message = "required reconciliation gate failed"
    else:
        error_code = None
        error_message = None

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
            error_code=error_code,
            error_message=error_message,
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
