"""Small relational control-plane persistence helpers pending the full repository adapter."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Engine, select

from .control_plane import apply_baseline_schema, capture_receipt
from .contracts.capture_receipt import CaptureReceipt


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
