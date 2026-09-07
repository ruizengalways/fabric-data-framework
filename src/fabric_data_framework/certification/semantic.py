"""Thin installed-package semantic probes not tied to a customer repository."""

from __future__ import annotations

from datetime import datetime, timezone

from fabric_data_framework.capture.cdc import (
    CDCEvent,
    CDCOperation,
    CDCSourcePosition,
    build_cdc_checkpoint,
    normalize_cdc_batch,
)
from fabric_data_framework.capture.watermark import plan_watermark_batch
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    LoadPolicy,
    WatermarkConfig,
)


def run_semantic_acceptance() -> dict[str, str]:
    """Exercise installed metadata, incremental and CDC contracts before Fabric IO."""

    watermark = WatermarkConfig(column="modified_at", tie_breaker=("customer_id",))
    policy = LoadPolicy(
        capture_strategy=CaptureStrategy.WATERMARK,
        apply_strategy=ApplyStrategy.SCD1,
        merge_key=("customer_id",),
        watermark=watermark,
    )
    if policy.watermark != watermark:
        raise AssertionError("metadata/config acceptance failed")

    t1 = datetime(2026, 9, 7, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 7, 2, tzinfo=timezone.utc)
    first = plan_watermark_batch(
        [
            {"customer_id": "C2", "modified_at": t2},
            {"customer_id": "C1", "modified_at": t1},
        ],
        watermark,
        None,
    )
    if [row["customer_id"] for row in first.rows] != ["C1", "C2"]:
        raise AssertionError("incremental watermark ordering acceptance failed")
    rerun = plan_watermark_batch(list(first.rows), watermark, first.after)
    if rerun.rows != ():
        raise AssertionError("incremental watermark rerun acceptance failed")

    event = CDCEvent(
        event_id="cert-cdc-1",
        operation=CDCOperation.INSERT,
        key={"customer_id": "C1"},
        position=CDCSourcePosition(partition="p0", values=(1,)),
        after={"customer_id": "C1", "name": "Alice"},
        event_time=t1,
    )
    batch = normalize_cdc_batch(
        [event, event],
        upper_checkpoint=build_cdc_checkpoint({"p0": (1,)}),
        complete_through_upper=True,
    )
    if len(batch.events) != 1 or batch.duplicate_events_ignored != 1:
        raise AssertionError("CDC duplicate/idempotency acceptance failed")

    return {
        "metadata.config": "PASS",
        "incremental.watermark": "PASS",
        "cdc.normalization": "PASS",
    }


__all__ = ["run_semantic_acceptance"]
