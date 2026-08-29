from datetime import datetime, timedelta, timezone

import pytest

from fabric_data_framework.quality.temporal import (
    EventTimeRelation,
    SourceOrderRelation,
    TemporalCondition,
    TemporalOrderingError,
    assess_temporal,
    compare_event_time,
    compare_source_order,
)


BASE = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)


def test_source_order_relation_is_shared_and_deterministic():
    assert compare_source_order((9, 1), (10, 0)) is SourceOrderRelation.STALE
    assert compare_source_order((10, 0), (10, 0)) is SourceOrderRelation.EQUAL
    assert compare_source_order((10, 1), (10, 0)) is SourceOrderRelation.NEWER


def test_source_order_rejects_arity_and_type_ambiguity():
    with pytest.raises(TemporalOrderingError, match="same arity"):
        compare_source_order((1,), (1, 0))

    with pytest.raises(TemporalOrderingError, match="not mutually comparable"):
        compare_source_order(("10",), (10,))


def test_event_time_relation_is_independent_from_source_order():
    assert compare_event_time(BASE - timedelta(seconds=1), BASE) is EventTimeRelation.EARLIER
    assert compare_event_time(BASE, BASE) is EventTimeRelation.EQUAL
    assert compare_event_time(BASE + timedelta(seconds=1), BASE) is EventTimeRelation.LATER
    assert compare_event_time(None, BASE) is EventTimeRelation.UNKNOWN


def test_event_time_requires_timezone_aware_values():
    with pytest.raises(TemporalOrderingError, match="candidate event_time"):
        compare_event_time(datetime(2026, 8, 29, 0, 0), BASE)

    with pytest.raises(TemporalOrderingError, match="current event_time"):
        compare_event_time(BASE, datetime(2026, 8, 29, 0, 0))


def test_stale_source_position_remains_stale_even_when_event_time_is_later():
    decision = assess_temporal(
        candidate_source_position=(9, 0),
        current_source_position=(10, 0),
        candidate_event_time=BASE + timedelta(hours=1),
        current_event_time=BASE,
    )

    assert decision.source_order is SourceOrderRelation.STALE
    assert decision.event_time is EventTimeRelation.LATER
    assert decision.condition is TemporalCondition.STALE_SOURCE_POSITION
    assert decision.requires_history_rewrite is False


def test_equal_source_position_has_explicit_conflict_boundary():
    decision = assess_temporal(
        candidate_source_position=(10, 0),
        current_source_position=(10, 0),
        candidate_event_time=BASE + timedelta(seconds=1),
        current_event_time=BASE,
    )

    assert decision.condition is TemporalCondition.EQUAL_SOURCE_POSITION
    assert decision.source_order is SourceOrderRelation.EQUAL


def test_newer_source_with_earlier_event_time_requires_history_rewrite():
    decision = assess_temporal(
        candidate_source_position=(11, 0),
        current_source_position=(10, 0),
        candidate_event_time=BASE - timedelta(seconds=5),
        current_event_time=BASE,
    )

    assert decision.source_order is SourceOrderRelation.NEWER
    assert decision.event_time is EventTimeRelation.EARLIER
    assert decision.condition is TemporalCondition.LATE_EVENT_TIME
    assert decision.requires_history_rewrite is True


def test_newer_source_with_same_event_time_is_not_retroactive():
    decision = assess_temporal(
        candidate_source_position=(11, 0),
        current_source_position=(10, 0),
        candidate_event_time=BASE,
        current_event_time=BASE,
    )

    assert decision.condition is TemporalCondition.SAME_EVENT_TIME
    assert decision.requires_history_rewrite is False


def test_newer_source_without_valid_time_is_still_source_in_order():
    decision = assess_temporal(
        candidate_source_position=(11, 0),
        current_source_position=(10, 0),
    )

    assert decision.event_time is EventTimeRelation.UNKNOWN
    assert decision.condition is TemporalCondition.IN_ORDER
    assert decision.requires_history_rewrite is False
