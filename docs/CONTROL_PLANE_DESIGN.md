# Control Plane and Metadata-Driven Runtime Design

Status: Canonical detailed design
Last updated: 2026-08-29

## 1. Purpose

The control plane stores durable semantic definitions, environment-local runtime state and operational evidence for metadata-driven framework execution. It is not a business warehouse and not an unrestricted mutable configuration database.

The framework must support tens/hundreds of datasets through reusable execution without one bespoke pipeline per table.

## 2. Core principles

1. Git/source-controlled domain definitions are the semantic source of truth.
2. Deployment materializes a runtime-readable semantic snapshot.
3. Runtime overrides are allow-listed operational controls only.
4. Effective config is immutable and deterministically hashed per attempt.
5. Capture semantics, apply semantics, capture executor and apply executor are separate decisions.
6. One physical capture has one authoritative source-progress owner.
7. Native/external capture is correlated through immutable `CaptureReceipt` evidence.
8. Framework downstream CDC application progress is distinct from native/external source checkpoint authority.
9. Runtime state/evidence is environment-local and never promoted.
10. Dataset is the default failure/retry boundary.
11. Recovery intent and attempt lineage are explicit and auditable.
12. Unknown target outcome is reconciled before retry.
13. State progression is gated by target commit + required reconciliation.
14. Every run is traceable to framework/domain/config/deployment identity.

## 3. Configuration layers

```text
Git semantic definition
    -> deployed semantic snapshot
        + allow-listed runtime override
        + RunRequest / ReprocessRequest
    -> immutable EffectiveDatasetConfig
```

Semantic changes require Git/deployment. Runtime overrides may change operational knobs such as enabled, priority, retry, timeout, batch size, bounded concurrency and approved watermark overlap; they may not change merge keys, capture/apply strategy, engine/profile identity, schema/delete semantics or extension implementation identity.

## 4. Current schema version

```text
CONTROL_PLANE_SCHEMA_VERSION = 2
```

v2 is still unreleased and now contains the complete current hardening definition:

```text
execution_policy
apply_execution_policy
ordering_policy
capture_receipt
reprocess_request
dataset_attempt_lineage
cdc_checkpoint
```

Because no public v2 control-plane contract has been released, these additive hardening changes remain version 2 rather than pretending a published migration history exists.

A production migration checksum/rolling-compatibility mechanism is still required when a persistent production store is selected.

## 5. Promotable semantic definitions

These travel with the domain release/config bundle:

### `dataset`
Dataset/domain/source/target identity, enabled default, criticality/group, config hash/schema version, domain Git SHA and framework version.

### `dataset_contract`
Expected schema/contract identity and compatibility policy.

### `load_policy`
Capture/apply semantics, keys, watermark metadata, event time/tracked columns and delete policy.

### `ordering_policy`
Event-time/version/sequence source-order metadata used by current-state/history semantics. Provider CDC offsets themselves are runtime evidence and do not belong in this definition table.

### `execution_policy`
Capture/movement engine, progress owner, capability profile and logical extension configuration.

### `apply_execution_policy`
Independent final-target apply engine and capability profile.

### `orchestration_policy`
Execution group, criticality, dependencies, priority, retry/timeout/batch/concurrency defaults.

### `data_quality_policy`
Reusable DQ/quarantine policy identity.

### `reconciliation_policy`
Required completion checks and state/publication gate behavior.

## 6. Environment-local state/evidence

These rows never move between DEV/UAT/PROD.

### `schema_migration_history`
Environment-local applied schema history.

### `runtime_override`
Audited operational override with requester/reason/validity/precedence.

### `watermark`
Framework-owned WATERMARK progress. FABRIC_NATIVE/EXTERNAL capture must not also advance a competing framework watermark for the same physical source cursor.

### `cdc_checkpoint`
Framework downstream CDC semantic-application progress:

```text
dataset_id
positions               # canonical per-partition integer tuples
committed_dataset_run_id
version                 # optimistic-concurrency token
created_at
updated_at
```

Important distinction:

```text
positions = canonical CDC semantic progress
version   = control-plane concurrency version
```

For FABRIC_NATIVE/EXTERNAL capture, provider/native source progress remains provider-owned and is correlated through `CaptureReceipt`. `cdc_checkpoint` records downstream framework semantic completion and must not be used to claim source-cursor ownership.

Checkpoint persistence rejects:

- target/reconciliation gate failure;
- source-position regression;
- dropping an already-known partition;
- stale `expected_version`;
- concurrent stale update.

### `dataset_state`
Generic committed runtime state beyond specialized watermark/CDC state.

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

### `capture_receipt`
Immutable handoff evidence for one physical capture:

```text
dataset run / dataset
capture strategy
execution engine
progress owner
native run id
source / landing reference
rows read / written
source lower / upper bound
snapshot identity / completeness
external checkpoint reference
schema / timestamps
```

### `step_run`
Meaningful operational lifecycle checkpoints, not every Python function call.

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

Semantic identity is immutable; lifecycle status/timestamps may change.

### `deployment_history`
Environment-local deployment provenance and previous deployment linkage.

## 7. Promotion boundary

Canonical sets in code:

```text
PROMOTABLE_DEFINITION_TABLES
ENVIRONMENT_LOCAL_STATE_TABLES
```

They remain disjoint and every known control-plane table must be classified.

Promotion copies definitions/migrations/item definitions only. It never copies watermarks, CDC checkpoints, leases, run history, receipts, quarantine, reprocess requests or attempt lineage.

## 8. Metadata materialization

`delivery.materialize_semantic_metadata()` idempotently materializes source-controlled semantic definitions and preserves runtime state.

Current materialized definition scope includes:

- dataset identity/provenance;
- load policy;
- ordering policy;
- capture execution engine/progress owner/profile/extensions;
- independent apply engine/profile;
- orchestration/DQ/reconciliation policies.

The config bundle hash is deterministic and environment-independent.

## 9. Native/external capture evidence path

```text
ExecutionPlan capture unit
    -> provider request
    -> native/external run evidence
    -> adapter validation
    -> CaptureReceipt
    -> downstream framework stages
```

Fabric adapter contracts reject native FAILED/CANCELLED/UNKNOWN status and evidence mismatch. FRAMEWORK-owned bounded movement additionally requires observed source bounds to match the requested bounds.

For native/external CDC, the receipt retains provider checkpoint/run correlation. It does not automatically advance `cdc_checkpoint`; downstream semantic application + reconciliation must succeed first.

## 10. CDC state protocol

Canonical CDC detail lives in `CDC_DESIGN.md`.

Framework downstream sequence:

```text
read cdc_checkpoint + version
  -> freeze upper checkpoint / obtain completeness evidence
  -> normalize canonical events
  -> apply selected semantic (UPSERT/SCD1/SCD2/...)
  -> reconcile target
  -> validate CDCCheckpointTransition
  -> commit cdc_checkpoint(expected_version=N)
  -> version N+1
```

A stale writer fails rather than overwriting newer progress.

Snapshot/bootstrap initialization:

```text
start/retain CDC at S
snapshot complete/consistent through B, where S <= B
apply/publish snapshot
CDC <= B -> overlap already represented by snapshot
CDC >  B -> semantic apply
commit downstream checkpoint after target/reconciliation success
```

Current bootstrap proof rejects repartition during the handoff.

## 11. Recovery model

### Failure classification

```text
RETRYABLE
NON_RETRYABLE
UNKNOWN_OUTCOME
```

Only explicit retryable failures automatically retry. Unknown/unclassified exceptions are non-retryable by default.

### Attempt protocol

```text
validate/create non-normal request
  -> append attempt lineage
  -> execute attempt
  -> record terminal audit
  -> retry only when classification/policy allows
  -> link next attempt to previous/root
```

### Unknown commit protocol

```text
target mutation response uncertain
  -> reconcile actual target state
       COMMITTED     -> converge success
       NOT_COMMITTED -> retry may proceed
       UNRESOLVED    -> stop
```

Blind duplicate write is prohibited.

### Reprocess contracts

- RETRY requires original dataset run.
- BACKFILL requires explicit lower/upper range.
- REPLAY requires original run or quarantine IDs.
- FULL_REBUILD requires explicit authoritative-reset intent.

Generic recovery core is implemented. Strategy/provider-specific replay/resume/rebuild remains partial.

## 12. State/progress ownership

FRAMEWORK-owned source progress:

```text
read committed source state/version
  -> freeze source boundary
  -> execute idempotent candidate/mutation
  -> reconcile/prove target outcome
  -> commit next source/application state
```

FABRIC_NATIVE/EXTERNAL source progress:

```text
provider owns native/source checkpoint
  -> framework records provider correlation in CaptureReceipt
  -> framework processes landing/events
  -> framework records downstream semantic completion separately
  -> provider offset resume/commit behavior is adapter-specific
```

The framework never silently invents ownership of a native/external source cursor.

## 13. Row accounting and reconciliation

For bounded row flows:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

CDC additionally tracks duplicate/committed-overlap/stale/no-change/delete observations where relevant. Required reconciliation can block checkpoint/state progression.

## 14. Operator questions

A production control plane must answer:

- which pipeline/dataset/attempt failed and at which stage;
- framework/domain/config/deployment identity;
- concrete capture/apply engine/profile;
- native run ID / external checkpoint / landing;
- source range/snapshot/CDC positions;
- CDC downstream checkpoint + version + committing run;
- row/mutation/quarantine/CDC duplicate/stale counts;
- reconciliation result;
- state before/after;
- root/previous attempt lineage;
- retryability and authorized recovery path.

## 15. Current proof vs production store

Implemented/reference-tested:

- additive schema creation/idempotency;
- definition/runtime promotion boundary;
- execution/apply/ordering materialization;
- CaptureReceipt persistence;
- ReprocessRequest persistence with immutable semantic identity;
- dataset attempt-lineage append-only evidence;
- CDC checkpoint persistence + optimistic concurrency;
- runtime-state preservation during semantic materialization.

Not production-proven:

- approved persistent control-plane technology;
- real transaction/parallel concurrency behavior under production load;
- migration checksum/rollback/rolling compatibility;
- operator API/CLI/query layer;
- retention/backup/restore;
- IAM/network/security integration.

SQLite/in-memory are deterministic reference proof only.

## 16. Next control-plane work

1. Persist richer source-boundary/state-before/state-after evidence consistently across capture families.
2. Integrate provider-specific native/external CDC checkpoint correlation and recovery.
3. Complete quarantine replay lineage updates.
4. Complete FULL_REBUILD reset/rebuild evidence.
5. Add supported persistent repository + transaction/concurrency tests.
6. Add operator `status/retry/backfill/replay/rebuild` surface.
7. Ingest real Fabric Pipeline/Copy/Dataflow/SJD run IDs from actual transports.

## 17. Documentation/evidence rule

Any lifecycle/schema change must update `CONTROL_PLANE_DESIGN.md`, `PRODUCTION_REQUIREMENTS.md`, `GUARANTEE_COVERAGE.md`, `PRODUCTION_READINESS_AUDIT.md`, relevant strategy design docs and `CURRENT_STATUS.md`, with executable evidence before being marked implemented.
