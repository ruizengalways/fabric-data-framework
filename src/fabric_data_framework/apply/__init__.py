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
from .upsert import (
    InMemoryUpsertTarget,
    UpsertApplyPolicy,
    UpsertApplyResult,
    UpsertConflictError,
    UpsertOrderingError,
    apply_upsert,
)

__all__ = [
    "InMemoryReplaceTarget",
    "InMemorySCD1Target",
    "InMemoryUpsertTarget",
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
    "UpsertApplyPolicy",
    "UpsertApplyResult",
    "UpsertConflictError",
    "UpsertOrderingError",
    "apply_scd1",
    "apply_upsert",
    "plan_replace",
    "plan_snapshot_diff",
]
