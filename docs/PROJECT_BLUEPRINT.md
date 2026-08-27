# fabric-data-framework — Project Blueprint

Status: Canonical
Last updated: 2026-08-28

## 1. Goal

Build a production-grade, reusable Microsoft Fabric data-engineering runtime package that domain repositories consume through explicit, immutable versions.

The framework standardizes stable cross-domain behaviour while leaving domain-specific transformations explicit in domain repositories.

## 2. Non-goals

- Customer-specific business logic or canonical Customer transformations.
- Power BI dashboards, DAX, semantic models or visualization UX.
- Owning Fabric capacity, workspace RBAC, network architecture or tenant settings.
- A giant metadata product that hides genuinely different business logic.
- A central cross-workspace runtime notebook called by every domain.
- Hand-authoring one generic-looking but still bespoke Fabric pipeline for every source table.

## 3. Design principles

1. Share versioned code, not a shared runtime.
2. Configuration-driven where behaviour is stable; explicit code where logic differs.
3. Metadata-driven execution is a first-class framework capability.
4. Capture strategy and apply strategy are separate concepts.
5. Git semantic configuration is distinct from runtime state and operational overrides.
6. Resource identities/names are resolved through an infrastructure contract.
7. Stateful behaviour is defined through invariants and idempotent semantics.
8. A dataset is the default execution/failure boundary; unrelated datasets continue where safe.
9. Quarantine, reconciliation and audit are part of execution semantics, not bolt-on monitoring.
10. Recovery is designed before operational scale.

## 4. Repository structure

Phase 0 contains canonical documentation. Phase 1 adds code incrementally, in coherent capability slices rather than tiny stop-and-review increments:

```text
fabric-data-framework/
  pyproject.toml
  src/fabric_data_framework/
    config/
    runtime/
    control_plane/
    audit/
    quality/
    infrastructure/
  tests/
  docs/
    ECOSYSTEM_BLUEPRINT.md
    PROJECT_BLUEPRINT.md
    CONTROL_PLANE_DESIGN.md
    CURRENT_STATUS.md
    adr/
    runbooks/
```

This is a target shape, not permission to create empty placeholder modules. Files are added only when the current coherent implementation slice needs them.

## 5. Package boundaries

The framework package will progressively expose:

- typed dataset metadata/configuration models and enums;
- effective-config resolution from deployed semantic metadata plus audited operational overrides;
- infrastructure/environment resolution contracts;
- immutable runtime context and run-mode contracts;
- control-plane repository/store interfaces and schema/migration definitions;
- pipeline/dataset/step audit contracts;
- quarantine and reconciliation policy/result contracts;
- capture/apply strategy interfaces and implementations;
- state/watermark/lease management;
- retry/reprocess/replay primitives;
- structured logging and observability hooks;
- test utilities for framework and domain repositories.

## 6. Metadata model

Stable metadata describes each dataset's execution semantics. Example:

```yaml
dataset: crm.customer
source:
  system: crm
  object: dbo.Customer
target:
  layer: silver
  object: customer
capture_strategy: WATERMARK
apply_strategy: SCD2
business_key:
  - customer_id
merge_key:
  - customer_id
watermark:
  column: modified_at
  tie_breaker:
    - customer_id
event_time_column: modified_at
tracked_columns:
  - name
  - address
  - segment
orchestration:
  execution_group: crm_daily
  criticality: HIGH
quality:
  policy: customer_standard
  quarantine_policy: reject_bad_rows
reconciliation:
  policy: standard_count_and_key
```

The configuration selects stable framework behaviour; it does not encode complex domain transformation logic.

### 6.1 Semantic metadata vs operational controls

Semantic metadata is canonical in Git and deployed as a versioned snapshot. Examples:

- dataset/source/target identity;
- capture/apply strategy;
- business and merge keys;
- watermark/event-time/tie-breaker semantics;
- schema contract;
- delete/late-arrival policy;
- DQ/reconciliation policy;
- dataset dependencies.

Operational runtime controls may be changed without a code deployment, but are audited and intentionally constrained. Examples:

- enabled/disabled;
- priority;
- execution group activation;
- retry limit/backoff profile;
- timeout;
- batch/chunk size;
- overlap window within approved bounds;
- bounded parallelism/concurrency profile.

A PROD runtime override must not silently change merge keys, capture/apply semantics or schema contracts.

### 6.2 Effective configuration

Each dataset execution resolves an immutable effective configuration:

```text
Deployed semantic metadata
        +
valid runtime operational overrides
        +
run-mode / reprocess request
        =
EffectiveDatasetConfig
```

The effective config version/hash is recorded on `dataset_run` so every run is reproducible and explainable.

## 7. Runtime architecture

Conceptual per-dataset execution flow:

```text
Resolve effective dataset config
  -> acquire dataset lease / concurrency guard
  -> create dataset_run
  -> capture source changes
  -> write/normalize Bronze contract
  -> schema/DQ validation
  -> quarantine applicable bad rows/batches
  -> execute domain transformation hook when required
  -> apply target strategy
  -> reconcile
  -> commit runtime state/watermark only after required gates pass
  -> finalize audit
  -> release lease
```

Each significant step writes auditable status/metrics through a shared step-audit contract.

## 8. Metadata-driven orchestration

A domain-level Fabric Pipeline should act as a dispatcher:

```text
Lookup effective active dataset set
  -> filter by execution group/run request
  -> bounded parallel ForEach/dispatcher
  -> generic dataset executor(dataset_id, pipeline_run_id, run_mode)
  -> aggregate outcomes
```

The parent pipeline does not hard-code forty sets of source/target/merge/watermark parameters. Those come from metadata.

A single dataset failure must not immediately stop unrelated siblings. Dataset execution records a terminal outcome, while the parent performs an aggregate completion gate after independent eligible work has completed.

Expected dataset statuses include at least:

`PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `QUARANTINED`, `SKIPPED`, `BLOCKED_DEPENDENCY`, `CANCELLED`.

Expected parent outcomes include:

`SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`, `CANCELLED`.

Criticality/failure policy decides whether a failed dataset makes the final parent outcome fail.

## 9. Control-plane model

Detailed schema and lifecycle design lives in `docs/CONTROL_PLANE_DESIGN.md`.

Core entities are grouped as follows.

### Deployed configuration

- `dataset`
- `dataset_contract`
- `load_policy`
- `orchestration_policy`
- `data_quality_policy`
- `reconciliation_policy`
- `runtime_override`

### Runtime state and operations

- `watermark`
- `dataset_state`
- `dataset_lease`
- `pipeline_run`
- `dataset_run`
- `step_run`
- `reconciliation_result`
- `quarantine_batch`
- `schema_change`
- `reprocess_request`
- `deployment_history`

Framework owns schema definitions/migrations and APIs/contracts. Physical hosting is supplied through the infrastructure contract.

## 10. Audit model

Three levels of operational audit are required:

### Pipeline run

Captures orchestration scope, environment/domain, selected dataset count, aggregate status, domain Git SHA, metadata/config version and framework version.

### Dataset run

Captures dataset, attempt, run mode, effective-config hash, source/target state, watermark before/after, row metrics, reconciliation outcome, error classification and terminal status.

### Step run

Captures significant execution steps such as capture, Bronze write, validation, quarantine, transform, apply, reconcile and state commit with start/end/status/metrics/error information.

Structured audit records are durable operational state. Logs remain useful for diagnostics but are not a substitute for control-plane audit.

## 11. Quarantine model

Quarantine distinguishes bad/contract-violating data from platform/system failure.

- Row-level quarantine stores/references rejected records plus dataset/run/source lineage and rule/reason.
- Batch-level quarantine is allowed for severe contract violations; target state/watermark does not advance.
- Connection, permission, unavailable-resource and code failures are dataset failures, not quarantine.
- Quarantined data is replayable through an explicit `reprocess_request`/`REPLAY` path.
- Accepted + intentionally filtered + rejected/quarantined counts must reconcile with source rows according to policy.
- Quarantine storage retention/access is governed by enterprise security; the framework provides lineage and lifecycle contracts.

## 12. Stateful correctness

Watermark design must support duplicate timestamps via a tie-breaker or an overlap-window/idempotent alternative. State advances only after successful target commit and required reconciliation.

A dataset lease or optimistic concurrency mechanism prevents overlapping stateful runs from advancing the same dataset state concurrently.

SCD2 must eventually define/test business keys, tracked-attribute hashing, effective ranges, current-row invariant, insert/update/delete, duplicates, late/out-of-order events, rerun and backfill.

Recovery modes are explicit: `NORMAL`, `RETRY`, `BACKFILL`, `REPLAY`, `FULL_REBUILD`.

## 13. Reconciliation model

Reconciliation policy is metadata-driven where rules are stable. Examples include:

- source rows vs accepted + quarantined + intentional filters;
- source/target key counts;
- insert/update/delete control totals;
- hash/control-total comparison;
- freshness/event-time checks;
- duplicate business-key checks.

Policy decides whether a mismatch warns, quarantines the batch, fails the dataset, or blocks state advancement.

## 14. Testing model

- Unit tests: pure reusable logic, metadata validation, override restrictions and effective-config resolution.
- Contract tests: framework metadata, control-plane schemas, environment contract and audit/quarantine contracts.
- Orchestration tests: one dataset fails while unrelated siblings continue; critical vs non-critical aggregate result; dependency blocking; concurrency selection.
- Integration tests: representative small datasets and state transitions.
- Reconciliation tests: expected counts/hashes/state.
- Quarantine tests: row/batch rejection, lineage and replay eligibility.
- Smoke tests: later, against a deployed Fabric environment.

Tests prioritize correctness over volume or benchmark performance.

## 15. Release and versioning model

The package follows semantic versioning. Domain repositories pin exact released versions; `@main` or direct mutable branch dependencies are not production dependencies.

Framework release and domain release lifecycles are independent. A framework release never silently changes a deployed domain; the domain must accept an explicit dependency-upgrade PR.

The effective deployed metadata snapshot records the domain Git SHA/config hash so operational control tables cannot hide semantic drift.

## 16. Implementation cadence

This project is based on mature, known enterprise patterns. Implementation should therefore proceed in reasonably sized, coherent vertical capability slices rather than stopping for review after every small class/file.

Default Definition of Done for a substantive implementation slice:

1. code/contracts implemented;
2. relevant migrations/schema definitions included;
3. high-value tests written and executed where possible;
4. docs/ADR/status synchronized;
5. next coherent slice recorded.

A new architecture decision, destructive production action, or unresolved ambiguity can still require explicit review. Routine implementation within accepted ADR/Blueprint boundaries should continue without artificial approval pauses.

## 17. Implementation roadmap

### Phase 0 — COMPLETE
Canonical architecture, ownership model, ADRs and recoverable status documentation.

### Phase 1 — Framework foundation
Implement a coherent foundation slice covering:

1. `pyproject.toml`, package/test structure and quality tooling;
2. typed capture/apply/run-mode/status enums;
3. typed dataset/load/orchestration/DQ/reconciliation metadata models;
4. semantic-vs-operational override validation and effective-config resolution;
5. infrastructure/environment resolution interface;
6. immutable runtime context and identifiers;
7. audit, quarantine and reconciliation contracts;
8. control-plane schema/migration design for the initial core tables;
9. unit/contract tests for the above.

This is intentionally larger than the previous four-item micro-step, but it still does **not** implement WATERMARK extraction, SCD2/CDC algorithms, Fabric deployment or Terraform.

### Phase 2 onward
Follow the ecosystem roadmap beginning with one Customer WATERMARK -> Bronze -> SCD2 -> Silver vertical slice using the metadata/control-plane contracts, then delivery spine, remaining strategies, multi-dataset orchestration hardening, streaming and finally infrastructure automation.

## 18. Documentation obligations

Every meaningful implementation PR must update `docs/CURRENT_STATUS.md`; architecture changes must update this blueprint and/or add an ADR. The ecosystem blueprint is updated when cross-repository boundaries or shared architecture change.
