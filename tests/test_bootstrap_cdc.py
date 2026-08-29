from datetime import datetime, timezone

import pytest

from fabric_data_framework.apply.cdc import CDC_POSITION, apply_cdc_current_state
from fabric_data_framework.capture.bootstrap_cdc import (
    CDCBootstrapEvidence,
    CDCBootstrapEvidenceError,
    normalize_bootstrap_cdc_batch,
    plan_cdc_bootstrap,
)
from fabric_data_framework.capture.cdc import (
    CDCEvent,
    CDCOperation,
    CDCSourcePosition,
    build_cdc_checkpoint,
)
from fabric_data_framework.config import ApplyStrategy


def _event(event_id: str, position: int, *, name: str) -> CDCEvent:
    return CDCEvent(
        event_id=event_id,
        operation=CDCOperation.UPDATE,
        key={"customer_id": 1},
        position=CDCSourcePosition(partition="p0", values=(position, 0)),
        after={"customer_id": 1, "name": name},
        event_time=datetime(2026, 8, 29, 0, position % 60, tzinfo=timezone.utc),
    )


def _evidence(
    *,
    stream_start: int = 8,
    snapshot: int = 10,
    complete_snapshot: bool = True,
    consistent: bool = True,
    retained: bool = True,
) -> CDCBootstrapEvidence:
    return CDCBootstrapEvidence(
        dataset_id="crm.customer",
        snapshot_id="snapshot-001",
        source_epoch="primary-incarnation-7",
        stream_start_checkpoint=build_cdc_checkpoint({"p0": (stream_start, 0)}),
        snapshot_checkpoint=build_cdc_checkpoint({"p0": (snapshot, 0)}),
        complete_snapshot=complete_snapshot,
        snapshot_consistent_through_checkpoint=consistent,
        stream_retained_from_start=retained,
    )


def test_bootstrap_requires_complete_consistent_snapshot_and_retained_stream():
    with pytest.raises(CDCBootstrapEvidenceError, match="complete snapshot"):
        plan_cdc_bootstrap(_evidence(complete_snapshot=False))

    with pytest.raises(CDCBootstrapEvidenceError, match="consistent through"):
        plan_cdc_bootstrap(_evidence(consistent=False))

    with pytest.raises(CDCBootstrapEvidenceError, match="retained/buffered"):
        plan_cdc_bootstrap(_evidence(retained=False))


def test_bootstrap_rejects_stream_that_starts_after_snapshot_fence():
    with pytest.raises(CDCBootstrapEvidenceError, match="starts after snapshot"):
        plan_cdc_bootstrap(_evidence(stream_start=11, snapshot=10))


def test_bootstrap_rejects_partition_change_during_handoff():
    evidence = CDCBootstrapEvidence(
        dataset_id="crm.customer",
        snapshot_id="snapshot-001",
        source_epoch="epoch-1",
        stream_start_checkpoint=build_cdc_checkpoint({"p0": (8, 0)}),
        snapshot_checkpoint=build_cdc_checkpoint({"p0": (10, 0), "p1": (3, 0)}),
        complete_snapshot=True,
        snapshot_consistent_through_checkpoint=True,
        stream_retained_from_start=True,
    )

    with pytest.raises(CDCBootstrapEvidenceError, match="partition set changed"):
        plan_cdc_bootstrap(evidence)


def test_bootstrap_normalization_drops_snapshot_covered_events_and_keeps_strictly_newer():
    events = [
        _event("e9", 9, name="covered-before-fence"),
        _event("e10", 10, name="covered-at-fence"),
        _event("e11", 11, name="after-fence"),
        _event("e12", 12, name="latest"),
    ]
    batch = normalize_bootstrap_cdc_batch(
        events,
        evidence=_evidence(),
        upper_checkpoint=build_cdc_checkpoint({"p0": (12, 0)}),
        complete_through_upper=True,
    )

    assert [event.event_id for event in batch.events] == ["e11", "e12"]
    assert batch.already_committed_events_ignored == 2
    assert batch.lower_checkpoint == build_cdc_checkpoint({"p0": (10, 0)})


def test_snapshot_to_cdc_current_state_has_no_double_apply_and_no_gap():
    snapshot_rows = [{"customer_id": 1, "name": "snapshot-at-10"}]
    batch = normalize_bootstrap_cdc_batch(
        [
            _event("e9", 9, name="old"),
            _event("e10", 10, name="snapshot-at-10"),
            _event("e11", 11, name="cdc-11"),
        ],
        evidence=_evidence(),
        upper_checkpoint=build_cdc_checkpoint({"p0": (11, 0)}),
        complete_through_upper=True,
    )
    result = apply_cdc_current_state(
        snapshot_rows,
        batch,
        merge_key=("customer_id",),
        strategy=ApplyStrategy.SCD1,
    )

    assert len(result.rows) == 1
    assert result.rows[0]["name"] == "cdc-11"
    assert result.rows[0][CDC_POSITION] == (11, 0)
    assert result.mutations.updated == 1
    assert batch.already_committed_events_ignored == 2


def test_bootstrap_first_cdc_upper_cannot_regress_below_snapshot_checkpoint():
    with pytest.raises(Exception, match="regressed partition p0"):
        normalize_bootstrap_cdc_batch(
            [],
            evidence=_evidence(snapshot=10),
            upper_checkpoint=build_cdc_checkpoint({"p0": (9, 0)}),
            complete_through_upper=True,
        )
