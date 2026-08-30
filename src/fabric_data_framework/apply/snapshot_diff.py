"""Complete-snapshot diff planning with explicit delete safety."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from pydantic import Field

from ..capture.full import FullSnapshotEvidence
from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.contracts.audit import MutationCounts


class SnapshotDiffError(ValueError):
    """Raised when snapshot identity or delete safety cannot be proven."""


class SnapshotDiffPolicy(FrozenModel):
    require_complete_snapshot: bool = True
    propagate_deletes: bool = False
    allow_delete_all: bool = False
    allow_delete_with_quarantine: bool = False
    max_delete_fraction: float | None = Field(default=None, ge=0.0, le=1.0)


@dataclass(frozen=True)
class SnapshotDiffPlan:
    rows: tuple[dict[str, Any], ...]
    inserted_keys: tuple[tuple[Any, ...], ...]
    updated_keys: tuple[tuple[Any, ...], ...]
    deleted_keys: tuple[tuple[Any, ...], ...]
    unchanged_keys: tuple[tuple[Any, ...], ...]
    mutations: MutationCounts


def _key(row: Mapping[str, Any], merge_key: tuple[str, ...]) -> tuple[Any, ...]:
    try:
        values = tuple(row[column] for column in merge_key)
    except KeyError as exc:
        raise SnapshotDiffError(f"missing merge-key column: {exc.args[0]}") from exc
    if any(value is None for value in values):
        raise SnapshotDiffError("snapshot merge-key values must not be null")
    return values


def _index(
    rows: Sequence[Mapping[str, Any]],
    merge_key: tuple[str, ...],
    *,
    label: str,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    indexed: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        row_key = _key(row, merge_key)
        if row_key in indexed:
            raise SnapshotDiffError(f"duplicate {label} merge key: {row_key}")
        indexed[row_key] = dict(row)
    return indexed


def _changed(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    tracked_columns: tuple[str, ...],
) -> bool:
    if tracked_columns:
        return any(before.get(column) != after.get(column) for column in tracked_columns)
    return dict(before) != dict(after)


def plan_snapshot_diff(
    current_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    *,
    evidence: FullSnapshotEvidence,
    merge_key: tuple[str, ...],
    tracked_columns: tuple[str, ...] = (),
    quarantined_count: int = 0,
    policy: SnapshotDiffPolicy | None = None,
) -> SnapshotDiffPlan:
    """Calculate I/U/D without mutating the target.

    Missing source keys become deletes only when the snapshot is explicitly complete
    and delete policy permits it. Row quarantine blocks delete inference by default
    because a quarantined source key must not be misread as source-side deletion.
    """

    if not merge_key:
        raise SnapshotDiffError("SNAPSHOT_DIFF requires merge_key")
    policy = policy or SnapshotDiffPolicy()
    if policy.require_complete_snapshot and not evidence.complete:
        raise SnapshotDiffError("SNAPSHOT_DIFF requires complete snapshot evidence")

    current = _index(current_rows, merge_key, label="target")
    candidate = _index(candidate_rows, merge_key, label="candidate")

    current_keys = set(current)
    candidate_keys = set(candidate)
    inserted = tuple(sorted(candidate_keys - current_keys, key=repr))
    missing = tuple(sorted(current_keys - candidate_keys, key=repr))
    common = tuple(sorted(current_keys & candidate_keys, key=repr))
    updated = tuple(
        key for key in common if _changed(current[key], candidate[key], tracked_columns)
    )
    updated_set = set(updated)
    unchanged = tuple(key for key in common if key not in updated_set)

    deleted: tuple[tuple[Any, ...], ...] = ()
    if policy.propagate_deletes:
        if quarantined_count and not policy.allow_delete_with_quarantine:
            raise SnapshotDiffError(
                "delete inference is blocked when source rows were quarantined"
            )
        deleted = missing
        if current and len(deleted) == len(current) and not policy.allow_delete_all:
            raise SnapshotDiffError("snapshot would delete all existing target rows")
        if policy.max_delete_fraction is not None and current:
            delete_fraction = len(deleted) / len(current)
            if delete_fraction > policy.max_delete_fraction:
                raise SnapshotDiffError(
                    "snapshot delete fraction exceeds configured guard: "
                    f"delete_fraction={delete_fraction:.6f}, "
                    f"max={policy.max_delete_fraction:.6f}"
                )

    if policy.propagate_deletes:
        final = tuple(candidate[key] for key in sorted(candidate, key=repr))
    else:
        final_map = dict(current)
        final_map.update(candidate)
        final = tuple(final_map[key] for key in sorted(final_map, key=repr))

    return SnapshotDiffPlan(
        rows=final,
        inserted_keys=inserted,
        updated_keys=updated,
        deleted_keys=deleted,
        unchanged_keys=unchanged,
        mutations=MutationCounts(
            inserted=len(inserted),
            updated=len(updated),
            deleted=len(deleted),
        ),
    )
