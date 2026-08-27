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

Owns reusable runtime behaviour: metadata/configuration contracts, metadata-driven orchestration, FULL and WATERMARK capture, CDC normalization, snapshot diff, APPEND/REPLACE/UPSERT/SCD1/SCD2 apply behaviour, schema contracts/evolution policies, DQ/reconciliation primitives, quarantine contracts, idempotency, retry/rerun/backfill/replay, late-arriving and delete handling, runtime state, operational logging/audit/observability hooks, control-plane schemas/migrations, testing utilities, and generic Fabric deployment/runtime helpers.

It publishes a versioned reusable Python package. It must not contain Customer-specific business logic.

### `fabric-customer`
Owner: Domain Data Engineering.

Owns the reference Customer domain: source configuration, source-controlled dataset metadata, Bronze contracts, Customer mappings and transformations, canonical Customer modelling, domain-specific DQ/reconciliation rules, Fabric item definitions that are domain-owned, fixtures, integration tests and smoke tests.

It consumes the framework; it does not reimplement generic SCD2, watermark, snapshot-diff, quarantine, orchestration or reconciliation engines.

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
    control: <logical-resolution>
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

## 7. Metadata-driven operating model

The production runtime is metadata-driven for stable, repeatable behaviour. A domain should not hand-author one bespoke pipeline per table.

For a domain with tens of tables, source-controlled metadata declares per-dataset semantics such as:

```yaml
dataset: crm.customer
source_object: dbo.Customer
target_object: silver.customer
capture_strategy: WATERMARK
apply_strategy: SCD2
business_key: [customer_id]
merge_key: [customer_id]
watermark:
  column: modified_at
  tie_breaker: [customer_id]
event_time_column: modified_at
criticality: HIGH
execution_group: crm_daily
reconciliation_policy: standard_count_and_key
quarantine_policy: reject_bad_rows
```

The framework deploys/reads this metadata through the control plane and executes generic behaviour from it.

### 7.1 Configuration hierarchy

Configuration has three distinct layers:

1. **Source-controlled semantic configuration** — canonical in Git. This owns dataset identity, source/target contract, capture/apply strategy, business/merge keys, watermark/event-time columns, schema contract, delete semantics, DQ/reconciliation policy and dependency declarations.
2. **Deployed metadata snapshot** — the immutable/effectively immutable representation of a released domain configuration in the runtime control plane. It records config version/hash, domain Git SHA and framework version.
3. **Audited runtime operational overrides** — time-bounded operational controls such as enable/disable, priority, retry limit, timeout, bounded parallelism, batch size and overlap window.

Runtime overrides must not silently mutate business semantics in PROD. Changing merge keys, apply strategy, schema contract or other semantic behaviour requires a source-controlled change and deployment unless an explicit emergency procedure is later designed and audited.

This preserves the rule:

```text
Git configuration/source of truth != runtime state/operational override
```

while still allowing production operators to tune or suspend individual datasets without code changes.

## 8. Capture strategy and apply strategy

Capture describes how changes are acquired:

`FULL`, `WATERMARK`, `CDC`, `MIRROR`, `STREAM`, `SNAPSHOT`.

Apply describes how normalized changes are materialized:

`APPEND`, `REPLACE`, `UPSERT`, `SCD1`, `SCD2`, `SNAPSHOT_DIFF`.

They are independent axes. Examples include WATERMARK -> SCD2, CDC -> UPSERT, FULL/SNAPSHOT -> SNAPSHOT_DIFF -> SCD2, FULL -> REPLACE and STREAM -> APPEND. CDC is not synonymous with SCD2.

## 9. Bronze framework contract

Downstream framework logic consumes normalized Bronze metadata rather than provider-specific envelopes. The stable contract will evolve around fields such as:

```text
_framework_ingested_at
_framework_run_id
_framework_dataset_run_id
_framework_source_system
_framework_source_object
_framework_operation
_framework_source_commit_ts
_framework_source_sequence
_framework_snapshot_id
_framework_schema_version
_framework_quarantine_reason
```

Not every ingestion provider must populate every field.

## 10. Metadata-driven pipeline orchestration

Fabric Pipelines are orchestration shells, not containers for duplicated table-specific business logic.

Reference runtime shape:

```text
Trigger / schedule / operator request
        |
        v
Create pipeline_run
        |
        v
Lookup/select active datasets from effective metadata
        |
        v
Filter by execution_group / dependency readiness / run mode
        |
        v
Bounded parallel dispatcher
        |
        +--> Dataset A executor --> audit outcome
        +--> Dataset B executor --> audit outcome
        +--> Dataset C executor --> audit outcome
        +--> ...
        |
        v
Aggregate dataset outcomes
        |
        v
SUCCESS / PARTIAL_SUCCESS / FAILED
```

The dispatcher passes a small contract such as `pipeline_run_id`, `dataset_id`, `environment`, `run_mode` and optional `reprocess_request_id`. The dataset executor resolves the remaining parameters from effective metadata.

### 10.1 Failure isolation

A dataset is the default failure boundary.

If one of forty datasets fails, unrelated datasets must continue where technically safe. A child failure is recorded in `dataset_run`; it must not automatically terminate all siblings.

At the end of the orchestration run, the framework calculates the aggregate pipeline outcome using policy such as:

- `SUCCESS` — all required datasets succeeded;
- `PARTIAL_SUCCESS` — one or more non-critical datasets failed/quarantined/skipped while required datasets succeeded;
- `FAILED` — critical datasets failed, policy thresholds were exceeded, or orchestration/control-plane integrity failed.

The pipeline may intentionally emit a final Fabric failure only after independent eligible datasets have finished, so operational alerting remains truthful without sacrificing fault isolation.

### 10.2 Dependency-aware execution

If explicit dataset dependencies exist, a failed prerequisite marks only dependent datasets as `BLOCKED`/`SKIPPED_DEPENDENCY`; unrelated branches continue.

The framework should support execution groups/stages before attempting a fully generic arbitrary DAG engine. Avoid unnecessary orchestration magic.

### 10.3 Concurrency controls

Parallelism is bounded and configurable by environment/execution group/source system. The framework must avoid overwhelming source systems or Fabric capacity. Runtime control may reduce concurrency without changing code.

Current Fabric limits and exact Pipeline activity behaviour must be re-verified against Microsoft Learn when the Fabric orchestration implementation is built; limits are not embedded as timeless architecture constants.

## 11. Runtime and control plane

The framework owns control-plane schema definitions and migrations. The physical Warehouse/Lakehouse shell may be supplied by pre-provisioned enterprise infrastructure or later by `fabric-infra`.

The control-plane model progressively covers:

### Configuration/deployed metadata

```text
dataset
dataset_contract
load_policy
orchestration_policy
data_quality_policy
reconciliation_policy
runtime_override
```

### Runtime state

```text
watermark
dataset_state
dataset_lease
pipeline_run
dataset_run
step_run
reconciliation_result
quarantine_batch
schema_change
reprocess_request
deployment_history
```

A detailed design is maintained in `docs/CONTROL_PLANE_DESIGN.md`.

Watermark advancement occurs only after successful target commit and required reconciliation. Composite `(timestamp, tie_breaker)` watermarks or an overlap-window plus idempotent merge must be supported; timestamp-only correctness is insufficient.

A dataset lease/optimistic concurrency mechanism prevents overlapping runs of the same stateful dataset from corrupting watermark or target state.

## 12. Audit and observability

Every production run must be explainable at pipeline, dataset and significant-step level.

Audit records should capture, where applicable:

- pipeline/dataset/step run IDs and parent correlation IDs;
- Fabric pipeline/activity/notebook run identifiers;
- environment, domain, dataset and attempt;
- run mode (`NORMAL`, `RETRY`, `BACKFILL`, `REPLAY`, `FULL_REBUILD`);
- domain Git SHA, deployed metadata/config hash and framework version;
- start/end/duration/status;
- source/target row counts;
- rows inserted/updated/deleted/rejected/quarantined;
- watermark/state before and after;
- reconciliation results;
- schema version/change information;
- error category/code/message and retryability classification.

Audit data must support both operations and data-recovery decisions. Logging text alone is not sufficient operational state.

## 13. Quarantine and bad-data handling

Quarantine is first-class and distinct from infrastructure/system failure.

### Row-level quarantine

Rows failing explicitly quarantinable schema/DQ rules can be redirected to a quarantine data location with lineage metadata, rule/reason, source identity, original run IDs and replay status.

### Batch-level quarantine

Severe contract violations may quarantine or reject an entire dataset batch. In this case target state and watermark must not advance.

### System failures

Connection failures, permission errors, unavailable sinks, code defects and similar system failures are dataset failures, not "bad data" and must not be disguised as quarantine.

### No silent loss

Production policy must reconcile rows read against rows accepted, intentionally filtered and quarantined/rejected. Skipped incompatible rows are never silently ignored.

Quarantine storage access, sensitive-data handling and retention follow enterprise security/governance controls. The framework owns lineage and replay contracts, not tenant/RBAC policy.

## 14. Runtime correctness and recovery

Stateful strategies are designed around explicit invariants, idempotent semantics and atomic state advancement.

Recovery modes are first-class:

`NORMAL`, `RETRY`, `BACKFILL`, `REPLAY`, `FULL_REBUILD`.

Code rollback, deployment rollback and data recovery are distinct operations.

A failed batch must not advance watermark/state. A successful data write whose audit/state commit is uncertain must be recoverable through idempotency/reconciliation rather than blind duplicate execution.

## 15. Reconciliation and completion gates

Reconciliation is part of successful completion for stateful/critical loads, not an optional dashboard metric.

Policies may include source-vs-target row counts, key counts, control totals, hash comparisons, accepted/quarantined balance and expected delete counts.

The effective policy determines whether reconciliation differences:

- warn only;
- quarantine the batch;
- fail the dataset;
- block watermark/state advancement.

## 16. CI/CD and release model

Use trunk-based development:

```text
feature branch -> PR -> CI -> merge -> immutable Git SHA -> DEV -> UAT -> PROD
```

The same commit is promoted through environments; environments must not independently deploy whatever `main` happens to contain at deployment time.

`fabric-data-framework` uses semantic versioning and publishes immutable package versions. Domain repositories pin an exact version such as `fabric-data-framework==1.4.2`. Framework upgrades happen through explicit domain PRs and CI.

Reusable GitHub workflows, when introduced, are version-pinned rather than consumed from `@main`.

Deployment provenance must answer which exact domain Git SHA, config hash and framework version are running in an environment.

## 17. Fabric deployment boundary

Infrastructure lifecycle and Fabric application/item lifecycle are separate planes.

- Infrastructure plane: future Terraform in `fabric-infra` for capacities, Domains, Workspaces, RBAC and related estate resources.
- Application/data-platform plane: Git plus an explicitly selected Fabric deployment mechanism for notebooks, pipelines, Lakehouses/Warehouses where application-owned, and environment variables/configuration.

One object must have one authoritative management mechanism; overlapping Terraform/script/manual ownership is prohibited.

## 18. Security boundary

Infrastructure owns tenant/subscription/capacity/workspace/network/RBAC/identity primitives. Framework and domain code consume granted identities and resolved resource contracts; they do not silently redesign enterprise RBAC, networking or tenant settings.

In the initial company-Fabric phase, no changes to capacity, tenant settings, private networking, RBAC architecture or production workspace configuration are made without explicit authorization.

Operational override and quarantine access must be least-privilege and auditable; detailed identity/RBAC implementation remains an infrastructure/governance concern.

## 19. Testing strategy

Testing remains lightweight but correctness-focused:

- unit tests for reusable algorithms, metadata validation and effective-config resolution;
- contract tests for schemas, control-plane contracts and infrastructure/configuration boundaries;
- orchestration tests for independent dataset failure, partial success, dependency blocking and bounded concurrency decisions;
- integration tests for representative end-to-end behaviour;
- quarantine tests for row/batch handling and replay lineage;
- reconciliation tests for source/target correctness;
- smoke tests for deployed Fabric execution.

High-value invariants include watermark advancement, SCD2 correctness, idempotent rerun, snapshot diff, delete handling, schema compatibility, reconciliation, failure isolation, quarantine accounting and backfill/replay behaviour. Test datasets remain small.

## 20. Representative scenarios

The reference implementation proves reusable behaviour with a small number of representative datasets rather than dozens of bespoke pipelines:

1. CRM Customer: WATERMARK with `(modified_at, customer_id)` tie-breaker -> Bronze -> SCD2.
2. Legacy master: FULL SNAPSHOT -> snapshot diff -> I/U/D -> SCD2.
3. CDC-style transaction stream: normalize CDC -> Bronze -> dedupe -> UPSERT/APPEND.
4. Multi-dataset dispatcher test: several tiny datasets with one intentional non-critical failure, proving siblings continue and the parent becomes `PARTIAL_SUCCESS`.
5. Quarantine test: invalid row(s) quarantined with reconciliation/audit lineage and replay path.
6. Lightweight Fabric-native streaming vertical slice, secondary to batch/incremental runtime.

## 21. Cost philosophy

Use tiny synthetic data, short Spark execution and low-throughput streaming. Future personal-lab infrastructure should support explicit `make resume`, `make pause`, `make status`, `make destroy`, with manual resume and an automatic pause safety net. No automatic daily resume.

## 22. Current infrastructure mode

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

## 23. Implementation roadmap

- Phase 0 — canonical architecture, ownership boundaries, environment contract, ADRs, status docs and minimal repository skeletons.
- Phase 1 — framework foundation delivered in coherent slices: package structure, typed metadata/configuration, runtime contracts, effective-config layering, audit/control-plane models, quarantine/reconciliation contracts, logging and test infrastructure.
- Phase 2 — thin Customer WATERMARK -> Bronze -> SCD2 -> Silver vertical slice using deployed metadata and per-dataset audit/state.
- Phase 3 — delivery spine: PR CI, framework package release, exact dependency pin, Fabric item deployment, same-SHA promotion and deployment history.
- Phase 4 — complete reusable capture/apply strategies plus metadata-driven multi-dataset dispatcher/failure isolation.
- Phase 5 — enterprise runtime hardening: schema evolution, DQ, quarantine, reconciliation, retry, idempotency, recovery, observability and operational overrides.
- Phase 6 — lightweight streaming vertical slice.
- Phase 7 — Terraform-based `fabric-infra` implementation with cost controls and reproducible lifecycle.

The roadmap is incremental, but implementation work should be grouped into coherent, testable capabilities rather than stopping after every tiny class or file. Architecture review is required for meaningful design changes, not as a mandatory pause after every small implementation action.

## 24. Conversation recovery protocol

At the start of every new implementation conversation:

1. inspect all three repositories;
2. read this file;
3. read `fabric-data-framework/docs/CURRENT_STATUS.md`, `fabric-customer/docs/CURRENT_STATUS.md`, and `fabric-infra/docs/CURRENT_STATUS.md`;
4. read relevant project blueprints and ADRs;
5. inspect code relevant to the documented exact next step;
6. if docs and code disagree, inspect code, repair docs, then continue;
7. do not redesign accepted ADRs without a concrete technical reason.

Documentation is part of Definition of Done. A meaningful implementation step is not complete until status and architecture documentation are synchronized.
