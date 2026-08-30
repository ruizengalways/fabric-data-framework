"""Reusable WATERMARK planning and deterministic composite-position filtering."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from fabric_data_framework.metadata.config import WatermarkConfig
from fabric_data_framework.contracts.runtime import WatermarkPosition


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


def _ordering_key(position: WatermarkPosition) -> tuple[Any, tuple[str | int | float, ...]]:
    return (position.value, position.tie_breaker)


def _lower_bound(before: WatermarkPosition, config: WatermarkConfig) -> WatermarkPosition:
    if config.overlap_window_seconds <= 0:
        return before
    if not isinstance(before.value, datetime):
        raise TypeError("positive watermark overlap window requires datetime watermark values")
    return WatermarkPosition(
        value=before.value - timedelta(seconds=config.overlap_window_seconds),
        tie_breaker=(),
    )


def plan_watermark_batch(
    rows: Sequence[Mapping[str, Any]],
    config: WatermarkConfig,
    before: WatermarkPosition | None,
) -> WatermarkBatch:
    """Select rows newer than the committed composite watermark.

    Rows are sorted by `(watermark value, tie_breaker...)` to make downstream
    processing deterministic. With a configured overlap window, rows at or above
    the overlapped lower bound are re-read and must be handled idempotently by the
    target strategy.
    """

    positioned = [(dict(row), _position_for_row(row, config)) for row in rows]
    positioned.sort(key=lambda item: _ordering_key(item[1]))

    if before is None:
        selected = positioned
    else:
        lower_bound = _lower_bound(before, config)
        if config.overlap_window_seconds > 0:
            selected = [item for item in positioned if _ordering_key(item[1]) >= _ordering_key(lower_bound)]
        else:
            selected = [item for item in positioned if _ordering_key(item[1]) > _ordering_key(before)]

    if not selected:
        return WatermarkBatch(rows=(), before=before, after=before)

    return WatermarkBatch(
        rows=tuple(item[0] for item in selected),
        before=before,
        after=selected[-1][1],
    )
