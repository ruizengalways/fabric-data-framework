"""Shared source-order and event-time taxonomy.

Source ordering and business/event valid-time are independent clocks.  Current-state
and history strategies may choose different actions, but they must classify the same
evidence consistently before applying strategy-specific policy.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from ..config import FrozenModel


class TemporalOrderingError(ValueError):
    """Raised when source/event ordering cannot be compared safely."""


class SourceOrderRelation(str, Enum):
    STALE = "STALE"
    EQUAL = "EQUAL"
    NEWER = "NEWER"


class EventTimeRelation(str, Enum):
    EARLIER = "EARLIER"
    EQUAL = "EQUAL"
    LATER = "LATER"
    UNKNOWN = "UNKNOWN"


class TemporalCondition(str, Enum):
    """Provider-neutral condition names consumed by strategy-specific policy."""

    IN_ORDER = "IN_ORDER"
    STALE_SOURCE_POSITION = "STALE_SOURCE_POSITION"
    EQUAL_SOURCE_POSITION = "EQUAL_SOURCE_POSITION"
    LATE_EVENT_TIME = "LATE_EVENT_TIME"
    SAME_EVENT_TIME = "SAME_EVENT_TIME"


class TemporalAssessment(FrozenModel):
    source_order: SourceOrderRelation
    event_time: EventTimeRelation
    condition: TemporalCondition
    requires_history_rewrite: bool = False


def _compare(left: Any, right: Any, *, label: str) -> int:
    try:
        if left < right:
            return -1
        if left > right:
            return 1
        return 0
    except TypeError as exc:
        raise TemporalOrderingError(f"{label} values are not mutually comparable") from exc


def compare_source_order(
    candidate: tuple[Any, ...],
    current: tuple[Any, ...],
) -> SourceOrderRelation:
    """Classify canonical source positions without assigning strategy action."""

    if not candidate or not current:
        raise TemporalOrderingError("source positions cannot be empty")
    if len(candidate) != len(current):
        raise TemporalOrderingError(
            "source positions must have the same arity before comparison"
        )
    comparison = _compare(candidate, current, label="source position")
    if comparison < 0:
        return SourceOrderRelation.STALE
    if comparison > 0:
        return SourceOrderRelation.NEWER
    return SourceOrderRelation.EQUAL


def compare_event_time(
    candidate: datetime | None,
    current: datetime | None,
) -> EventTimeRelation:
    """Compare valid/event time independently from source order."""

    if candidate is None or current is None:
        return EventTimeRelation.UNKNOWN
    if candidate.tzinfo is None or candidate.utcoffset() is None:
        raise TemporalOrderingError("candidate event_time must be timezone-aware")
    if current.tzinfo is None or current.utcoffset() is None:
        raise TemporalOrderingError("current event_time must be timezone-aware")

    comparison = _compare(candidate, current, label="event time")
    if comparison < 0:
        return EventTimeRelation.EARLIER
    if comparison > 0:
        return EventTimeRelation.LATER
    return EventTimeRelation.EQUAL


def assess_temporal(
    *,
    candidate_source_position: tuple[Any, ...],
    current_source_position: tuple[Any, ...],
    candidate_event_time: datetime | None = None,
    current_event_time: datetime | None = None,
) -> TemporalAssessment:
    """Produce one shared classification for current-state/history policy.

    A newer source position with an earlier event/valid time is the important case:
    source ordering proves the event arrived later, while valid-time semantics say it
    belongs before the current version.  Current-state targets may still choose to
    accept/ignore it by policy; SCD2 requires an explicit retroactive-history rewrite
    policy and must otherwise fail closed.
    """

    source_relation = compare_source_order(
        candidate_source_position,
        current_source_position,
    )
    event_relation = compare_event_time(candidate_event_time, current_event_time)

    if source_relation is SourceOrderRelation.STALE:
        return TemporalAssessment(
            source_order=source_relation,
            event_time=event_relation,
            condition=TemporalCondition.STALE_SOURCE_POSITION,
        )
    if source_relation is SourceOrderRelation.EQUAL:
        return TemporalAssessment(
            source_order=source_relation,
            event_time=event_relation,
            condition=TemporalCondition.EQUAL_SOURCE_POSITION,
        )
    if event_relation is EventTimeRelation.EARLIER:
        return TemporalAssessment(
            source_order=source_relation,
            event_time=event_relation,
            condition=TemporalCondition.LATE_EVENT_TIME,
            requires_history_rewrite=True,
        )
    if event_relation is EventTimeRelation.EQUAL:
        return TemporalAssessment(
            source_order=source_relation,
            event_time=event_relation,
            condition=TemporalCondition.SAME_EVENT_TIME,
        )
    return TemporalAssessment(
        source_order=source_relation,
        event_time=event_relation,
        condition=TemporalCondition.IN_ORDER,
    )


__all__ = [
    "EventTimeRelation",
    "SourceOrderRelation",
    "TemporalAssessment",
    "TemporalCondition",
    "TemporalOrderingError",
    "assess_temporal",
    "compare_event_time",
    "compare_source_order",
]
