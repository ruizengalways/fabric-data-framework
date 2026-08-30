"""Relational persistence for immutable schema-observation evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Engine, select

from .schema import apply_baseline_schema, schema_change
from ..quality.schema_evolution import SchemaEvolutionDecision


def record_schema_change(
    engine: Engine,
    *,
    dataset_id: str,
    decision: SchemaEvolutionDecision,
    dataset_run_id: UUID | None = None,
    schema_change_id: UUID | None = None,
    observed_at: datetime | None = None,
) -> UUID:
    """Append immutable schema classification evidence to the environment control plane."""

    apply_baseline_schema(engine)
    evidence_id = schema_change_id or uuid4()
    timestamp = observed_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")

    details = {
        "policy": decision.policy.value,
        "compatible": decision.compatible,
        "changes": [change.model_dump(mode="json") for change in decision.changes],
    }
    with engine.begin() as connection:
        existing = connection.execute(
            select(schema_change.c.schema_change_id).where(
                schema_change.c.schema_change_id == str(evidence_id)
            )
        ).first()
        if existing is not None:
            raise ValueError(f"schema change evidence {evidence_id} is already recorded")
        connection.execute(
            schema_change.insert().values(
                schema_change_id=str(evidence_id),
                dataset_id=dataset_id,
                dataset_run_id=str(dataset_run_id) if dataset_run_id is not None else None,
                observed_fingerprint=decision.observed_fingerprint,
                expected_fingerprint=decision.expected_fingerprint,
                classification=decision.classification.value,
                details=details,
                observed_at=timestamp,
            )
        )
    return evidence_id


__all__ = ["record_schema_change"]
