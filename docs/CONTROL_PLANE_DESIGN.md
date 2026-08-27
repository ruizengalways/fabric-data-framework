# Control Plane and Metadata-Driven Runtime Design

Status: Canonical detailed design
Last updated: 2026-08-28

## 1. Purpose

This document defines the production-oriented metadata/control-plane model for `fabric-data-framework`. It expands the ecosystem/project blueprints without changing repository ownership boundaries.

The design must support domains with tens of datasets using reusable orchestration rather than one bespoke pipeline per table.

## 2. Core principles

1. Dataset semantics are declared once and consumed generically.
2. Git remains the canonical source for semantic configuration.
3. Runtime control tables support state and audited operational tuning; they are not an uncontrolled second source of business semantics.
4. A dataset is the default fault/isolation boundary.
5. Watermark/state advances only after successful required gates.
6. Quarantine is explicit and reconciled; data loss is never silent.
7. Every run is traceable to code, config and framework versions.
8. Reprocess/retry/replay are modeled operations, not ad-hoc manual reruns.

## 3. Configuration layers

### 3.1 Source-controlled semantic definition

A domain-owned dataset definition declares stable execution semantics, for example:

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
business_key: [customer_id]
merge_key: [customer_id]
watermark:
  column: modified_at
  tie_breaker: [customer_id]
event_time_column: modified_at
tracked_columns: [name, address, segment]
orchestration:
  execution_group: crm_daily
  criticality: HIGH
  dependencies: []
quality:
  policy: customer_standard
  quarantine_policy: reject_bad_rows
reconciliation:
  policy: standard_count_and_key
```

Semantic fields that alter data meaning or correctness require a Git change and deployment. This includes business/merge keys, capture/apply strategy, schema contract, delete semantics and DQ/reconciliation semantics.

### 3.2 Deployed metadata snapshot

Deployment materializes a runtime-readable representation containing at least:

- dataset definition;
- config schema version;
- config hash;
- domain Git SHA/release;
- framework version expected by the domain release;
- deployed environment;
- deployment timestamp/history reference.

The runtime reads the deployed snapshot rather than parsing arbitrary mutable files at every activity step.

### 3.3 Runtime operational override

Operations may change approved runtime knobs without redeploying semantic configuration. Each override includes:

- environment/domain/dataset or execution-group scope;
- parameter name and typed value;
- reason/ticket/reference;
- requested/changed by;
- created timestamp;
- valid-from/valid-to or explicit expiry;
- enabled status;
- previous/effective value lineage.

Typical allowed knobs:

- dataset enabled/disabled;
- priority;
- retry count/backoff profile;
- timeout;
- batch/chunk size;
- bounded concurrency profile;
- approved watermark overlap window;
- temporary execution-group inclusion/exclusion.

The first implementation should use an allow-list of overridable fields rather than arbitrary key/value mutation.

## 4. Effective configuration

Before dataset execution, the framework resolves:

```text
DeployedDatasetDefinition
 + valid RuntimeOverride(s)
 + RunRequest / ReprocessRequest
 = EffectiveDatasetConfig
```

The resulting object is immutable for the lifetime of a dataset attempt and has its own deterministic hash/version recorded on `dataset_run`.

If an override is invalid, expired, conflicting or would change forbidden semantic fields, resolution fails before data mutation.

## 5. Control-plane entities

Names below are logical; physical SQL naming can be finalized with migrations.

## 5.1 `dataset`

Registry of deployed datasets.

Key fields:

- `dataset_id` stable logical identifier;
- domain/source system/source object;
- target logical layer/object;
- enabled default;
- criticality;
- execution group;
- current deployed config version/hash;
- deployed Git SHA;
- expected framework version;
- active/effective dates.

## 5.2 `dataset_contract`

Schema/contract identity and compatibility policy.

Key fields:

- dataset ID;
- contract/schema version;
- schema fingerprint or reference;
- compatibility policy;
- effective/deployed version metadata.

## 5.3 `load_policy`

Stable capture/apply/state semantics.

Key fields:

- capture strategy;
- apply strategy;
- business key list;
- merge key list;
- watermark column;
- watermark tie-breaker list;
- event-time column;
- overlap-window default/allowed bounds;
- tracked columns or tracking rule reference;
- delete policy;
- late-arrival policy;
- dedupe/source-sequence policy.

## 5.4 `orchestration_policy`

Execution/failure/parallelism defaults.

Key fields:

- execution group;
- criticality;
- dependency list/stage;
- concurrency/source-concurrency profile;
- timeout;
- retry/backoff profile;
- final failure policy;
- schedule association if needed by deployment/orchestration layer.

## 5.5 `data_quality_policy`

References reusable rule sets and action thresholds.

Rules may produce outcomes such as:

- pass;
- warn;
- quarantine row;
- quarantine batch;
- fail dataset.

Business-specific rules remain domain-owned even if executed by reusable framework primitives.

## 5.6 `reconciliation_policy`

Defines completion gates such as:

- source vs accepted/quarantined/filtered count balance;
- source/target key counts;
- insert/update/delete controls;
- hashes/control totals;
- freshness/event-time expectations.

The policy also defines whether mismatches warn, quarantine, fail or prevent state advancement.

## 5.7 `runtime_override`

Audited operational control described in section 3.3.

Semantic changes are forbidden through this table by validation policy.

## 5.8 `watermark`

Committed source progress for incremental datasets.

Key fields:

- dataset ID;
- committed watermark value;
- committed tie-breaker value(s);
- state version;
- last successful dataset run ID;
- committed timestamp.

A proposed next watermark may be calculated during a run but becomes committed only after target apply and required reconciliation succeed.

## 5.9 `dataset_state`

Generic current runtime state beyond watermark, such as last successful run, last full rebuild, schema version observed and state version for optimistic concurrency.

## 5.10 `dataset_lease`

Prevents overlapping mutable executions of the same stateful dataset.

Fields include dataset, lease/run owner, acquisition time, expiry/heartbeat if used and state version.

A stale-lease recovery procedure is required before production use.

## 5.11 `pipeline_run`

One orchestration request/run.

Recommended fields:

- `pipeline_run_id` framework UUID;
- Fabric pipeline run ID/correlation ID where available;
- environment/domain/execution group;
- run mode;
- requested by/trigger type;
- selected dataset count;
- start/end/duration;
- aggregate status;
- succeeded/failed/quarantined/skipped/blocked counts;
- domain Git SHA/release;
- framework version;
- deployed metadata version/hash reference;
- parent/reprocess request reference;
- error summary for orchestration-level failure.

## 5.12 `dataset_run`

One dataset attempt inside a pipeline/reprocess context.

Recommended fields:

- `dataset_run_id`;
- pipeline run ID;
- dataset ID;
- attempt number;
- run mode;
- effective-config hash/version;
- start/end/duration;
- status;
- source range/snapshot/event-time boundaries;
- watermark before/proposed/after;
- rows read;
- rows accepted;
- rows inserted/updated/deleted;
- rows rejected/quarantined;
- rows intentionally filtered;
- reconciliation status;
- schema version/fingerprint observed;
- error category/code/message;
- retryable flag;
- original dataset run ID for retry/replay lineage.

## 5.13 `step_run`

Audit of significant dataset-execution steps.

Suggested step names:

`RESOLVE_CONFIG`, `ACQUIRE_LEASE`, `CAPTURE`, `BRONZE_WRITE`, `VALIDATE`, `QUARANTINE`, `TRANSFORM`, `APPLY`, `RECONCILE`, `COMMIT_STATE`, `FINALIZE`.

Fields include dataset run ID, step name, attempt, start/end/status, row/byte metrics where meaningful and error details.

Do not create a step row for every trivial Python function; the unit is an operationally meaningful checkpoint.

## 5.14 `reconciliation_result`

Stores rule-level/group-level reconciliation results, expected/actual values, tolerance, severity and action taken.

## 5.15 `quarantine_batch`

Stores quarantine lineage and location rather than requiring large rejected payloads in the control database.

Recommended fields:

- quarantine ID;
- dataset/pipeline/dataset-run IDs;
- scope (`ROW_SET` or `BATCH`);
- rule/reason/category;
- record count;
- quarantine storage/table/path logical reference;
- schema version;
- created timestamp;
- replay eligibility/status;
- resolved/reprocessed run reference;
- retention classification if required.

Row-level quarantine data carries framework lineage columns in the quarantine store.

## 5.16 `schema_change`

Records observed schema differences and disposition (`ACCEPTED`, `WARNED`, `QUARANTINED`, `REJECTED`, etc.).

## 5.17 `reprocess_request`

Explicit request to retry/backfill/replay/rebuild.

Fields include:

- request ID;
- dataset(s)/scope;
- mode;
- source range/watermark range/snapshot/quarantine reference;
- reason;
- requested by/time;
- approval/reference if later required;
- status;
- resulting pipeline/dataset run references.

## 5.18 `deployment_history`

Records environment deployment provenance:

- domain release/Git SHA;
- framework version;
- config hash/version;
- deployment mechanism/run ID;
- target environment;
- timestamp/status.

## 6. Orchestration design

## 6.1 Dispatcher

Reference Fabric orchestration:

```text
Start
 -> create pipeline_run
 -> lookup effective dataset list
 -> filter enabled + requested execution group + dependency readiness
 -> bounded parallel dispatcher
       -> dataset executor for each dataset
 -> aggregate recorded dataset statuses
 -> write final pipeline_run status
 -> optionally fail Fabric parent at final gate if aggregate policy requires
```

The Fabric pipeline should pass identifiers, not dozens of table-specific settings. Dataset executor code loads effective metadata using `dataset_id`.

## 6.2 Failure isolation

Do not model a forty-table batch as one atomic success/failure unit.

For each dataset:

- handle/audit its own failure path;
- finalize `dataset_run` terminal status;
- preserve watermark/state on failure;
- allow unrelated siblings to continue.

After all eligible independent work has completed, aggregate:

- `SUCCESS` if required work succeeded;
- `PARTIAL_SUCCESS` if only policy-allowed non-critical items failed/quarantined/skipped;
- `FAILED` for critical failures, threshold breaches or orchestration integrity failure.

A production alert can therefore fire on the final failed aggregate without losing useful progress on unrelated datasets.

## 6.3 Dependencies

Initial support should use explicit execution groups/stages and simple dataset dependencies. If a prerequisite fails:

- direct dependents become `BLOCKED_DEPENDENCY`;
- unrelated datasets continue;
- blocked datasets do not touch state or targets.

Do not build a general-purpose workflow engine until concrete domain requirements justify it.

## 6.4 Concurrency

Concurrency controls exist at multiple levels:

- parent dispatcher maximum parallel datasets;
- execution-group/source-system limit;
- per-dataset single-writer lease for stateful loads;
- optional sink/source-specific concurrency profile.

Operational overrides may reduce limits during incidents or source-system pressure.

## 7. Quarantine lifecycle

### 7.1 Row-level invalid data

If policy allows row quarantine:

1. validate row;
2. write invalid row plus lineage/reason to quarantine location;
3. continue with accepted rows only if rule/action permits;
4. include quarantined count in reconciliation;
5. make final dataset status/warning policy explicit.

### 7.2 Batch contract violation

If the batch is unsafe to apply:

1. preserve/source-faithful Bronze where appropriate;
2. record quarantine batch and reason;
3. do not apply target mutation;
4. do not advance state;
5. finalize dataset as `QUARANTINED` or `FAILED` according to policy.

### 7.3 System error

System errors are not quarantine. Record a failed step/dataset with retryability classification.

### 7.4 Replay

Corrected/released quarantined data is reprocessed by an explicit `reprocess_request` in `REPLAY` mode. New run IDs are created while retaining original quarantine/run lineage.

## 8. Audit/reconciliation invariants

At minimum, production correctness should be able to answer:

- Which code/config/framework version processed this dataset?
- What source range or watermark did it read?
- What was written/inserted/updated/deleted?
- What was rejected or quarantined and why?
- Did accepted + quarantined + intentional filters reconcile to input?
- Which step failed?
- Was state/watermark advanced?
- Can this exact scope be retried/replayed safely?

For relevant loads, a useful accounting invariant is conceptually:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

with strategy-specific adjustments documented rather than silently ignored.

## 9. State commit protocol

For a stateful incremental dataset:

1. read committed state/version;
2. acquire lease/guard;
3. calculate source range;
4. execute data movement/transform/apply idempotently;
5. reconcile required invariants;
6. atomically/optimistically commit next state referencing successful dataset run;
7. finalize audit;
8. release lease.

A failure before step 6 leaves committed state unchanged.

If state commit certainty is lost after data mutation, rerun/recovery must rely on idempotency and reconciliation rather than assuming nothing was written.

## 10. Runtime override governance

Operational flexibility must not become uncontrolled production configuration drift.

Required controls:

- typed/allow-listed parameters;
- environment/dataset/group scope;
- operator identity;
- reason/ticket;
- expiry where practical;
- audit history;
- effective-config hash on each run;
- ability to list active overrides;
- safe removal/reversion.

Semantic changes remain Git-driven.

## 11. Testing requirements

Before production claims, tests must cover at least:

- metadata validation for merge/business keys and watermark requirements;
- forbidden semantic runtime overrides;
- effective-config precedence and deterministic hashing;
- one non-critical dataset failure while siblings succeed;
- critical failure causing final aggregate failure only after eligible siblings finish;
- dependency blocking without unrelated cancellation;
- dataset lease/concurrent-state protection;
- failed incremental load not advancing watermark;
- quarantined rows accounted for in reconciliation;
- batch quarantine preventing target/state commit;
- retry/replay lineage;
- step audit completeness for success and failure paths.

## 12. Fabric implementation notes

The architecture intentionally maps well to Microsoft Fabric Data Factory capabilities such as parameterized pipelines, Lookup-driven dynamic dataset selection, ForEach bounded parallelism and completion/failure control-flow branches.

Exact Fabric activity limits and deployment syntax are implementation details and must be checked against current Microsoft Learn documentation when the Fabric item is built.

## 13. Initial implementation boundary

Phase 1 should implement the **contracts and control-plane schema foundations**, not the full Fabric dispatcher or SCD2/WATERMARK algorithms.

The first coherent foundation slice should include typed metadata models, override rules/effective-config resolution, run/status/audit/quarantine/reconciliation contracts, initial control-plane schema/migrations approach, infrastructure resolution interface and high-value unit/contract tests.

Phase 2 will use those contracts in the first Customer WATERMARK/SCD2 vertical slice. Multi-dataset dispatcher hardening follows once the per-dataset executor semantics are proven.
