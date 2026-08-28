# Control Plane and Metadata-Driven Runtime Design

Status: Canonical detailed design
Last updated: 2026-08-28

## 1. Purpose

This document defines the durable semantic metadata, runtime state and operational evidence model for `fabric-data-framework`.

The framework must support tens/hundreds of datasets through reusable metadata-driven execution without one bespoke pipeline per table.

The control plane is not a second business warehouse and not an uncontrolled mutable configuration store.

## 2. Core principles

1. Git/source-controlled domain definitions are the source of semantic truth.
2. Deployment materializes a runtime-readable semantic snapshot.
3. Runtime overrides are allow-listed operational controls only.
4. Effective config is immutable for one dataset attempt and deterministically hashed.
5. Capture/apply semantics and physical execution engine are separate concerns.
6. One physical capture has one authoritative progress owner.
7. Native/external capture is correlated through `CaptureReceipt`.
8. Runtime state/evidence is environment-local and never promoted DEV -> UAT -> PROD.
9. Dataset is the default failure/isolation boundary.
10. Quarantine/reconciliation/state progression are explicit.
11. Recovery operations have explicit requests/lineage, not ad-hoc manual reruns.
12. Every run must be traceable to framework/domain/config/deployment identity.

## 3. Configuration layers

### 3.1 Source-controlled semantic definition

Representative definition:

```yaml
dataset_id: erp.customer

source:
  system: erp
  object: dbo.Customer
  connection_ref: erp_sql

target:
  layer: silver
  object: customer

load:
  capture_strategy: WATERMARK
  apply_strategy: SCD1
  merge_key: [tenant_id, customer_id]
  watermark:
    column: modified_at
    overlap_window_seconds: 60
  event_time_column: modified_at
  version_column: source_version

execution:
  engine: DATAFLOW_GEN2
  progress_owner: FABRIC_NATIVE
  capability_profile: dataflow_gen2_incremental_bucket_v1

orchestration:
  execution_group: erp_incremental_current
  criticality: HIGH
  dependencies: []

quality:
  policy_name: customer_standard
  quarantine_policy: reject_bad_rows

reconciliation:
  policy_name: current_state_standard

extensions:
  transform: null
```

Semantic changes require Git/deployment. This includes strategy, keys, ordering semantics, delete policy, engine/profile identity, extension identity, schema/DQ/reconciliation semantics.

### 3.2 Deployed metadata snapshot

Deployment materializes at least:

- dataset definition;
- config schema version/hash;
- domain Git SHA/release;
- expected framework version;
- execution/profile policy;
- ordering policy;
- deployment provenance.

Runtime execution should read deployed metadata rather than arbitrary mutable files on every activity step.

### 3.3 Runtime operational override

Allowed examples:

- enabled/disabled;
- priority;
- retry count;
- timeout;
- batch size;
- bounded concurrency;
- approved watermark overlap.

Required override evidence:

- scope;
- typed value;
- reason/reference;
- requested by;
- created/valid-from/valid-to;
- precedence;
- enabled state.

Forbidden through runtime override:

- merge/business keys;
- capture/apply strategy;
- engine/profile semantic identity;
- extension implementation identity;
- schema contract;
- delete semantics.

## 4. Effective config

Before execution:

```text
DeployedDatasetDefinition
 + active valid RuntimeOverride(s)
 + RunRequest / ReprocessRequest
 = immutable EffectiveDatasetConfig
```

The effective config receives a deterministic hash. Invalid/conflicting overrides fail before mutation.

## 5. Schema versioning

Current reference control-plane schema version:

```text
CONTROL_PLANE_SCHEMA_VERSION = 2
```

The v2 evolution is additive rather than rewriting released v1 runtime tables.

v2 adds first-class ownership for:

```text
execution_policy
ordering_policy
capture_receipt
```

This prevents execution/profile/order semantics from being hidden in opaque JSON or only in chat/docs.

The current SQLAlchemy migration helper proves schema/materialization behavior. A production migration framework with immutable migration checksums/compatibility policy remains required for the selected persistent store.

## 6. Promotable semantic definition entities

Promotable definitions travel as part of the domain release/config bundle. They do **not** include runtime progress.

### 6.1 `dataset`

Registry identity/provenance:

- dataset ID;
- domain;
- source system/object;
- target layer/object;
- enabled default;
- criticality/execution group;
- config schema version/hash;
- domain Git SHA;
- framework version.

### 6.2 `dataset_contract`

Schema/contract identity and compatibility policy.

Current physical baseline exists; broader schema-evolution behavior remains P0.

### 6.3 `load_policy`

Semantic data behavior:

- capture strategy;
- apply strategy;
- business/merge keys;
- watermark column/tie-breaker/overlap;
- event-time/tracked columns;
- delete policy.

Capture/apply remain independent.

### 6.4 `ordering_policy` — v2

First-class source ordering metadata such as:

- event time column;
- version column;
- sequence/LSN column;
- future tie/duplicate policy references.

SCD1/UPSERT/CDC/SCD2 can use these semantics without embedding physical engine assumptions.

### 6.5 `execution_policy` — v2

Physical capture/movement policy:

- engine;
- progress owner;
- named capability profile;
- logical extension references or serialized extension config where appropriate.

Important: `execution_policy` currently describes capture/movement ownership. Future schema evolution must make apply-executor/native apply delegation an explicit separate decision rather than interpreting this table as lifecycle-wide ownership.

### 6.6 `orchestration_policy`

- execution group;
- criticality;
- dependencies;
- priority;
- retry/timeout/batch/concurrency defaults.

### 6.7 `data_quality_policy`

References reusable rules/action thresholds. Business-specific rule definitions remain domain-owned.

### 6.8 `reconciliation_policy`

Defines required completion checks and whether failures block publication/state progression.

## 7. Environment-local state and evidence

These rows are never promoted between environments.

### 7.1 `runtime_override`

Audited operational controls described above.

### 7.2 `watermark`

Framework-owned committed incremental progress only.

A dataset using `FABRIC_NATIVE` capture progress must not create/advance a competing framework watermark for the same physical capture.

### 7.3 `dataset_state`

Generic environment-local state beyond watermark: last success/rebuild, schema state/version, idempotency/recovery references as the model expands.

### 7.4 `dataset_lease`

Single-writer/concurrency guard for mutable framework-owned state. Stale lease recovery remains required before production use.

### 7.5 `pipeline_run`

One orchestration request:

- framework pipeline run ID;
- environment/domain/run mode;
- release/config provenance;
- start/end/status;
- aggregate outcomes;
- future Fabric parent run correlation.

### 7.6 `dataset_run`

One dataset attempt:

- run IDs;
- dataset/attempt/run mode;
- effective config hash;
- status/timestamps;
- row accounting/mutations;
- error/retryability;
- future source boundary/state before/after/original attempt lineage.

Attempt/recovery lineage is not yet complete and is P0.

### 7.7 `step_run`

Operationally meaningful checkpoints, for example:

```text
RESOLVE_CONFIG
ACQUIRE_LEASE
CAPTURE
BRONZE_WRITE
VALIDATE
QUARANTINE
TRANSFORM
STAGE
APPLY
RECONCILE
PUBLISH
COMMIT_STATE
FINALIZE
```

Do not create step rows for every trivial Python call.

### 7.8 `capture_receipt` — v2

Environment-local evidence for one physical capture/landing operation.

Current contract includes/correlates:

- dataset run ID/dataset ID;
- capture strategy;
- physical execution engine;
- progress owner;
- native run ID;
- landing reference;
- rows read/written;
- source lower/upper boundary when meaningful;
- snapshot ID/completeness when meaningful;
- external checkpoint reference when meaningful;
- started/completed timestamps.

This is the handoff between native/external movement and framework downstream semantics.

Example:

```text
Dataflow Gen2 incremental
  -> capture_receipt(progress_owner=FABRIC_NATIVE)
  -> framework SCD1
```

The framework does not advance a second watermark merely because it owns SCD1 apply.

### 7.9 `reconciliation_result`

Rule/group expected/actual/status/evidence and whether progression is blocked.

### 7.10 `quarantine_batch`

Quarantine lineage/location/reason/count/replay reference. Large rejected payloads belong in governed storage, not necessarily the relational control DB.

### 7.11 `schema_change`

Observed/expected fingerprint and disposition. General schema policy is not yet fully implemented.

### 7.12 `reprocess_request`

Explicit RETRY/BACKFILL/REPLAY/FULL_REBUILD request:

- scope/range/snapshot/quarantine reference;
- reason/requester;
- original run references;
- status/results;
- future approval reference where enterprise policy requires it.

### 7.13 `deployment_history`

Environment-local deployment provenance:

- domain release/Git SHA;
- framework version;
- config bundle hash;
- control-plane schema version;
- Fabric item manifest version;
- mechanism/CI build;
- initiated/approved by;
- timestamps/status/previous deployment.

## 8. Definition vs runtime promotion boundary

Canonical sets in code:

```text
PROMOTABLE_DEFINITION_TABLES
ENVIRONMENT_LOCAL_STATE_TABLES
```

The sets are disjoint and cover the schema.

Promotion includes semantic definitions/schema migrations/item definitions. It never copies DEV watermark/state/leases/runs/receipts/quarantine/reprocess/deployment history into UAT/PROD.

## 9. Metadata materialization

`delivery.materialize_semantic_metadata()` is idempotent for deployed definitions and preserves runtime state.

Current v2 materialization persists:

- dataset identity/provenance;
- load policy;
- ordering policy;
- execution engine/progress owner/capability profile/extension config;
- orchestration policy;
- DQ/reconciliation policy.

The config bundle hash is deterministic and environment-independent.

## 10. Orchestration design

Reference logical flow:

```text
create pipeline_run
  -> load deployed definitions/overrides
  -> resolve EffectiveDatasetConfig
  -> capability validation + ExecutionPlan compilation
  -> filter/group/dependency ready sets
  -> bounded execution backend
       -> dataset attempts
  -> aggregate terminal outcomes
  -> finalize pipeline_run
```

Fabric Pipeline should eventually execute the same provider-neutral decisions, not duplicate dataset business/correctness logic in visual activities.

## 11. Failure isolation

Dataset is the default fault boundary.

- dataset failure is recorded/finalized;
- unrelated siblings continue when safe;
- direct dependents become `BLOCKED`;
- aggregate status is determined after eligible work completes;
- failed dataset must not advance framework-owned progress.

This reference behavior is already certified by dispatcher tests.

## 12. State/progress commit protocol

For FRAMEWORK-owned progress:

```text
read committed state/version
  -> acquire lease/guard
  -> freeze source range
  -> execute idempotent capture/apply candidate
  -> reconcile
  -> publish/commit target
  -> commit next framework state referencing successful run
  -> finalize audit
  -> release lease
```

For FABRIC_NATIVE/EXTERNAL capture progress:

```text
native/external authority advances its checkpoint according to adapter semantics
  -> framework records CaptureReceipt/checkpoint correlation
  -> downstream framework apply/reconcile remains independent
```

The adapter/recovery design must address cases where native capture succeeded but downstream apply failed. The framework must not invent a false second source checkpoint; replay/restaging must use receipt/native capabilities.

## 13. Row accounting and reconciliation

For relevant bounded row flows:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Strategy-specific evidence additionally includes:

- insert/update/delete;
- SCD1 duplicate/superseded/stale/conflict;
- snapshot completeness/delete guards;
- future CDC event/offset accounting.

Required reconciliation failure can block publication/state progression.

## 14. Quarantine lifecycle

### Row defect

```text
validate
 -> quarantine invalid row with lineage/reason
 -> continue accepted rows if policy permits
 -> reconcile counts
```

### Batch/contract defect

```text
preserve source-faithful landing where appropriate
 -> record batch defect
 -> do not perform unsafe publication/progress transition
 -> terminal QUARANTINED/FAILED policy
```

### System defect

Connection/permission/code/runtime defects are failures, not quarantine.

### Replay

Replay remains a required P0 lifecycle. It must create new run/attempt lineage while preserving original quarantine/run identity.

## 15. Operator questions the control plane must answer

Eventually without reading notebook source:

- What dataset/run/attempt failed and which step?
- Which framework/domain/config/deployment version ran?
- Which concrete execution engine/profile was selected?
- Which native Fabric run produced the landing?
- Who owns the capture checkpoint?
- What source boundary/snapshot/offset was processed?
- Where was data landed?
- What were read/accepted/quarantined/inserted/updated/deleted counts?
- What duplicate/superseded/stale evidence existed?
- Did reconciliation pass?
- Did framework state advance?
- Is exact retry/backfill/replay safe and what is its lineage?

## 16. Current reference implementation vs production store

Implemented/reference-tested:

- schema v2 creation/idempotency;
- promotable vs environment-local table boundary;
- v2 execution/ordering policy materialization;
- `CaptureReceipt` relational persistence contract;
- metadata materialization preserving runtime watermark/state;
- release/control-plane schema version provenance.

Not yet production-proven:

- approved persistent control-plane technology for the Fabric estate;
- real transaction/concurrency behavior under parallel production runs;
- migration checksum/rollback/rolling-compatibility mechanism;
- operator query/API surface;
- retention/backup/restore;
- IAM/network/secret integration.

SQLite/in-memory adapters are deterministic contract proof only.

## 17. Next control-plane work

1. extend dataset-run/attempt/original-run lineage for recovery;
2. add source-boundary/checkpoint/state-before/state-after evidence consistently;
3. add explicit apply-executor/native-delegation metadata when execution plan evolves;
4. implement reprocess request lifecycle;
5. implement CDC event/checkpoint evidence;
6. implement schema-contract/change disposition;
7. add supported persistent repository + transactional tests;
8. add operator status/retry/backfill/replay queries/CLI;
9. ingest real Fabric Pipeline/Copy/Dataflow/SJD run IDs through adapters.

## 18. Documentation/evidence rule

Changes to control-plane schema or lifecycle must update:

```text
CONTROL_PLANE_DESIGN.md
PRODUCTION_REQUIREMENTS.md
GUARANTEE_COVERAGE.md
PRODUCTION_READINESS_AUDIT.md
CURRENT_STATUS.md
```

and include executable schema/materialization/repository evidence before being marked implemented.
