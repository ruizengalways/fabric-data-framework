# ADR 0002 — Separate capture strategy from apply strategy

Status: Accepted
Date: 2026-08-28

## Context

Source change acquisition and target state materialization solve different problems. Treating CDC as equivalent to SCD2, or watermark ingestion as equivalent to UPSERT, would couple source mechanics to target semantics and reduce reuse.

## Decision

Model two independent configuration axes.

Capture strategies include: `FULL`, `WATERMARK`, `CDC`, `MIRROR`, `STREAM`, `SNAPSHOT`.

Apply strategies include: `APPEND`, `REPLACE`, `UPSERT`, `SCD1`, `SCD2`, `SNAPSHOT_DIFF`.

Valid compositions are chosen per dataset, for example WATERMARK -> SCD2, CDC -> UPSERT, or FULL/SNAPSHOT -> SNAPSHOT_DIFF -> SCD2.

Provider-specific events are normalized into a stable Bronze framework contract before downstream apply logic.

## Consequences

- Capture providers and target strategies can evolve independently.
- Domain configuration is expressive without provider-specific algorithm duplication.
- Validation must reject unsupported combinations while preserving the conceptual separation.
