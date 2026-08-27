# ADR 0003 — Control-plane ownership

Status: Accepted
Date: 2026-08-28

## Context

The platform needs durable runtime state such as watermarks, run history, schema-change records, reconciliation outcomes and reprocessing requests. Git configuration cannot represent mutable runtime state. At the same time, provisioning the physical Warehouse/Lakehouse shell is an infrastructure lifecycle concern.

## Decision

`fabric-data-framework` owns control-plane schema definitions, migrations and runtime semantics. `fabric-infra` or an existing enterprise estate supplies the physical storage shell and access through the infrastructure contract.

Planned framework-owned entities include dataset, dataset contract, load policy, watermark, dataset state, pipeline/dataset runs, reconciliation result, schema change, reprocess request and deployment history.

Runtime state is never treated as Git configuration.

## Consequences

- Runtime semantics remain reusable regardless of how infrastructure is provisioned.
- Infrastructure can be deferred initially without losing a clear control-plane boundary.
- Schema/migration compatibility becomes part of framework release discipline.
