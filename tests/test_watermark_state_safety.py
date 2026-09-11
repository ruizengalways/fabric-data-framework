from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from fabric_data_framework.capture.watermark import plan_watermark_batch
from fabric_data_framework.contracts.runtime import (
    StateCommitGate,
    WatermarkConflictError,
    WatermarkPosition,
    WatermarkTransition,
    compare_watermark_positions,
)
from fabric_data_framework.control_plane.repository import InMemoryControlPlane
from fabric_data_framework.control_plane.schema import apply_baseline_schema, watermark
from fabric_data_framework.control_plane.sqlalchemy_repository import SqlAlchemyControlPlaneRepository
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DatasetConfig,
    LoadPolicy,
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
)


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 11, hour, minute, tzinfo=timezone.utc)


def _config() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="crm.customer",
        source=SourceConfig(system="crm", object="customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.SCD2,
            watermark=WatermarkConfig(
                column="updated_at",
                tie_breaker=("customer_id",),
                overlap_window_seconds=300,
            ),
            business_key=("customer_id",),
            merge_key=("customer_id",),
            tracked_columns=("email",),
            event_time_column="updated_at",
        ),
    )


def _gate() -> StateCommitGate:
    return StateCommitGate(
        target_committed=True,
        reconciliation_required=True,
        reconciliation_passed=True,
    )


def test_overlap_only_old_rows_are_re_read_without_regressing_checkpoint():
    config = WatermarkConfig(
        column="updated_at", tie_breaker=("customer_id",), overlap_window_seconds=300
    )
    before = WatermarkPosition(value=_dt(12), tie_breaker=("C9",))
    batch = plan_watermark_batch(
        (
            {"customer_id": "C1", "updated_at": _dt(11, 58)},
            {"customer_id": "C2", "updated_at": _dt(11, 59)},
        ),
        config,
        before,
    )

    assert len(batch.rows) == 2
    assert batch.after == before


def test_same_watermark_value_uses_tie_breaker_order_and_exact_equal_is_stable():
    config = WatermarkConfig(column="updated_at", tie_breaker=("customer_id",))
    before = WatermarkPosition(value=_dt(12), tie_breaker=("C1",))

    newer = plan_watermark_batch(
        ({"customer_id": "C2", "updated_at": _dt(12)},), config, before
    )
    assert newer.after == WatermarkPosition(value=_dt(12), tie_breaker=("C2",))

    equal = plan_watermark_batch(
        ({"customer_id": "C1", "updated_at": _dt(12)},), config, before
    )
    assert equal.rows == ()
    assert equal.after == before


def test_watermark_comparison_rejects_incompatible_types_and_bool():
    with pytest.raises(TypeError, match="not safely comparable"):
        compare_watermark_positions(
            WatermarkPosition(value="12", tie_breaker=()),
            WatermarkPosition(value=12, tie_breaker=()),
        )

    with pytest.raises((TypeError, ValueError)):
        WatermarkPosition(value=True, tie_breaker=())


def test_transition_rejects_regression_even_when_commit_gate_passes():
    with pytest.raises(ValueError, match="cannot move backwards"):
        WatermarkTransition(
            before=WatermarkPosition(value=_dt(12), tie_breaker=("C1",)),
            after=WatermarkPosition(value=_dt(11, 59), tie_breaker=("C9",)),
            gate=_gate(),
        )


def test_in_memory_watermark_compare_and_set_rejects_stale_writer():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config())

    initial = repository.get_watermark_state("crm.customer")
    first = repository.commit_watermark(
        "crm.customer",
        WatermarkPosition(value=_dt(12), tie_breaker=("C1",)),
        expected_version=initial.version,
    )
    repository.commit_watermark(
        "crm.customer",
        WatermarkPosition(value=_dt(13), tie_breaker=("C1",)),
        expected_version=first.version,
    )

    with pytest.raises(WatermarkConflictError, match="stale watermark writer"):
        repository.commit_watermark(
            "crm.customer",
            WatermarkPosition(value=_dt(14), tie_breaker=("C1",)),
            expected_version=first.version,
        )

    assert repository.get_watermark("crm.customer") == WatermarkPosition(
        value=_dt(13), tie_breaker=("C1",)
    )


def test_sqlalchemy_datetime_watermark_round_trip_and_cas(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'watermark.db'}")
    apply_baseline_schema(engine)
    repository = SqlAlchemyControlPlaneRepository(
        engine,
        domain="customer",
        domain_git_sha="abcdef0",
        framework_version="0.4.0",
    )
    repository.deploy_dataset(_config())

    initial = repository.get_watermark_state("crm.customer")
    committed = repository.commit_watermark(
        "crm.customer",
        WatermarkPosition(value=_dt(12), tie_breaker=("C1",)),
        expected_version=initial.version,
    )
    round_trip = repository.get_watermark_state("crm.customer")

    assert round_trip == committed
    assert round_trip.position is not None
    assert round_trip.position.value == _dt(12)
    assert round_trip.position.tie_breaker == ("C1",)

    repository.commit_watermark(
        "crm.customer",
        WatermarkPosition(value=_dt(13), tie_breaker=("C1",)),
        expected_version=committed.version,
    )
    with pytest.raises(WatermarkConflictError):
        repository.commit_watermark(
            "crm.customer",
            WatermarkPosition(value=_dt(14), tie_breaker=("C1",)),
            expected_version=committed.version,
        )


def test_sqlalchemy_corrupt_tagged_watermark_fails_closed(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'corrupt.db'}")
    apply_baseline_schema(engine)
    repository = SqlAlchemyControlPlaneRepository(
        engine,
        domain="customer",
        domain_git_sha="abcdef0",
        framework_version="0.4.0",
    )
    repository.deploy_dataset(_config())
    repository.commit_watermark(
        "crm.customer",
        WatermarkPosition(value=_dt(12), tie_breaker=("C1",)),
        expected_version=0,
    )

    with engine.begin() as connection:
        connection.execute(
            watermark.update()
            .where(watermark.c.dataset_id == "crm.customer")
            .values(committed_value={"$type": "datetime", "value": "not-a-datetime"})
        )

    with pytest.raises(RuntimeError, match="persisted watermark state is malformed"):
        repository.get_watermark_state("crm.customer")
