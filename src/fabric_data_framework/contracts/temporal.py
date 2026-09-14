"""Provider-neutral UTC clock and timezone-awareness invariants."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, TypeAlias


Clock: TypeAlias = Callable[[], datetime]


def utc_now() -> datetime:
    """Return an aware current UTC timestamp."""

    return datetime.now(timezone.utc)


def require_aware_datetime(value: datetime, field_name: str) -> None:
    """Fail closed when a contract timestamp has no timezone information."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


__all__ = ["Clock", "require_aware_datetime", "utc_now"]
