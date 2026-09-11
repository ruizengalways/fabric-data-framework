"""Reusable WATERMARK planning and deterministic composite-position filtering."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import cmp_to_key
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from fabric_data_framework.metadata.config import WatermarkConfig
from fabric_data_framework.contracts.runtime import (
    WatermarkPosition,
    compare_watermark_positions,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class WatermarkBatch(FrozenModel):
    rows: tuple[dict[str, Any], ...]
    before: WatermarkPosition | None
    after: WatermarkPosition | None


def _position_for_row(row: Mapping[str, Any], config: WatermarkConfig) -> WatermarkPosition:
    try:
        value = row[config.column]
    except KeyError as exc:
        raise KeyError(f"watermark column missing from source row: {config.column}") from exc
    if value is None:
        raise ValueError(f"watermark column {config.column} cannot be null")
    try:
        tie_breaker = tuple(row[column] for column in config.tie_breaker)
    except KeyError as exc:
        raise KeyError(f"watermark tie-breaker column missing from source row: {exc.args[0]}") from exc
    if any(value is None for value in tie_breaker):
        raise ValueError("watermark tie-breaker values cannot be null")
    return WatermarkPosition(value=value, tie_breaker=tie_breaker)


def _compare_positioned(
    left: tuple[dict[str, Any], WatermarkPosition],
    right: tuple[dict[str, Any], WatermarkPosition],
) -> int:
    return compare_watermark_positions(left[1], right[1])


def _overlap_lower_bound(before: WatermarkPosition, config: WatermarkConfig) -> datetime:
    if not isinstance(before.value, datetime):
        raise TypeError("positive watermark overlap window requires datetime watermark values")
    return before.value.astimezone(timezone.utc) - timedelta(
        seconds=config.overlap_window_seconds
    )


def _validate_before(before: WatermarkPosition, config: WatermarkConfig) -> None:
    if len(before.tie_breaker) != len(config.tie_breaker):
        raise ValueError(
            "committed watermark tie-breaker arity does not match current watermark configuration"
        )


def plan_watermark_batch(
    rows: Sequence[Mapping[str, Any]],
    config: WatermarkConfig,
    before: WatermarkPosition | None,
) -> WatermarkBatch:
    """Select a deterministic batch without allowing an overlap read to regress state.

    A positive overlap window deliberately re-reads rows older than the committed
    checkpoint. Those rows remain available to idempotent downstream apply logic, but
    the returned ``after`` position is the maximum of the committed position and the
    selected source positions.
    """

    if before is not None:
        _validate_before(before, config)

    positioned = [(dict(row), _position_for_row(row, config)) for row in rows]
    positioned.sort(key=cmp_to_key(_compare_positioned))

    if before is None:
        selected = positioned
    elif config.overlap_window_seconds > 0:
        lower_bound = _overlap_lower_bound(before, config)
        selected = []
        for item in positioned:
            position = item[1]
            if not isinstance(position.value, datetime):
                raise TypeError(
                    "positive watermark overlap window requires datetime watermark values"
                )
            if position.value.astimezone(timezone.utc) >= lower_bound:
                selected.append(item)
    else:
        selected = [
            item
            for item in positioned
            if compare_watermark_positions(item[1], before) > 0
        ]

    if not selected:
        return WatermarkBatch(rows=(), before=before, after=before)

    candidate_after = selected[-1][1]
    after = candidate_after
    if before is not None and compare_watermark_positions(candidate_after, before) <= 0:
        after = before

    return WatermarkBatch(
        rows=tuple(item[0] for item in selected),
        before=before,
        after=after,
    )
