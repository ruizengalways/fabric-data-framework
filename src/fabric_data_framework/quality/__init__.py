"""Data-quality, reconciliation, schema and temporal correctness primitives."""

from .append import reconcile_append
from .full_refresh import reconcile_full_replace
from .rules import QuarantinedRecord, RowRule, ValidationOutcome, validate_records
from .schema_evolution import (
    SchemaChangeKind,
    SchemaEvolutionClassification,
    SchemaEvolutionDecision,
    SchemaFieldChange,
    classify_schema_evolution,
    require_compatible_schema,
)
from .snapshot_diff import reconcile_snapshot_diff
from .temporal import (
    EventTimeRelation,
    SourceOrderRelation,
    TemporalAssessment,
    TemporalCondition,
    TemporalOrderingError,
    assess_temporal,
    compare_event_time,
    compare_source_order,
)

__all__ = [
    "EventTimeRelation",
    "QuarantinedRecord",
    "RowRule",
    "SchemaChangeKind",
    "SchemaEvolutionClassification",
    "SchemaEvolutionDecision",
    "SchemaFieldChange",
    "SourceOrderRelation",
    "TemporalAssessment",
    "TemporalCondition",
    "TemporalOrderingError",
    "ValidationOutcome",
    "assess_temporal",
    "classify_schema_evolution",
    "compare_event_time",
    "compare_source_order",
    "reconcile_append",
    "reconcile_full_replace",
    "reconcile_snapshot_diff",
    "require_compatible_schema",
    "validate_records",
]
