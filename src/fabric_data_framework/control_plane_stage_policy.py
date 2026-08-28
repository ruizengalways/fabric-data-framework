"""Stage-specific promotable control-plane definitions.

This module extends the unreleased control-plane v2 metadata with an additive table
rather than changing the existing capture execution-policy table in place.
"""

from sqlalchemy import Column, DateTime, ForeignKey, String, Table

from .control_plane import dataset, metadata


apply_execution_policy = Table(
    "apply_execution_policy",
    metadata,
    Column(
        "dataset_id",
        String(255),
        ForeignKey(dataset.c.dataset_id),
        primary_key=True,
    ),
    Column("execution_engine", String(64), nullable=False),
    Column("capability_profile", String(255), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=True),
)


__all__ = ["apply_execution_policy"]
