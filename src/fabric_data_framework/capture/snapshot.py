"""SNAPSHOT capture contract built on explicit complete-snapshot evidence."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .full import (
    FullCaptureBatch,
    FullSnapshotEvidence,
    FullSnapshotEvidenceError,
    capture_full_snapshot,
)

SnapshotEvidence = FullSnapshotEvidence
SnapshotEvidenceError = FullSnapshotEvidenceError
SnapshotCaptureBatch = FullCaptureBatch


def capture_snapshot(
    rows: Sequence[Mapping[str, Any]],
    *,
    evidence: SnapshotEvidence,
) -> SnapshotCaptureBatch:
    return capture_full_snapshot(rows, evidence=evidence)
