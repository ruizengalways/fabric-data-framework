# Control Plane and Metadata-Driven Runtime Design

Status: Canonical detailed design
Last updated: 2026-08-29

## 1. Purpose

The control plane stores durable semantic definitions, environment-local runtime state and operational evidence for metadata-driven framework execution. It is not a business warehouse and not an unrestricted mutable configuration database.

The framework must support tens/hundreds of datasets through reusable execution without one bespoke pipeline per table.

## 2. Core principles

1. Git/source-controlled domain definitions are the semantic source of truth.
2. Deployment materializes a runtime-readable snapshot.
3. Runtime overrides are allow-listed operational controls only.
4. Effective config is immutable and deterministically hashed per attempt.
5. Capture semantics, apply semantics, capture executor and apply executor are separate decisions.
6. One physical capture has one authoritative progress owner.
7. Native/external capture is correlated through `CaptureReceipt`.
8. Runtime state/evidence is environment-local and never promoted.
9. Dataset is the default failure/retry boundary.
10. Recovery intent and attempt lineage are explicit and auditable.
11. Unknown target outcome is reconciled before retry.
12. Every run is traceable to framework/domain/config/deployment identity.

## 3. Configuration layers

```text
Git semantic definition
    -> deployed semantic snapshot
        + allow-listed runtime override
        + RunRequest/ReprocessRequest
    -> immutable EffectiveDatasetConfig
```

Semantic changes require Git/deployment. Runtime overrides may change operational knobs such as enabled, priority, retry, timeout, batch size, bounded concurrency and approved overlap; they may not change merge keys, semantic strategies, engine/profile identity, schema/delete semantics or extension implementation identity.

## 4. Current schema version

```text
CONTROL_PLANE_SCHEMA_VERSION = 2
```

v2 is still an unreleased development schema and currently includes the broader hardening slice:

```text
execution_policy
apply_execution_policy
ordering_policy
capture_receipt
reprocess_request
dataset_attempt_lineage
```

The schema evolution is additive. A production migration/checksum/rolling-compatibility mechanism is still required when a persistent production store is selected.

## 5. Promotable semantic definitions

These travel with the domain release/config bundle:

### `dataset`

Dataset/domain/source/target identity, enabled default, criticality/group, config hash/schema version, domain Git SHA and framework version.

### `dataset_contract`

Expected schema/contract identity and compatibility policy.

### `load_policy`

Capture/apply semantics, keys, watermark metadata, event time/tracked columns and delete policy.

### `ordering_policy`

First-class event-time/version/sequence source-position columns used by current-state/history/CDC semantics.

### `execution_policy`

Capture/movement engine, progress owner, capability profile and logical extension configuration.

### `apply_execution_policy`

Independent final-target apply engine and apply capability profile.

### `orchestration_policy`

Execution group, criticality, dependencies, priority, retry/timeout/batch/concurrency defaults.

### `data_quality_policy`

Reusable DQ/quarantine policy identity.

### `reconciliation_policy`

Required completion checks and state/publication gate behavior.

## 6. Environment-local state/evidence

These rows never move between DEV/UAT/PROD:

### `schema_migration_history`

Environment-local applied schema history.

### `runtime_override`

Audited operational override with requester/reason/validity/precedence.

### `watermark`

Framework-owned committed incremental progress only. A FABRIC_NATIVE/EXTERNAL capture must not also advance a competing framework watermark for the same physical source progress.

### `dataset_state`

Generic committed runtime state beyond watermark.

### `dataset_lease`

Single-writer/concurrency guard for framework-owned mutable state.

### `pipeline_run`

One orchestration request with environment/domain/release/config provenance and aggregate status.

### `dataset_run`

One dataset attempt with attempt number, status, config hash, row/mutation/error/retryability evidence.

### `dataset_attempt_lineage`

Append-only attempt linkage:

```text
dataset_run_id
root_dataset_run_id
previous_dataset_run_id
attempt
run_mode
reprocess_request_id
created_at
```

Attempt 1 is its own root. Attempts >1 require a previous run.

### `capture_receipt`

Immutable handoff evidence for one physical capture:

```text
dataset run/dataset
capture strategy
execution engine
progress owner
native run id
source/landing reference
rows read/written
source lower/upper bound
snapshot identity/completeness
external checkpoint reference
schema/timestamps
```

### `step_run`

Meaningful operational checkpoints, not every Python function call.

### `reconciliation_result`

Expected/actual metrics, status and whether progression is blocked.

### `quarantine_batch`

Quarantine lineage/location/reason/count/replay correlation. Large payloads belong in governed data storage, not necessarily the relational control DB.

### `schema_change`

Observed/expected fingerprint and classification evidence; general schema policy remains incomplete.

### `reprocess_request`

Audited non-normal execution intent:

```text
RETRY
BACKFILL
REPLAY
FULL_REBUILD
```

Required fields depend on mode. Semantic identity is immutable; lifecycle status/timestamps may change.

### `deployment_history`

Environment-local deployment provenance and previous deployment linkage.

## 7. Promotion boundary

Canonical sets in code:

```text
PROMOTABLE_DEFINITION_TABLES
ENVIRONMENT_LOCAL_STATE_TABLES
```

They must remain disjoint and together cover every control-plane table.

Promotion copies definitions/migrations/item definitions only. It never copies watermarks, run history, leases, receipts, quarantine, reprocess requests or attempt lineage.

## 8. Metadata materialization

`delivery.materialize_semantic_metadata()` idempotently materializes source-controlled semantic definitions and preserves runtime state.

Current materialized policy includes:

- dataset identity/provenance;
- load policy;
- ordering policy;
- capture execution engine/progress owner/profile/extensions;
- independent apply engine/profile;
- orchestration/DQ/reconciliation policies.

The config bundle hash is deterministic and environment-independent.

## 9. Native capture evidence path

```text
ExecutionPlan capture unit
    -> FabricCaptureRequest
    -> provider transport
    -> FabricNativeRunEvidence
    -> FabricCaptureAdapter validation
    -> CaptureReceipt
    -> downstream framework stages
```

The adapter rejects native FAILED/CANCELLED/UNKNOWN status and evidence mismatch. For FRAMEWORK-owned bounded movement, the observed source bounds must equal the requested bounds before a receipt is accepted.

## 10. Recovery model

### Failure classification

```text
RETRYABLE
NON_RETRYABLE
UNKNOWN_OUTCOME
```

Only explicit retryable failures may automatically retry. Unknown/unclassified exceptions are non-retryable by default.

### Attempt protocol

```text
create/validate request if non-normal
  -> create attempt lineage
  -> execute attempt
  -> record dataset terminal audit
  -> retry only if classified and policy allows
  -> link next attempt to previous/root
```

### Unknown commit protocol

```text
target mutation response uncertain
  -> reconcile actual target state
       COMMITTED     -> converge success
       NOT_COMMITTED -> retry may proceed
       UNRESOLVED    -> fail/stop
```

Blind duplicate write is prohibited.

### Reprocess request validation

- RETRY requires original dataset run.
- BACKFILL requires explicit lower/upper range.
- REPLAY requires original run or quarantine IDs.
- FULL_REBUILD requires explicit authoritative-reset intent.

The generic core is implemented. Strategy-specific source retention/restaging/replay/rebuild execution remains to be completed.

## 11. State/progress commit protocol

FRAMEWORK-owned progress:

```text
read committed state/version
  -> acquire guard
  -> freeze source boundary
  -> execute idempotent candidate/mutation
  -> reconcile/prove target outcome
  -> commit next state
  -> finalize audit
```

FABRIC_NATIVE/EXTERNAL progress:

```text
provider owns source checkpoint
  -> framework records receipt/checkpoint correlation
  -> downstream apply/reconcile failure is recovered without inventing a second source checkpoint
```

## 12. Row accounting and reconciliation

For bounded row flows:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Strategy-specific evidence includes current-state duplicate/superseded/stale counts, destructive-load guards and future CDC event/offset accounting.

Required reconciliation can block publication/state progression.

## 13. Operator questions

The production control plane must answer:

- which pipeline/dataset/attempt failed and where;
- framework/domain/config/deployment identity;
- concrete capture/apply engine/profile;
- native Fabric run ID and landing;
- source range/snapshot/checkpoint;
- row/mutation/quarantine counts;
- reconciliation result;
- committed state before/after;
- root/previous attempt lineage;
- whether failure is retryable;
- whether retry/backfill/replay/rebuild is safe and authorized.

## 14. Current proof vs production store

Implemented/reference-tested:

- additive schema creation/idempotency;
- definition/runtime promotion boundary;
- execution/apply/ordering materialization;
- CaptureReceipt persistence;
- ReprocessRequest persistence with immutable semantic identity;
- dataset attempt-lineage append-only evidence;
- runtime-state preservation during semantic materialization.

Not production-proven:

- approved persistent control-plane technology;
- real transaction/parallel concurrency behavior;
- migration checksum/rollback/rolling compatibility;
- operator API/CLI/query layer;
- retention/backup/restore;
- IAM/network/security integration.

SQLite/in-memory are deterministic contract proof only.

## 15. Next control-plane work

1. CDC checkpoint/event evidence and state transition contracts.
2. Persist exact source-boundary/state-before/state-after evidence consistently across capture families.
3. Complete quarantine replay lineage updates.
4. Complete FULL_REBUILD reset/rebuild evidence.
5. Add supported persistent repository + transaction/concurrency tests.
6. Add operator `status/retry/backfill/replay/rebuild` surface.
7. Ingest real Fabric Pipeline/Copy/Dataflow/SJD run IDs from actual transports.

## 16. Documentation/evidence rule

Any control-plane lifecycle/schema change must update `CONTROL_PLANE_DESIGN.md`, `PRODUCTION_REQUIREMENTS.md`, `GUARANTEE_COVERAGE.md`, `PRODUCTION_READINESS_AUDIT.md` and `CURRENT_STATUS.md`, with executable evidence before it is marked implemented.
