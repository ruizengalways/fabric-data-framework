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
5. Capture/apply semantics and physical stage executors are separate concerns.
6. Capture/movement and final-target apply execution policies are independent.
7. One physical capture has one authoritative progress owner.
8. Native/external capture is correlated through `CaptureReceipt`.
9. Runtime state/evidence is environment-local and never promoted DEV -> UAT -> PROD.
10. Dataset is the default failure/isolation boundary.
11. Quarantine/reconciliation/state progression are explicit.
12. Recovery operations have explicit requests/lineage, not ad-hoc manual reruns.
13. Every run must be traceable to framework/domain/config/deployment identity.

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
  sequence_column: source_sequence

execution:
  engine: DATAFLOW_GEN2
  progress_owner: FABRIC_NATIVE
  capability_profile: dataflow_gen2_incremental_bucket_v1
  apply_engine: AUTO
  apply_capability_profile: null

orchestration:
  execution_group: erp_incremental_current
  criticality: HIGH
  dependencies: []

quality:
  policy_name: customer_standard
  quarantine_policy: reject_bad_rows

reconciliation:
  policy_name: current_state_standard
```

Semantic changes require Git/deployment. This includes strategy, keys, ordering semantics, delete policy, capture/apply engine/profile identity, extension identity, schema/DQ/reconciliation semantics.

### 3.2 Deployed metadata snapshot

Deployment materializes at least:

- dataset definition;
- config schema version/hash;
- domain Git SHA/release;
- expected framework version;
- capture execution/profile/progress policy;
- apply execution/profile policy;
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
- capture/apply engine/profile semantic identity;
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

`AUTO` is a policy value, not a final physical executor. Capability resolution must produce concrete capture/apply engines before an immutable `ExecutionPlan` is emitted.

## 5. Schema versioning

Current reference control-plane schema version:

```text
CONTROL_PLANE_SCHEMA_VERSION = 2
```

The v2 evolution is additive and is still unreleased as part of the 0.4.0 development line. It currently includes:

```text
execution_policy
apply_execution_policy
ordering_policy
capture_receipt
```

This prevents physical stage policy and source ordering semantics from being hidden in opaque JSON or only in code/docs.

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

Current physical baseline exists; broader schema-evolution behavior remains required.

### 6.3 `load_policy`

Semantic data behavior:

- capture strategy;
- apply strategy;
- business/merge keys;
- watermark column/tie-breaker/overlap;
- event-time/tracked columns;
- delete policy.

Capture/apply remain independent semantics.

### 6.4 `ordering_policy` — v2

First-class source ordering metadata:

- event-time column;
- version column;
- sequence/LSN-like column.

SCD1/UPSERT/CDC/SCD2 can use these semantics without embedding physical engine assumptions.

### 6.5 `execution_policy` — v2

Physical **capture/movement** policy:

- execution engine;
- progress owner;
- named capture capability profile;
- controlled extension config.

This table does not imply downstream apply ownership.

### 6.6 `apply_execution_policy` — v2

Independent physical **apply** policy:

- execution engine;
- named apply capability profile.

Current conservative runtime behavior resolves `AUTO` to SPARK/framework apply. Native/SQL apply remains fail-closed until a named profile certifies the requested `ApplyStrategy`. A CUSTOM apply requires a controlled `extensions.apply` reference in the source config.

`apply_execution_policy` is included in `PROMOTABLE_DEFINITION_TABLES` and is created by the same baseline schema/CLI path as the other semantic definitions.

### 6.7 `orchestration_policy`

- execution group;
- criticality;
- dependencies;
- priority;
- retry/timeout/batch/concurrency defaults.

### 6.8 `data_quality_policy`

References reusable rules/action thresholds. Business-specific rule definitions remain domain-owned.

### 6.9 `reconciliation_policy`

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

One orchestration request with environment/domain/run mode, release/config provenance, timestamps/status and future Fabric parent run correlation.

### 7.6 `dataset_run`

One dataset attempt with IDs, dataset/attempt, effective-config hash, status/timestamps, row mutations, error/retryability and future source-boundary/state/original-attempt lineage.

Attempt/recovery lineage is not yet complete.

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

Example:

```text
Dataflow Gen2 incremental
  -> capture_receipt(progress_owner=FABRIC_NATIVE)
  -> framework SCD1/UPSERT
```

The framework does not advance a second watermark merely because it owns apply.

### 7.9 `reconciliation_result`

Rule/group expected/actual/status/evidence and whether progression is blocked.

### 7.10 `quarantine_batch`

Quarantine lineage/location/reason/count/replay reference. Large rejected payloads belong in governed storage, not necessarily the relational control DB.

### 7.11 `schema_change`

Observed/expected fingerprint and disposition. General schema policy is not yet fully implemented.

### 7.12 `reprocess_request`

Explicit RETRY/BACKFILL/REPLAY/FULL_REBUILD request with scope/range/snapshot/quarantine reference, reason/requester, original run references, status/results and future approval reference where required.

### 7.13 `deployment_history`

Environment-local deployment provenance: domain release/Git SHA, framework version, config hash, schema/item versions, mechanism/build, actors, timestamps/status and previous deployment.

## 8. Definition vs runtime promotion boundary

Canonical sets in code:

```text
PROMOTABLE_DEFINITION_TABLES
ENVIRONMENT_LOCAL_STATE_TABLES
```

They are disjoint and cover the schema.

Promotable definitions now include both:

```text
execution_policy
apply_execution_policy
```

Promotion never copies DEV watermark/state/leases/runs/receipts/quarantine/reprocess/deployment history into UAT/PROD.

## 9. Metadata materialization

`delivery.materialize_semantic_metadata()` is idempotent for deployed definitions and preserves runtime state.

Current v2 materialization persists:

- dataset identity/provenance;
- load policy;
- ordering policy;
- capture engine/progress owner/capture profile/extensions;
- apply engine/apply profile;
- orchestration policy;
- DQ/reconciliation policy.

The config bundle hash is deterministic and environment-independent.

## 10. Orchestration and execution-plan flow

Reference logical flow:

```text
create pipeline_run
  -> load deployed definitions/overrides
  -> resolve EffectiveDatasetConfig
  -> independently validate capture/apply capabilities
  -> compile concrete ExecutionPlan
  -> filter/group/dependency ready sets
  -> bounded execution backend
       -> dataset attempts / execution units
  -> aggregate terminal outcomes
  -> finalize pipeline_run
```

Fabric Pipeline should eventually execute the same provider-neutral decisions, not duplicate dataset correctness logic in visual activities.

## 11. Failure isolation

Dataset is the default fault boundary.

- dataset failure is recorded/finalized;
- unrelated siblings continue when safe;
- direct dependents become `BLOCKED`;
- aggregate status is determined after eligible work completes;
- failed dataset must not advance framework-owned progress.

This reference behavior is certified by dispatcher tests.

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
native/external authority owns its checkpoint
  -> framework records CaptureReceipt/checkpoint correlation
  -> downstream apply/reconcile remains independent
```

Recovery must address native capture success followed by downstream failure without inventing a false second source checkpoint.

## 13. Row accounting and reconciliation

For relevant bounded row flows:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Strategy-specific evidence includes:

- insert/update/delete;
- SCD1/UPSERT duplicate/superseded/stale/conflict;
- snapshot completeness/delete guards;
- future CDC event/offset accounting.

Required reconciliation failure can block publication/state progression.

## 14. Quarantine lifecycle

Row defects may quarantine and continue when policy allows. Batch/contract defects block unsafe publication/progress. Connection/permission/code/runtime defects are failures, not quarantine.

Replay remains a required lifecycle and must create new run/attempt lineage while preserving original quarantine/run identity.

## 15. Operator questions the control plane must answer

Eventually without reading notebook source:

- What dataset/run/attempt failed and which step?
- Which framework/domain/config/deployment version ran?
- Which concrete capture and apply engines/profiles were selected?
- Which native Fabric run produced the landing?
- Who owns the capture checkpoint?
- What source boundary/snapshot/offset was processed?
- Where was data landed?
- What were read/accepted/quarantined/inserted/updated/deleted counts?
- What duplicate/superseded/stale evidence existed?
- Did reconciliation pass?
- Did framework state advance?
- Is exact retry/backfill/replay safe and what is its lineage?

## 16. Current reference evidence vs production store

Implemented/reference-tested:

- schema v2 creation/idempotency;
- promotable vs environment-local boundary;
- capture and apply execution-policy materialization;
- ordering-policy materialization;
- `CaptureReceipt` persistence contract;
- metadata materialization preserving runtime watermark/state;
- release/control-plane schema version provenance.

Representative proof:

```text
tests/test_control_plane_v2.py
tests/test_apply_execution_policy.py
tests/test_delivery.py
```

Not yet production-proven:

- approved persistent control-plane technology for the Fabric estate;
- real transaction/concurrency behavior under production load;
- migration checksum/rollback/rolling-compatibility mechanism;
- operator query/API surface;
- retention/backup/restore;
- IAM/network/secret integration.

SQLite/in-memory adapters are deterministic contract proof only.

## 17. Next control-plane work

1. extend dataset-run/attempt/original-run lineage for recovery;
2. add source-boundary/checkpoint/state-before/state-after evidence consistently;
3. implement reprocess request lifecycle;
4. implement CDC event/checkpoint evidence;
5. implement schema-contract/change disposition;
6. add supported persistent repository + transactional tests;
7. add operator status/retry/backfill/replay queries/CLI;
8. ingest real Fabric Pipeline/Copy/Dataflow/SJD run IDs through adapters.

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
