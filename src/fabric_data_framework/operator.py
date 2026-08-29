"""Read-only operator views over the relational control-plane contract.

This module deliberately exposes typed operational snapshots rather than raw SQLAlchemy
rows.  It is provider-neutral and safe for CLI/API use; it does not mutate runtime
state or pretend the reference SQL store is the final production technology.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field
from sqlalchemy import Engine, func, select

from .config import FrozenModel, RunMode
from .contracts.recovery import ReprocessRequestStatus
from .control_plane import (
    apply_baseline_schema,
    capture_receipt,
    cdc_checkpoint,
    dataset,
    dataset_attempt_lineage,
    dataset_run,
    quarantine_batch,
    reconciliation_result,
    reprocess_request,
    schema_change,
    watermark,
)


class DatasetRunView(FrozenModel):
    dataset_run_id: UUID
    pipeline_run_id: UUID
    attempt: int = Field(ge=1)
    status: str
    effective_config_hash: str
    run_mode: RunMode | None = None
    root_dataset_run_id: UUID | None = None
    previous_dataset_run_id: UUID | None = None
    reprocess_request_id: UUID | None = None
    rows_read: int | None = None
    rows_accepted: int | None = None
    rows_quarantined: int | None = None
    rows_filtered: int | None = None
    rows_inserted: int | None = None
    rows_updated: int | None = None
    rows_deleted: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool | None = None
    started_at: datetime
    completed_at: datetime | None = None


class CaptureCorrelationView(FrozenModel):
    capture_receipt_id: UUID
    dataset_run_id: UUID
    capture_strategy: str
    execution_engine: str
    progress_owner: str
    native_run_id: str | None = None
    landing_reference: str
    source_reference: str | None = None
    external_checkpoint_reference: str | None = None
    source_lower_bound: Any | None = None
    source_upper_bound: Any | None = None
    snapshot_id: str | None = None
    complete_snapshot: bool | None = None
    rows_read: int = Field(ge=0)
    rows_written: int = Field(ge=0)
    completed_at: datetime


class WatermarkProgressView(FrozenModel):
    committed_value: Any | None = None
    committed_tie_breaker: Any | None = None
    committed_dataset_run_id: UUID | None = None
    version: int = Field(ge=0)


class CDCProgressView(FrozenModel):
    positions: Any
    committed_dataset_run_id: UUID
    version: int = Field(ge=1)


class ReconciliationView(FrozenModel):
    reconciliation_id: UUID
    dataset_run_id: UUID
    policy_name: str
    status: str
    metrics: dict[str, Any]
    blocks_state_advance: bool
    created_at: datetime


class SchemaChangeView(FrozenModel):
    schema_change_id: UUID
    dataset_run_id: UUID | None = None
    observed_fingerprint: str
    expected_fingerprint: str | None = None
    classification: str
    details: dict[str, Any] | None = None
    observed_at: datetime


class ReprocessRequestView(FrozenModel):
    reprocess_request_id: UUID
    run_mode: RunMode
    status: ReprocessRequestStatus
    reason: str
    requested_by: str
    original_pipeline_run_id: UUID | None = None
    original_dataset_run_id: UUID | None = None
    range_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class QuarantineBacklogView(FrozenModel):
    open_batches: int = Field(ge=0)
    open_rows: int = Field(ge=0)


class DatasetOperationalSnapshot(FrozenModel):
    dataset_id: str
    latest_run: DatasetRunView | None = None
    latest_capture: CaptureCorrelationView | None = None
    watermark: WatermarkProgressView | None = None
    cdc_checkpoint: CDCProgressView | None = None
    latest_reconciliation: ReconciliationView | None = None
    quarantine_backlog: QuarantineBacklogView
    latest_schema_change: SchemaChangeView | None = None
    active_reprocess_requests: tuple[ReprocessRequestView, ...] = ()


def _uuid(value: object | None) -> UUID | None:
    return UUID(str(value)) if value is not None else None


def _latest(connection, table, predicate, order_columns):
    return connection.execute(
        select(table).where(predicate).order_by(*order_columns).limit(1)
    ).mappings().first()


def get_dataset_operational_snapshot(
    engine: Engine,
    dataset_id: str,
    *,
    reprocess_limit: int = 20,
) -> DatasetOperationalSnapshot:
    """Return one coherent read-only on-call view for a deployed dataset."""

    if reprocess_limit <= 0:
        raise ValueError("reprocess_limit must be positive")
    apply_baseline_schema(engine)

    with engine.connect() as connection:
        exists = connection.execute(
            select(dataset.c.dataset_id).where(dataset.c.dataset_id == dataset_id)
        ).first()
        if exists is None:
            raise KeyError(f"dataset not deployed: {dataset_id}")

        run_row = _latest(
            connection,
            dataset_run,
            dataset_run.c.dataset_id == dataset_id,
            (dataset_run.c.started_at.desc(), dataset_run.c.dataset_run_id.desc()),
        )
        latest_run = None
        if run_row is not None:
            lineage = connection.execute(
                select(dataset_attempt_lineage).where(
                    dataset_attempt_lineage.c.dataset_run_id == run_row["dataset_run_id"]
                )
            ).mappings().first()
            latest_run = DatasetRunView(
                dataset_run_id=UUID(str(run_row["dataset_run_id"])),
                pipeline_run_id=UUID(str(run_row["pipeline_run_id"])),
                attempt=int(run_row["attempt"]),
                status=str(run_row["status"]),
                effective_config_hash=str(run_row["effective_config_hash"]),
                run_mode=RunMode(str(lineage["run_mode"])) if lineage is not None else None,
                root_dataset_run_id=(
                    _uuid(lineage["root_dataset_run_id"]) if lineage is not None else None
                ),
                previous_dataset_run_id=(
                    _uuid(lineage["previous_dataset_run_id"]) if lineage is not None else None
                ),
                reprocess_request_id=(
                    _uuid(lineage["reprocess_request_id"]) if lineage is not None else None
                ),
                rows_read=run_row["rows_read"],
                rows_accepted=run_row["rows_accepted"],
                rows_quarantined=run_row["rows_quarantined"],
                rows_filtered=run_row["rows_filtered"],
                rows_inserted=run_row["rows_inserted"],
                rows_updated=run_row["rows_updated"],
                rows_deleted=run_row["rows_deleted"],
                error_code=run_row["error_code"],
                error_message=run_row["error_message"],
                retryable=run_row["retryable"],
                started_at=run_row["started_at"],
                completed_at=run_row["completed_at"],
            )

        capture_row = _latest(
            connection,
            capture_receipt,
            capture_receipt.c.dataset_id == dataset_id,
            (capture_receipt.c.completed_at.desc(), capture_receipt.c.capture_receipt_id.desc()),
        )
        latest_capture = None
        if capture_row is not None:
            latest_capture = CaptureCorrelationView(
                capture_receipt_id=UUID(str(capture_row["capture_receipt_id"])),
                dataset_run_id=UUID(str(capture_row["dataset_run_id"])),
                capture_strategy=str(capture_row["capture_strategy"]),
                execution_engine=str(capture_row["execution_engine"]),
                progress_owner=str(capture_row["progress_owner"]),
                native_run_id=capture_row["native_run_id"],
                landing_reference=str(capture_row["landing_reference"]),
                source_reference=capture_row["source_reference"],
                external_checkpoint_reference=capture_row["external_checkpoint_reference"],
                source_lower_bound=capture_row["source_lower_bound"],
                source_upper_bound=capture_row["source_upper_bound"],
                snapshot_id=capture_row["snapshot_id"],
                complete_snapshot=capture_row["complete_snapshot"],
                rows_read=int(capture_row["rows_read"]),
                rows_written=int(capture_row["rows_written"]),
                completed_at=capture_row["completed_at"],
            )

        watermark_row = connection.execute(
            select(watermark).where(watermark.c.dataset_id == dataset_id)
        ).mappings().first()
        watermark_view = (
            WatermarkProgressView(
                committed_value=watermark_row["committed_value"],
                committed_tie_breaker=watermark_row["committed_tie_breaker"],
                committed_dataset_run_id=_uuid(watermark_row["committed_dataset_run_id"]),
                version=int(watermark_row["version"]),
            )
            if watermark_row is not None
            else None
        )

        cdc_row = connection.execute(
            select(cdc_checkpoint).where(cdc_checkpoint.c.dataset_id == dataset_id)
        ).mappings().first()
        cdc_view = (
            CDCProgressView(
                positions=cdc_row["positions"],
                committed_dataset_run_id=UUID(str(cdc_row["committed_dataset_run_id"])),
                version=int(cdc_row["version"]),
            )
            if cdc_row is not None
            else None
        )

        reconciliation_row = _latest(
            connection,
            reconciliation_result,
            reconciliation_result.c.dataset_id == dataset_id,
            (
                reconciliation_result.c.created_at.desc(),
                reconciliation_result.c.reconciliation_id.desc(),
            ),
        )
        reconciliation_view = (
            ReconciliationView(
                reconciliation_id=UUID(str(reconciliation_row["reconciliation_id"])),
                dataset_run_id=UUID(str(reconciliation_row["dataset_run_id"])),
                policy_name=str(reconciliation_row["policy_name"]),
                status=str(reconciliation_row["status"]),
                metrics=dict(reconciliation_row["metrics"]),
                blocks_state_advance=bool(reconciliation_row["blocks_state_advance"]),
                created_at=reconciliation_row["created_at"],
            )
            if reconciliation_row is not None
            else None
        )

        open_quarantine = connection.execute(
            select(
                func.count(quarantine_batch.c.quarantine_id),
                func.coalesce(func.sum(quarantine_batch.c.row_count), 0),
            ).where(
                quarantine_batch.c.dataset_id == dataset_id,
                quarantine_batch.c.replayed_by_dataset_run_id.is_(None),
            )
        ).one()

        schema_row = _latest(
            connection,
            schema_change,
            schema_change.c.dataset_id == dataset_id,
            (schema_change.c.observed_at.desc(), schema_change.c.schema_change_id.desc()),
        )
        schema_view = (
            SchemaChangeView(
                schema_change_id=UUID(str(schema_row["schema_change_id"])),
                dataset_run_id=_uuid(schema_row["dataset_run_id"]),
                observed_fingerprint=str(schema_row["observed_fingerprint"]),
                expected_fingerprint=schema_row["expected_fingerprint"],
                classification=str(schema_row["classification"]),
                details=dict(schema_row["details"]) if schema_row["details"] is not None else None,
                observed_at=schema_row["observed_at"],
            )
            if schema_row is not None
            else None
        )

        active_rows = connection.execute(
            select(reprocess_request)
            .where(
                reprocess_request.c.dataset_id == dataset_id,
                reprocess_request.c.status.in_(
                    [ReprocessRequestStatus.PENDING.value, ReprocessRequestStatus.RUNNING.value]
                ),
            )
            .order_by(reprocess_request.c.created_at.desc(), reprocess_request.c.reprocess_request_id.desc())
            .limit(reprocess_limit)
        ).mappings().all()
        active_requests = tuple(
            ReprocessRequestView(
                reprocess_request_id=UUID(str(row["reprocess_request_id"])),
                run_mode=RunMode(str(row["run_mode"])),
                status=ReprocessRequestStatus(str(row["status"])),
                reason=str(row["reason"]),
                requested_by=str(row["requested_by"]),
                original_pipeline_run_id=_uuid(row["original_pipeline_run_id"]),
                original_dataset_run_id=_uuid(row["original_dataset_run_id"]),
                range_json=dict(row["range_json"]) if row["range_json"] is not None else None,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in active_rows
        )

    return DatasetOperationalSnapshot(
        dataset_id=dataset_id,
        latest_run=latest_run,
        latest_capture=latest_capture,
        watermark=watermark_view,
        cdc_checkpoint=cdc_view,
        latest_reconciliation=reconciliation_view,
        quarantine_backlog=QuarantineBacklogView(
            open_batches=int(open_quarantine[0]),
            open_rows=int(open_quarantine[1]),
        ),
        latest_schema_change=schema_view,
        active_reprocess_requests=active_requests,
    )


def list_dataset_operational_snapshots(engine: Engine) -> tuple[DatasetOperationalSnapshot, ...]:
    """Return stable dataset-id ordered snapshots for an operator overview."""

    apply_baseline_schema(engine)
    with engine.connect() as connection:
        dataset_ids = tuple(connection.execute(select(dataset.c.dataset_id).order_by(dataset.c.dataset_id)).scalars())
    return tuple(get_dataset_operational_snapshot(engine, value) for value in dataset_ids)


__all__ = [
    "CDCProgressView",
    "CaptureCorrelationView",
    "DatasetOperationalSnapshot",
    "DatasetRunView",
    "QuarantineBacklogView",
    "ReconciliationView",
    "ReprocessRequestView",
    "SchemaChangeView",
    "WatermarkProgressView",
    "get_dataset_operational_snapshot",
    "list_dataset_operational_snapshots",
]
