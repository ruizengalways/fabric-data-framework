"""Data-quality, quarantine, reconciliation and schema-evolution primitives."""

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

__all__ = [
    "QuarantinedRecord",
    "RowRule",
    "SchemaChangeKind",
    "SchemaEvolutionClassification",
    "SchemaEvolutionDecision",
    "SchemaFieldChange",
    "ValidationOutcome",
    "classify_schema_evolution",
    "reconcile_append",
    "reconcile_full_replace",
    "reconcile_snapshot_diff",
    "require_compatible_schema",
    "validate_records",
]
