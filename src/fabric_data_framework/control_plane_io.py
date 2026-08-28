"""Small relational control-plane persistence helpers pending the full repository adapter."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Engine, select

from .control_plane import (
    apply_baseline_schema,
    capture_receipt,
    dataset_attempt_lineage,
    reprocess_request,
)
from .contracts.capture_receipt import CaptureReceipt
from .contracts.recovery import DatasetAttemptLineage, ReprocessRequest


def record_capture_receipt(engine: Engine, receipt: CaptureReceipt) -> None:
    """Append one immutable native/custom capture handoff receipt."""

    apply_baseline_schema(engine)
    with engine.begin() as connection:
        existing = connection.execute(
            select(capture_receipt.c.capture_receipt_id).where(
                capture_receipt.c.capture_receipt_id == str(receipt.capture_receipt_id)
            )
        ).first()
        if existing is not None:
            raise ValueError(
                f"capture receipt {receipt.capture_receipt_id} is already recorded"
            )
        connection.execute(
            capture_receipt.insert().values(
                capture_receipt_id=str(receipt.capture_receipt_id),
                dataset_run_id=str(receipt.dataset_run_id),
                dataset_id=receipt.dataset_id,
                capture_strategy=receipt.capture_strategy.value,
                execution_engine=receipt.execution_engine.value,
                progress_owner=receipt.progress_owner.value,
                native_run_id=receipt.native_run_id,
                source_reference=receipt.source_reference,
                landing_reference=receipt.landing_reference,
                rows_read=receipt.rows_read,
                rows_written=receipt.rows_written,
                source_lower_bound=receipt.source_lower_bound,
                source_upper_bound=receipt.source_upper_bound,
                snapshot_id=receipt.snapshot_id,
                complete_snapshot=receipt.complete_snapshot,
                external_checkpoint_reference=receipt.external_checkpoint_reference,
                schema_version=receipt.schema_version,
                started_at=receipt.started_at,
                completed_at=receipt.completed_at,
                created_at=datetime.now(timezone.utc),
            )
        )


def record_attempt_lineage(engine: Engine, lineage: DatasetAttemptLineage) -> None:
    """Append immutable dataset-attempt linkage before/around execution."""

    apply_baseline_schema(engine)
    with engine.begin() as connection:
        existing = connection.execute(
            select(dataset_attempt_lineage.c.dataset_run_id).where(
                dataset_attempt_lineage.c.dataset_run_id == str(lineage.dataset_run_id)
            )
        ).first()
        if existing is not None:
            raise ValueError(
                f"attempt lineage already recorded for {lineage.dataset_run_id}"
            )
        connection.execute(
            dataset_attempt_lineage.insert().values(
                dataset_run_id=str(lineage.dataset_run_id),
                dataset_id=lineage.dataset_id,
                root_dataset_run_id=str(lineage.root_dataset_run_id),
                previous_dataset_run_id=(
                    str(lineage.previous_dataset_run_id)
                    if lineage.previous_dataset_run_id is not None
                    else None
                ),
                attempt=lineage.attempt,
                run_mode=lineage.run_mode.value,
                reprocess_request_id=(
                    str(lineage.reprocess_request_id)
                    if lineage.reprocess_request_id is not None
                    else None
                ),
                created_at=lineage.created_at,
            )
        )


def record_reprocess_request(engine: Engine, request: ReprocessRequest) -> None:
    """Insert a request or advance only its mutable lifecycle status."""

    apply_baseline_schema(engine)
    request_id = str(request.reprocess_request_id)
    semantic = {
        "dataset_id": request.dataset_id,
        "run_mode": request.run_mode.value,
        "reason": request.reason,
        "requested_by": request.requested_by,
        "original_pipeline_run_id": (
            str(request.original_pipeline_run_id)
            if request.original_pipeline_run_id is not None
            else None
        ),
        "original_dataset_run_id": (
            str(request.original_dataset_run_id)
            if request.original_dataset_run_id is not None
            else None
        ),
        "range_json": request.range_json,
    }
    with engine.begin() as connection:
        existing = connection.execute(
            select(reprocess_request).where(
                reprocess_request.c.reprocess_request_id == request_id
            )
        ).mappings().first()
        if existing is None:
            connection.execute(
                reprocess_request.insert().values(
                    reprocess_request_id=request_id,
                    **semantic,
                    status=request.status.value,
                    created_at=request.created_at,
                    updated_at=request.updated_at,
                )
            )
            return

        for key, expected in semantic.items():
            if existing[key] != expected:
                raise ValueError("reprocess request semantic identity cannot change")
        connection.execute(
            reprocess_request.update()
            .where(reprocess_request.c.reprocess_request_id == request_id)
            .values(
                status=request.status.value,
                updated_at=request.updated_at or datetime.now(timezone.utc),
            )
        )


__all__ = [
    "record_attempt_lineage",
    "record_capture_receipt",
    "record_reprocess_request",
]
