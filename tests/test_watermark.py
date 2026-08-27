from datetime import datetime, timezone

from fabric_data_framework.config import WatermarkConfig
from fabric_data_framework.runtime import WatermarkPosition
from fabric_data_framework.watermark import plan_watermark_batch


def dt(hour: int):
    return datetime(2026, 8, 1, hour, tzinfo=timezone.utc)


def test_composite_watermark_selects_duplicate_timestamp_by_tie_breaker():
    rows = [
        {"customer_id": "C001", "modified_at": dt(10)},
        {"customer_id": "C002", "modified_at": dt(10)},
        {"customer_id": "C003", "modified_at": dt(11)},
    ]
    config = WatermarkConfig(column="modified_at", tie_breaker=("customer_id",))
    batch = plan_watermark_batch(
        rows,
        config,
        WatermarkPosition(value=dt(10), tie_breaker=("C001",)),
    )
    assert [row["customer_id"] for row in batch.rows] == ["C002", "C003"]
    assert batch.after == WatermarkPosition(value=dt(11), tie_breaker=("C003",))


def test_no_new_rows_preserves_watermark():
    config = WatermarkConfig(column="modified_at", tie_breaker=("customer_id",))
    before = WatermarkPosition(value=dt(10), tie_breaker=("C002",))
    batch = plan_watermark_batch(
        [{"customer_id": "C001", "modified_at": dt(10)}],
        config,
        before,
    )
    assert batch.rows == ()
    assert batch.after == before
