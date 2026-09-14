from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from fabric_data_framework.contracts.hashing import canonical_hash
from fabric_data_framework.contracts.temporal import require_aware_datetime, utc_now
from fabric_data_framework.metadata import config as metadata_config


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/fabric_data_framework"


def test_canonical_hash_has_one_cross_layer_owner_and_stable_behavior():
    assert canonical_hash({"b": 2, "a": "é"}) == canonical_hash({"a": "é", "b": 2})
    assert not hasattr(metadata_config, "canonical_hash")

    offenders = []
    for path in SRC.rglob("*.py"):
        if path.name == "hashing.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "def canonical_hash(" in text:
            offenders.append(path.relative_to(ROOT).as_posix())
        if "metadata.config import canonical_hash" in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_utc_clock_is_aware_and_local_utc_helpers_do_not_regrow():
    current = utc_now()
    assert current.tzinfo is not None
    assert current.utcoffset() is not None
    assert current.utcoffset().total_seconds() == 0

    with pytest.raises(ValueError, match="timezone-aware"):
        require_aware_datetime(datetime(2026, 1, 1), "observed_at")

    offenders = []
    for path in SRC.rglob("*.py"):
        if path.name == "temporal.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "def _utcnow(" in text or "datetime.now(timezone.utc)" in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []
