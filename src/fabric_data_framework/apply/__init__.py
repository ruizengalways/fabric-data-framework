"""Apply-strategy implementations and publication guards."""

from .replace import (
    InMemoryReplaceTarget,
    ReplaceGuardError,
    ReplaceGuardPolicy,
    ReplacePlan,
    plan_replace,
)
from .scd1 import (
    InMemorySCD1Target,
    SCD1ApplyPolicy,
    SCD1ApplyResult,
    SCD1ConflictError,
    SCD1OrderingError,
    StaleRecordAction,
    apply_scd1,
)
from .snapshot_diff import (
    SnapshotDiffError,
    SnapshotDiffPlan,
    SnapshotDiffPolicy,
    plan_snapshot_diff,
)

__all__ = [
    "InMemoryReplaceTarget",
    "InMemorySCD1Target",
    "ReplaceGuardError",
    "ReplaceGuardPolicy",
    "ReplacePlan",
    "SCD1ApplyPolicy",
    "SCD1ApplyResult",
    "SCD1ConflictError",
    "SCD1OrderingError",
    "SnapshotDiffError",
    "SnapshotDiffPlan",
    "SnapshotDiffPolicy",
    "StaleRecordAction",
    "apply_scd1",
    "plan_replace",
    "plan_snapshot_diff",
]
