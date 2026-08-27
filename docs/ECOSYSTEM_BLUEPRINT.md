# Enterprise Microsoft Fabric Data Engineering Platform — Ecosystem Blueprint

Status: Canonical
Last updated: 2026-08-28

## 1. Purpose

This document is the highest-level canonical architecture record for the three-repository Enterprise Microsoft Fabric Data Engineering Platform reference implementation. It is designed to demonstrate production-grade Senior/Principal Data Engineer and Data Platform Engineer concerns rather than BI/dashboard implementation.

GitHub documentation is the durable project memory. New conversations and contributors must recover state from these repositories before making changes.

## 2. Repository model and ownership

### `fabric-infra`
Owner: Infrastructure Platform Engineering.

Owns the infrastructure plane: Azure subscription/resource-group concerns, Fabric capacity, Domains, Workspaces, workspace RBAC, Entra/service identities, networking, Private Link, Trusted Workspace Access, managed private endpoints, key-management integration where appropriate, capacity sizing, pause/resume, cost controls, provisioning and teardown.

It does not own business transformations or reusable data-processing behaviour.

### `fabric-data-framework`
Owner: Data Platform Engineering / Reusable Data Engineering Runtime.

Owns reusable runtime behaviour: metadata/configuration contracts, FULL and WATERMARK capture, CDC normalization, snapshot diff, APPEND/REPLACE/UPSERT/SCD1/SCD2 apply behaviour, schema contracts/evolution policies, DQ/reconciliation primitives, idempotency, retry/rerun/backfill/replay, late-arriving and delete handling, runtime state, operational logging/observability hooks, control-plane schemas/migrations, testing utilities, and generic Fabric deployment/runtime helpers.

It publishes a versioned reusable Python package. It must not contain Customer-specific business logic.

### `fabric-customer`
Owner: Domain Data Engineering.

Owns the reference Customer domain: source configuration, Bronze contracts, Customer mappings and transformations, canonical Customer modelling, domain-specific DQ/reconciliation rules, Fabric item definitions that are domain-owned, fixtures, integration tests and smoke tests.

It consumes the framework; it does not reimplement generic SCD2, watermark, snapshot-diff or reconciliation engines.

## 3. Dependency direction

```text
fabric-infra
      |
      | provisions / exposes environment contract
      v
Fabric estate

fabric-data-framework
      |
      | publishes immutable/versioned reusable package
      v
fabric-customer
```

Forbidden dependencies:

- `fabric-data-framework` depending on `fabric-customer`.
- `fabric-infra` importing domain business logic.
- domain repositories copying generic framework algorithms.

Core principle: **share code, not runtime**. Each domain executes an isolated runtime while consuming the same versioned framework implementation.

## 4. Infrastructure abstraction contract

Framework and domain code must not hard-code workspace IDs, Lakehouse/Warehouse IDs, company-specific workspace names, or DEV/UAT/PROD physical naming.

A logical environment contract resolves those resources, conceptually:

```yaml
environment: dev
domain: customer
fabric:
  workspaces:
    bronze: <logical-resolution>
    silver: <logical-resolution>
    gold: <logical-resolution>
  lakehouses:
    bronze: <logical-resolution>
    silver: <logical-resolution>
  warehouses:
    gold: <logical-resolution>
```

The source of these values is deliberately abstract. Initially it may be enterprise-provided/manual configuration; later it may be Terraform outputs from `fabric-infra`. The framework contract must not change when the provider changes.

## 5. Logical Fabric architecture

The target is domain-oriented:

```text
Fabric Tenant
  +-- Platform capabilities
  +-- Customer Domain
  +-- Finance Domain
  +-- Workforce Domain
  +-- ...
```

Datasource count does not define workspace count. Workspace boundaries are driven by security, ownership, governance, deployment lifecycle, blast radius and SLOs.

A reference logical topology may use Domain × Environment × Medallion Layer, but physical workspace mapping is environment-specific and remains decoupled from framework behaviour.

## 6. Data architecture and ownership boundary

```text
Source Systems
      |
      v
Ingestion
      |
      v
BRONZE — source-faithful + normalized framework metadata
      |
      v
SILVER — validated / standardized / canonical / SCD
      |
      v
GOLD — curated / publishable data products
      |
      v
Data Engineering ownership ends
```

Power BI dashboards, DAX, semantic-model UX and BI visualization are out of scope.

## 7. Capture strategy and apply strategy

Capture describes how changes are acquired:

`FULL`, `WATERMARK`, `CDC`, `MIRROR`, `STREAM`, `SNAPSHOT`.

Apply describes how normalized changes are materialized:

`APPEND`, `REPLACE`, `UPSERT`, `SCD1`, `SCD2`, `SNAPSHOT_DIFF`.

They are independent axes. Examples include WATERMARK → SCD2, CDC → UPSERT, FULL/SNAPSHOT → SNAPSHOT_DIFF → SCD2, FULL → REPLACE and STREAM → APPEND. CDC is not synonymous with SCD2.

## 8. Bronze framework contract

Downstream framework logic consumes normalized Bronze metadata rather than provider-specific envelopes. The stable contract will evolve around fields such as:

```text
_framework_ingested_at
_framework_run_id
_framework_source_system
_framework_source_object
_framework_operation
_framework_source_commit_ts
_framework_source_sequence
_framework_snapshot_id
_framework_schema_version
```

Not every ingestion provider must populate every field.

## 9. Runtime and control plane

Git is configuration/source control; it is not runtime state.

The framework owns control-plane schema definitions and migrations. The physical Warehouse/Lakehouse shell may be supplied by pre-provisioned enterprise infrastructure or later by `fabric-infra`.

The control-plane model will progressively cover:

```text
dataset
dataset_contract
load_policy
watermark
dataset_state
pipeline_run
dataset_run
reconciliation_result
schema_change
reprocess_request
deployment_history
```

Watermark advancement occurs only after successful commit. Composite `(timestamp, tie_breaker)` watermarks or an overlap-window plus idempotent merge must be supported; timestamp-only correctness is insufficient.

## 10. Runtime correctness principles

SCD2 and other stateful strategies must be designed around explicit invariants, including one current record per business key, idempotent rerun, no new version for unchanged tracked attributes, correct close/open behaviour for changes, and explicit delete/late/out-of-order policies.

Recovery modes are first-class concepts:

`NORMAL`, `RETRY`, `BACKFILL`, `REPLAY`, `FULL_REBUILD`.

Code rollback, deployment rollback and data recovery are distinct operations.

## 11. CI/CD and release model

Use trunk-based development:

```text
feature branch -> PR -> CI -> merge -> immutable Git SHA -> DEV -> UAT -> PROD
```

The same commit is promoted through environments; environments must not independently deploy whatever `main` happens to contain at deployment time.

`fabric-data-framework` uses semantic versioning and publishes immutable package versions. Domain repositories pin an exact version such as `fabric-data-framework==1.4.2`. Framework upgrades happen through explicit domain PRs and CI.

Reusable GitHub workflows, when introduced, are version-pinned rather than consumed from `@main`.

Deployment provenance must answer which exact domain Git SHA and framework version are running in an environment.

## 12. Fabric deployment boundary

Infrastructure lifecycle and Fabric application/item lifecycle are separate planes.

- Infrastructure plane: future Terraform in `fabric-infra` for capacities, Domains, Workspaces, RBAC and related estate resources.
- Application/data-platform plane: Git plus an explicitly selected Fabric deployment mechanism for notebooks, pipelines, Lakehouses/Warehouses where application-owned, and environment variables/configuration.

One object must have one authoritative management mechanism; overlapping Terraform/script/manual ownership is prohibited.

## 13. Security boundary

Infrastructure owns tenant/subscription/capacity/workspace/network/RBAC/identity primitives. Framework and domain code consume granted identities and resolved resource contracts; they do not silently redesign enterprise RBAC, networking or tenant settings.

In the initial company-Fabric phase, no changes to capacity, tenant settings, private networking, RBAC architecture or production workspace configuration are made without explicit authorization.

## 14. Testing strategy

Testing remains lightweight but correctness-focused:

- unit tests for reusable algorithms and config validation;
- contract tests for schemas and infrastructure/configuration boundaries;
- integration tests for representative end-to-end behaviour;
- reconciliation tests for source/target correctness;
- smoke tests for deployed Fabric execution.

High-value invariants include watermark advancement, SCD2 correctness, idempotent rerun, snapshot diff, delete handling, schema compatibility, reconciliation and backfill/replay behaviour. Test datasets remain small.

## 15. Representative scenarios

The reference implementation proves reusable behaviour with a small number of representative datasets rather than dozens of bespoke pipelines:

1. CRM Customer: WATERMARK with `(modified_at, customer_id)` tie-breaker -> Bronze -> SCD2.
2. Legacy master: FULL SNAPSHOT -> snapshot diff -> I/U/D -> SCD2.
3. CDC-style transaction stream: normalize CDC -> Bronze -> dedupe -> UPSERT/APPEND.
4. Lightweight Fabric-native streaming vertical slice, secondary to batch/incremental runtime.

## 16. Cost philosophy

Use tiny synthetic data, short Spark execution and low-throughput streaming. Future personal-lab infrastructure should support explicit `make resume`, `make pause`, `make status`, `make destroy`, with manual resume and an automatic pause safety net. No automatic daily resume.

## 17. Current infrastructure mode

Initial infrastructure implementation is intentionally deferred. The first working target is:

```text
Existing Company Fabric Estate
        -> Infrastructure Contract
        -> fabric-data-framework
        -> fabric-customer
```

Future target:

```text
fabric-infra / Terraform outputs
        -> same Infrastructure Contract
        -> fabric-data-framework
        -> fabric-customer
```

This transition must not require architectural refactoring of framework/domain runtime code.

## 18. Implementation roadmap

- Phase 0 — canonical architecture, ownership boundaries, environment contract, ADRs, status docs and minimal repository skeletons.
- Phase 1 — framework package foundation: typed configuration, runtime interfaces, logging model, test infrastructure and control-plane schema design.
- Phase 2 — thin Customer WATERMARK -> Bronze -> SCD2 -> Silver vertical slice.
- Phase 3 — delivery spine: PR CI, framework package release, exact dependency pin, Fabric item deployment, same-SHA promotion and deployment history.
- Phase 4 — complete reusable capture/apply strategies.
- Phase 5 — enterprise runtime hardening: schema evolution, DQ, reconciliation, retry, idempotency, recovery, observability.
- Phase 6 — lightweight streaming vertical slice.
- Phase 7 — Terraform-based `fabric-infra` implementation with cost controls and reproducible lifecycle.

## 19. Conversation recovery protocol

At the start of every new implementation conversation:

1. inspect all three repositories;
2. read this file;
3. read `fabric-data-framework/docs/CURRENT_STATUS.md`, `fabric-customer/docs/CURRENT_STATUS.md`, and `fabric-infra/docs/CURRENT_STATUS.md`;
4. read relevant project blueprints and ADRs;
5. inspect code relevant to the documented exact next step;
6. if docs and code disagree, inspect code, repair docs, then continue;
7. do not redesign accepted ADRs without a concrete technical reason.

Documentation is part of Definition of Done. A meaningful implementation step is not complete until status and architecture documentation are synchronized.
