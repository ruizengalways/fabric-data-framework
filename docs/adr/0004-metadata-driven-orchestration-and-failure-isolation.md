# ADR-0004 — Metadata-driven orchestration and dataset failure isolation

Status: Accepted
Date: 2026-08-28

## Context

The platform must support domains with tens of datasets/tables without creating one bespoke Fabric Pipeline per table and without coupling the fate of every dataset in a batch.

Stable behaviour differs by metadata: datasets can use different capture/apply strategies, merge keys, watermark/event-time columns, criticality, quality/reconciliation policies and runtime parameters.

Production operators also need to disable or tune an individual dataset during incidents without redeploying code. At the same time, runtime control tables must not become an uncontrolled second source of semantic truth.

A forty-table orchestration run must not immediately abort all remaining independent work because one non-critical table fails. However, true critical failures still need to produce an observable failed parent outcome for alerting and operations.

## Decision

### 1. Metadata-driven dataset execution

Dataset execution semantics are declared in source-controlled domain metadata and consumed by generic framework runtime code.

The framework supports per-dataset metadata including, as applicable:

- source/target identity;
- capture strategy;
- apply strategy;
- business/merge keys;
- watermark column and tie-breaker;
- event-time column;
- tracked columns;
- delete/late-arrival/dedupe policy;
- execution group/criticality/dependencies;
- DQ/quarantine policy;
- reconciliation policy.

### 2. Semantic configuration remains Git-driven

Business/merge keys, apply/capture semantics, schema contracts and other correctness-defining fields change through Git/PR/deployment.

Deployment materializes an immutable/effectively immutable runtime-readable metadata snapshot with config hash, domain Git SHA and framework version.

### 3. Runtime operational overrides are allowed but constrained

The control plane supports audited, typed, optionally time-bounded overrides for approved operational knobs such as enable/disable, priority, retry, timeout, batch size, approved overlap window and bounded concurrency.

Runtime overrides cannot silently change semantic fields in PROD.

### 4. Fabric Pipeline is a dispatcher

The reference orchestration pattern is:

```text
lookup/select active datasets
 -> bounded parallel dispatch
 -> generic dataset executor(dataset_id, run context)
 -> aggregate recorded outcomes
 -> final completion gate
```

Table-specific merge/watermark/source parameters are resolved from effective metadata rather than duplicated across pipeline activities.

### 5. Dataset is the default failure boundary

A failed dataset records its own terminal status and leaves committed state unchanged. Unrelated datasets continue where safe.

Dependent datasets are marked blocked/skipped when a prerequisite fails; unrelated branches are not cancelled.

### 6. Parent outcome is aggregated after eligible work completes

The orchestration run records one of at least:

- `SUCCESS`;
- `PARTIAL_SUCCESS`;
- `FAILED`;
- `CANCELLED`.

Criticality/failure policy decides the final aggregate. A Fabric parent may deliberately fail only at the final completion gate after independent eligible datasets have completed.

### 7. Quarantine, audit and reconciliation are part of the runtime contract

The framework owns durable pipeline/dataset/significant-step audit contracts, explicit row/batch quarantine lineage, reconciliation results and reprocess/replay requests.

System failures are not disguised as quarantine. Quarantined batches do not advance watermark/state.

## Consequences

### Positive

- Tens of tables can share a small number of generic orchestration/runtime patterns.
- Adding a stable-pattern dataset is primarily configuration plus domain-specific transformations/tests where required.
- One non-critical failure does not destroy all useful work in a domain batch.
- Operators can temporarily disable/tune datasets without mutating business semantics.
- Every run remains traceable to code/config/framework versions.
- Retry/replay/quarantine and audit have explicit lineage.

### Trade-offs

- The framework/control plane becomes more substantial than a simple set of Spark helper functions.
- Metadata schema governance and migrations become important.
- Effective configuration and override precedence must be carefully tested.
- Parent `PARTIAL_SUCCESS` semantics require operational consumers/alerts to understand dataset-level status, not only a single Fabric pipeline status.
- Concurrency/state locking requires deliberate implementation for stateful datasets.

## Alternatives rejected

### One Fabric Pipeline per table

Rejected because it creates excessive duplicated orchestration, deployment surface and maintenance cost for stable repeated patterns.

### One giant forty-table pipeline where any activity failure immediately fails the run

Rejected because it creates unnecessary blast radius and makes recovery/retry expensive.

### Fully mutable control tables as the only configuration source

Rejected because production semantic drift would not be reliably tied to Git review/deployment provenance.

### Swallow every dataset error so the parent always succeeds

Rejected because it hides critical failures from standard operational alerting. The chosen design continues independent work but computes a truthful aggregate at the end.

## Related documents

- `docs/ECOSYSTEM_BLUEPRINT.md`
- `docs/PROJECT_BLUEPRINT.md`
- `docs/CONTROL_PLANE_DESIGN.md`
- `docs/adr/0002-capture-vs-apply-strategy.md`
- `docs/adr/0003-control-plane-ownership.md`
