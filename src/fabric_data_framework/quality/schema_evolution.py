"""Deterministic provider-neutral schema-evolution classification."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from ..config import FrozenModel
from ..schema_contract import (
    LogicalType,
    SchemaCompatibilityPolicy,
    SchemaContract,
    SchemaField,
    SchemaShape,
)


class SchemaEvolutionClassification(str, Enum):
    NO_CHANGE = "NO_CHANGE"
    COMPATIBLE = "COMPATIBLE"
    BREAKING = "BREAKING"


class SchemaChangeKind(str, Enum):
    FIELD_ADDED = "FIELD_ADDED"
    FIELD_REMOVED = "FIELD_REMOVED"
    TYPE_WIDENED = "TYPE_WIDENED"
    TYPE_CHANGED = "TYPE_CHANGED"
    NULLABILITY_RELAXED = "NULLABILITY_RELAXED"
    NULLABILITY_TIGHTENED = "NULLABILITY_TIGHTENED"


class SchemaFieldChange(FrozenModel):
    field_name: str = Field(min_length=1)
    kind: SchemaChangeKind
    intrinsically_safe: bool
    detail: str = Field(min_length=1)


class SchemaEvolutionDecision(FrozenModel):
    classification: SchemaEvolutionClassification
    policy: SchemaCompatibilityPolicy
    expected_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    changes: tuple[SchemaFieldChange, ...] = ()

    @property
    def compatible(self) -> bool:
        return self.classification is not SchemaEvolutionClassification.BREAKING


def _safe_type_transition(expected: SchemaField, observed: SchemaField) -> tuple[bool, str]:
    if expected.logical_type is not observed.logical_type:
        if (expected.logical_type, observed.logical_type) in {
            (LogicalType.INT32, LogicalType.INT64),
            (LogicalType.FLOAT32, LogicalType.FLOAT64),
        }:
            return True, f"{expected.logical_type.value}->{observed.logical_type.value}"
        return False, f"{expected.logical_type.value}->{observed.logical_type.value}"

    if expected.logical_type is LogicalType.STRING:
        before = expected.max_length
        after = observed.max_length
        if before == after:
            return True, "unchanged"
        if before is not None and (after is None or after >= before):
            return True, f"max_length {before}->{after if after is not None else 'unbounded'}"
        return False, f"max_length {before}->{after}"

    if expected.logical_type is LogicalType.DECIMAL:
        assert expected.precision is not None and expected.scale is not None
        assert observed.precision is not None and observed.scale is not None
        if expected.precision == observed.precision and expected.scale == observed.scale:
            return True, "unchanged"
        if observed.scale == expected.scale and observed.precision >= expected.precision:
            return True, (
                f"DECIMAL({expected.precision},{expected.scale})->"
                f"DECIMAL({observed.precision},{observed.scale})"
            )
        return False, (
            f"DECIMAL({expected.precision},{expected.scale})->"
            f"DECIMAL({observed.precision},{observed.scale})"
        )

    return True, "unchanged"


def _raw_changes(expected: SchemaContract, observed: SchemaShape) -> tuple[SchemaFieldChange, ...]:
    expected_by_name = {field.name: field for field in expected.fields}
    observed_by_name = {field.name: field for field in observed.fields}
    changes: list[SchemaFieldChange] = []

    for name in sorted(expected_by_name.keys() - observed_by_name.keys()):
        changes.append(
            SchemaFieldChange(
                field_name=name,
                kind=SchemaChangeKind.FIELD_REMOVED,
                intrinsically_safe=False,
                detail="expected field is missing from observed schema",
            )
        )

    for name in sorted(observed_by_name.keys() - expected_by_name.keys()):
        field = observed_by_name[name]
        changes.append(
            SchemaFieldChange(
                field_name=name,
                kind=SchemaChangeKind.FIELD_ADDED,
                intrinsically_safe=field.nullable,
                detail=(
                    "new nullable field"
                    if field.nullable
                    else "new required field cannot be backfilled safely"
                ),
            )
        )

    for name in sorted(expected_by_name.keys() & observed_by_name.keys()):
        before = expected_by_name[name]
        after = observed_by_name[name]
        type_safe, type_detail = _safe_type_transition(before, after)
        type_changed = (
            before.logical_type is not after.logical_type
            or before.precision != after.precision
            or before.scale != after.scale
            or before.max_length != after.max_length
        )
        if type_changed:
            changes.append(
                SchemaFieldChange(
                    field_name=name,
                    kind=(
                        SchemaChangeKind.TYPE_WIDENED
                        if type_safe
                        else SchemaChangeKind.TYPE_CHANGED
                    ),
                    intrinsically_safe=type_safe,
                    detail=type_detail,
                )
            )

        if before.nullable != after.nullable:
            relaxed = not before.nullable and after.nullable
            changes.append(
                SchemaFieldChange(
                    field_name=name,
                    kind=(
                        SchemaChangeKind.NULLABILITY_RELAXED
                        if relaxed
                        else SchemaChangeKind.NULLABILITY_TIGHTENED
                    ),
                    intrinsically_safe=relaxed,
                    detail=(
                        "required->nullable"
                        if relaxed
                        else "nullable->required"
                    ),
                )
            )

    return tuple(changes)


def _policy_allows(change: SchemaFieldChange, policy: SchemaCompatibilityPolicy) -> bool:
    if policy is SchemaCompatibilityPolicy.EXACT:
        return False
    if policy is SchemaCompatibilityPolicy.ADDITIVE_ONLY:
        return change.kind is SchemaChangeKind.FIELD_ADDED and change.intrinsically_safe
    if policy is SchemaCompatibilityPolicy.SAFE_EVOLUTION:
        return change.intrinsically_safe and change.kind in {
            SchemaChangeKind.FIELD_ADDED,
            SchemaChangeKind.TYPE_WIDENED,
            SchemaChangeKind.NULLABILITY_RELAXED,
        }
    raise ValueError(f"unsupported schema compatibility policy: {policy}")


def classify_schema_evolution(
    expected: SchemaContract,
    observed: SchemaShape,
) -> SchemaEvolutionDecision:
    """Classify an observed schema against the source-controlled contract.

    Rules are intentionally conservative. Cross-family casts, removals, required
    additions, narrowing and nullability tightening are breaking. SAFE_EVOLUTION
    additionally permits only explicitly listed widening transitions.
    """

    changes = _raw_changes(expected, observed)
    if not changes:
        classification = SchemaEvolutionClassification.NO_CHANGE
    elif all(_policy_allows(change, expected.compatibility_policy) for change in changes):
        classification = SchemaEvolutionClassification.COMPATIBLE
    else:
        classification = SchemaEvolutionClassification.BREAKING

    return SchemaEvolutionDecision(
        classification=classification,
        policy=expected.compatibility_policy,
        expected_fingerprint=expected.fingerprint,
        observed_fingerprint=observed.fingerprint,
        changes=changes,
    )


def require_compatible_schema(
    expected: SchemaContract,
    observed: SchemaShape,
) -> SchemaEvolutionDecision:
    decision = classify_schema_evolution(expected, observed)
    if not decision.compatible:
        reasons = "; ".join(
            f"{change.field_name}:{change.kind.value}:{change.detail}"
            for change in decision.changes
            if not _policy_allows(change, expected.compatibility_policy)
        )
        raise ValueError(
            f"observed schema is incompatible under {expected.compatibility_policy.value}: "
            f"{reasons}"
        )
    return decision


__all__ = [
    "SchemaChangeKind",
    "SchemaEvolutionClassification",
    "SchemaEvolutionDecision",
    "SchemaFieldChange",
    "classify_schema_evolution",
    "require_compatible_schema",
]
