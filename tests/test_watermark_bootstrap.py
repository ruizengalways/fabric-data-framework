from datetime import datetime, timezone

import pytest

from fabric_data_framework.capture.bootstrap_watermark import (
    WatermarkBootstrapEvidence,
    WatermarkBootstrapEvidenceError,
    assert_same_watermark_bootstrap,
    plan_first_watermark_batch,
    plan_watermark_bootstrap,
)
from fabric_data_framework.config import WatermarkConfig
from fabric_data_framework.runtime import WatermarkPosition


def _evidence(**overrides):
    values = {
        "dataset_id": "crm.customer",
        "snapshot_id": "snapshot-001",
        "source_epoch": "crm-primary-v1",
        "boundary": WatermarkPosition(value=100, tie_breaker=(10,)),
        "complete_baseline": True,
        "baseline_consistent_through_boundary": True,
        "watermark_ordering_verified": True,
        "post_boundary_changes_guaranteed_visible": True,
    }
    values.update(overrides)
    return WatermarkBootstrapEvidence(**values)


def test_strict_watermark_bootstrap_produces_committed_baseline_boundary():
    config = WatermarkConfig(column="version", tie_breaker=("id",))
    evidence = _evidence()

    plan = plan_watermark_bootstrap(evidence, config)

    assert plan.dataset_id == "crm.customer"
    assert plan.baseline_watermark == WatermarkPosition(value=100, tie_breaker=(10,))
    assert plan.overlap_window_seconds == 0
    assert plan.first_incremental_may_reread_baseline is False
    assert plan.requires_idempotent_downstream is False


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("complete_baseline", "complete authoritative baseline"),
        ("baseline_consistent_through_boundary", "consistent through the boundary"),
        ("watermark_ordering_verified", "deterministic source ordering"),
        ("post_boundary_changes_guaranteed_visible", "future source changes remain visible"),
    ],
)
def test_watermark_bootstrap_fails_closed_without_required_source_proof(field, message):
    config = WatermarkConfig(column="version", tie_breaker=("id",))
    with pytest.raises(WatermarkBootstrapEvidenceError, match=message):
        plan_watermark_bootstrap(_evidence(**{field: False}), config)


def test_watermark_bootstrap_rejects_null_boundary_and_tie_breaker_mismatch():
    config = WatermarkConfig(column="version", tie_breaker=("id",))

    with pytest.raises(WatermarkBootstrapEvidenceError, match="cannot be null"):
        plan_watermark_bootstrap(
            _evidence(boundary=WatermarkPosition(value=None, tie_breaker=(10,))),
            config,
        )

    with pytest.raises(WatermarkBootstrapEvidenceError, match="tie-breaker arity"):
        plan_watermark_bootstrap(
            _evidence(boundary=WatermarkPosition(value=100, tie_breaker=())),
            config,
        )


def test_strict_watermark_bootstrap_requires_deterministic_tie_breaker():
    config = WatermarkConfig(column="version")
    evidence = _evidence(boundary=WatermarkPosition(value=100))

    with pytest.raises(WatermarkBootstrapEvidenceError, match="deterministic tie-breaker"):
        plan_watermark_bootstrap(evidence, config)


def test_positive_lookback_bootstrap_requires_datetime_boundary():
    config = WatermarkConfig(column="updated_at", overlap_window_seconds=300)
    evidence = _evidence(boundary=WatermarkPosition(value=100))

    with pytest.raises(WatermarkBootstrapEvidenceError, match="datetime boundary"):
        plan_watermark_bootstrap(evidence, config)


def test_first_strict_incremental_starts_after_composite_baseline_boundary():
    config = WatermarkConfig(column="version", tie_breaker=("id",))
    evidence = _evidence()
    rows = [
        {"id": 9, "version": 99, "name": "already in baseline"},
        {"id": 10, "version": 100, "name": "exact boundary"},
        {"id": 11, "version": 100, "name": "same version after boundary tie-breaker"},
        {"id": 1, "version": 101, "name": "new version"},
    ]

    batch = plan_first_watermark_batch(rows, evidence=evidence, config=config)

    assert [(row["version"], row["id"]) for row in batch.rows] == [(100, 11), (101, 1)]
    assert batch.before == evidence.boundary
    assert batch.after == WatermarkPosition(value=101, tie_breaker=(1,))


def test_first_lookback_incremental_intentionally_rereads_baseline_overlap():
    boundary_time = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)
    config = WatermarkConfig(column="updated_at", overlap_window_seconds=300)
    evidence = _evidence(boundary=WatermarkPosition(value=boundary_time))
    rows = [
        {
            "id": 1,
            "updated_at": datetime(2026, 8, 29, 9, 54, tzinfo=timezone.utc),
        },
        {
            "id": 2,
            "updated_at": datetime(2026, 8, 29, 9, 58, tzinfo=timezone.utc),
        },
        {"id": 3, "updated_at": boundary_time},
        {
            "id": 4,
            "updated_at": datetime(2026, 8, 29, 10, 2, tzinfo=timezone.utc),
        },
    ]

    plan = plan_watermark_bootstrap(evidence, config)
    batch = plan_first_watermark_batch(rows, evidence=evidence, config=config)

    assert plan.first_incremental_may_reread_baseline is True
    assert plan.requires_idempotent_downstream is True
    assert [row["id"] for row in batch.rows] == [2, 3, 4]
    assert batch.after == WatermarkPosition(
        value=datetime(2026, 8, 29, 10, 2, tzinfo=timezone.utc)
    )


def test_retry_must_reuse_exact_watermark_bootstrap_evidence():
    expected = _evidence()
    assert_same_watermark_bootstrap(expected, expected.model_copy())

    changed = expected.model_copy(update={"snapshot_id": "snapshot-002"})
    with pytest.raises(WatermarkBootstrapEvidenceError, match="changed between attempts"):
        assert_same_watermark_bootstrap(expected, changed)
