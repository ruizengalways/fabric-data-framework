# Control Plane and Metadata-Driven Runtime Design

Status: Canonical detailed design
Last updated: 2026-08-29

## 1. Purpose

The control plane stores durable semantic definitions, environment-local runtime state and operational evidence for metadata-driven framework execution. It is not a business warehouse and not an unrestricted mutable configuration database.

## 2. Core principles

1. Git/source-controlled domain definitions are the semantic source of truth.
2. Deployment materializes a runtime-readable semantic snapshot.
3. Runtime overrides are allow-listed operational controls only.
4. Effective config is immutable and deterministically hashed per attempt.
5. Capture semantics, apply semantics, capture executor and apply executor are separate decisions.
6. One physical capture has one authoritative source-progress owner.
7. Native/external capture is correlated through immutable `CaptureReceipt` evidence.
8. Provider/native source progress and framework downstream semantic progress are distinct.
9. Runtime state/evidence is environment-local and never promoted.
10. Dataset is the default failure/retry boundary.
11. Recovery intent/attempt lineage are explicit and auditable.
12. Unknown target outcome is reconciled before retry.
13. State progression is gated by target commit + required reconciliation.
14. Schema contract is promotable; schema observation is environment-local evidence.

## 3. Configuration layers

```text
Git semantic definition
    -> deployed semantic snapshot
        + allow-listed RuntimeOverride
        + RunRequest / ReprocessRequest
    -> immutable EffectiveDatasetConfig
```

Runtime overrides cannot change semantic identities such as merge/append keys, capture/apply strategy, schema contract, execution engine/profile or custom extension identity.

## 4. Current schema version and migrations

```text
CONTROL_PLANE_SCHEMA_VERSION = 3
```

Migration history:

```text
v1 phase1_initial_control_plane_schema
v2 execution_policy_ordering_capture_receipt_recovery_and_cdc
v3 append_identity_semantics
```

v3 is important because it proves an actual additive change against an existing v2 store. `metadata.create_all()` creates missing tables but does not alter existing tables; therefore migration 3 explicitly adds `load_policy.append_identity` when absent and records the migration only after the DDL succeeds.

This is still a reference migration mechanism. A selected production store requires migration checksums, rollback/forward policy, rolling compatibility and operational ownership.

## 5. Promotable semantic definitions

These move with the domain release/config bundle:

```text
dataset
dataset_contract
load_policy
ordering_policy
execution_policy
apply_execution_policy
orchestration_policy
data_quality_policy
reconciliation_policy
```

### `dataset_contract`

Versioned expected schema contract. It stores contract version, stable fingerprint, compatibility policy and full typed definition. A new contract version is appended/upserted under its version identity; it does not silently overwrite historical versions.

### `load_policy`

Owns capture/apply semantics and semantic keys including:

```text
business_key
merge_key
append_identity
watermark metadata
event/tracked columns
delete policy
```

APPEND identity is explicitly separate from merge keys.

### `ordering_policy`

Event-time/version/sequence metadata used by ordered current-state/history semantics.

### `execution_policy` / `apply_execution_policy`

Capture/movement engine + progress owner + capability profile + logical extensions, and independently selected apply engine/profile.

## 6. Environment-local state/evidence

These rows never move DEV -> UAT -> PROD:

```text
schema_migration_history
runtime_override
watermark
cdc_checkpoint
dataset_state
dataset_lease
pipeline_run
dataset_run
dataset_attempt_lineage
capture_receipt
step_run
reconciliation_result
quarantine_batch
schema_change
reprocess_request
deployment_history
```

### `watermark`
Framework-owned WATERMARK progress only.

### `cdc_checkpoint`
Framework downstream CDC semantic-application progress with canonical per-partition positions, committing dataset run and optimistic-concurrency version. It is not a provider/native source cursor.

### `capture_receipt`
Immutable physical-capture handoff evidence: engine, progress owner, native run ID, landing/source refs, rows, bounds/snapshot/checkpoint/schema/timestamps.

### `schema_change`
Append-only runtime observation evidence: expected/observed fingerprint, classification and detailed field changes. It records what was seen; it does not mutate the source-controlled contract.

### `quarantine_batch`
Immutable lineage/location/reason/count plus replay correlation. Large payloads remain in governed data storage.

### `dataset_attempt_lineage` / `reprocess_request`
Explicit retry/backfill/replay/rebuild intent and attempt lineage.

## 7. Promotion boundary

Canonical sets in code:

```text
PROMOTABLE_DEFINITION_TABLES
ENVIRONMENT_LOCAL_STATE_TABLES
```

They are disjoint and cover every known control-plane table. Promotion copies definitions/migrations/item definitions only, never runtime checkpoints, receipts, runs, quarantine, schema observations or reprocess state.

## 8. Metadata materialization

`delivery.materialize_semantic_metadata()` idempotently materializes:

- dataset identity/provenance;
- versioned schema contract;
- capture/apply/load keys including APPEND identity;
- ordering policy;
- capture engine/progress/profile/extensions;
- independent apply engine/profile;
- orchestration/DQ/reconciliation policy.

Runtime state remains untouched.

## 9. State/progress ownership

FRAMEWORK-owned progress:

```text
read committed state/version
  -> freeze source boundary
  -> execute idempotent candidate/mutation
  -> reconcile/prove target outcome
  -> commit next state
```

FABRIC_NATIVE/EXTERNAL progress:

```text
provider owns source cursor
  -> CaptureReceipt records provider correlation
  -> framework performs downstream semantic processing
  -> framework commits its own downstream semantic state separately
```

No dual source-of-truth checkpointing is allowed.

## 10. CDC state protocol

```text
read cdc_checkpoint + version
  -> freeze complete upper checkpoint
  -> normalize canonical events
  -> semantic apply
  -> reconcile target
  -> validate transition
  -> optimistic checkpoint commit
```

Checkpoint regression, partition drop, stale writer and pre-reconciliation progression fail closed.

## 11. Recovery protocol

Failure classes:

```text
RETRYABLE
NON_RETRYABLE
UNKNOWN_OUTCOME
```

Unknown target mutation:

```text
COMMITTED     -> converge success
NOT_COMMITTED -> retry may proceed
UNRESOLVED    -> stop
```

Quarantine REPLAY resolves immutable quarantine evidence, loads governed payload through an external provider boundary and marks originals replayed only after successful target/reconciliation gate.

FULL_REBUILD uses `reprocess_request_id` as stable destructive identity and performs optimistic capture-aware state cutover only after authoritative rebuild completion.

## 12. File/API source evidence

Current file/API guardrails are provider-neutral and currently live in capture contracts rather than new relational tables.

File evidence freezes a manifest fingerprint over snapshot/listing reference + object URI/version/readiness/metadata. API evidence freezes source bounds/filter identity and validates page/cursor/completeness/volume evidence.

If future production operations require durable relational indexing of those manifests/windows, add environment-local evidence tables through an explicit migration rather than overloading `capture_receipt` with opaque JSON.

## 13. Operator questions the production store must answer

- which dataset/attempt failed and at which semantic stage;
- framework/domain/config/deployment identity;
- concrete capture/apply engine/profile;
- source range/snapshot/file manifest/API window/native run/checkpoint evidence;
- row/mutation/quarantine/reconciliation counts;
- schema expected vs observed classification;
- state before/after and committing attempt;
- recovery request/root/previous attempt lineage;
- retryability and authorized recovery path.

## 14. Current proof vs production store

Implemented/reference-tested:

- additive schema creation/idempotency;
- real v2 -> v3 additive migration;
- definition/runtime promotion boundary;
- semantic materialization including versioned schema contracts and APPEND identity;
- CaptureReceipt persistence;
- recovery/reprocess lineage evidence;
- CDC checkpoint optimistic concurrency;
- schema-change append-only evidence;
- runtime-state preservation during materialization.

Not production-proven:

- approved persistent control-plane technology;
- real parallel transaction behavior under production load;
- migration checksum/rollback/rolling compatibility;
- supported operator query/API/CLI surface;
- retention/backup/restore;
- IAM/network/security integration.

SQLite/in-memory are deterministic reference proof only.

## 15. Next control-plane work

1. Add supported persistent repository/query surface and transaction/concurrency certification.
2. Persist richer source-boundary/idempotency evidence where provider integration requires it.
3. Integrate real Fabric/Kafka run/cursor correlation.
4. Add operator `status/retry/backfill/replay/rebuild` workflows.
5. Add production migration governance once a real store is selected.

## 16. Documentation/evidence rule

Any lifecycle/schema change must update `CONTROL_PLANE_DESIGN.md`, `PRODUCTION_REQUIREMENTS.md`, `GUARANTEE_COVERAGE.md`, `PRODUCTION_READINESS_AUDIT.md`, relevant strategy docs and `CURRENT_STATUS.md` with executable evidence before being marked implemented.
