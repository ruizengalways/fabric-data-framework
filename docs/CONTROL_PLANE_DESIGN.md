# Control Plane and Metadata-Driven Runtime Design

Status: Canonical detailed design
Last updated: 2026-08-29

## Purpose

The control plane stores durable semantic definitions, environment-local runtime state and operational evidence for metadata-driven framework execution. It is not a business warehouse and not an unrestricted mutable configuration database.

## Core principles

1. Git/source-controlled domain definitions are the semantic source of truth.
2. Deployment materializes a runtime-readable semantic snapshot.
3. Runtime overrides are allow-listed operational controls only.
4. Effective config is immutable and deterministically hashed per attempt.
5. Capture/apply semantics and physical engines are separate decisions.
6. One physical capture has one authoritative source-progress owner.
7. Native/external capture is correlated through immutable CaptureReceipt evidence.
8. Runtime state/evidence is environment-local and never promoted.
9. Dataset is the default failure/retry boundary.
10. Unknown target outcome is reconciled before retry.
11. State progression is gated by target commit + required reconciliation.
12. Schema contract is promotable; schema observation is environment-local.
13. Operator-facing reads use typed projections instead of raw table coupling.

## Configuration layers

```text
Git semantic definition
    -> deployed semantic snapshot
        + allow-listed RuntimeOverride
        + RunRequest / ReprocessRequest
    -> immutable EffectiveDatasetConfig
```

Runtime overrides cannot change semantic identities such as merge/append keys, capture/apply strategy, schema contract, execution profile or custom extension identity.

## Current schema version

```text
CONTROL_PLANE_SCHEMA_VERSION = 3
```

Migration history:

```text
v1 phase1_initial_control_plane_schema
v2 execution_policy_ordering_capture_receipt_recovery_and_cdc
v3 append_identity_semantics
```

v3 explicitly adds `load_policy.append_identity` for an existing v2 store before recording migration success. `create_all()` alone is not treated as a general ALTER migration mechanism.

## Promotable semantic definitions

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

`dataset_contract` is versioned expected schema. `load_policy` owns capture/apply semantics and business/merge/append keys. `ordering_policy` owns event/version/sequence metadata. Execution policy independently selects capture and apply execution.

## Environment-local runtime/evidence

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

These never move DEV -> UAT -> PROD.

`cdc_checkpoint` records framework downstream CDC semantic application, not native/provider source cursor authority. `capture_receipt` retains native/provider correlation. `schema_change` records observation without rewriting source-controlled schema. `quarantine_batch` stores lineage/location/count, not large payloads.

## State/progress ownership

Framework-owned progress:

```text
read state/version
  -> freeze source boundary
  -> execute idempotent candidate/mutation
  -> reconcile/prove target outcome
  -> commit next state
```

Native/external progress:

```text
provider owns source cursor
  -> CaptureReceipt records correlation
  -> framework downstream semantic apply
  -> framework commits its own semantic state separately
```

No dual checkpoint truth is allowed.

## Recovery protocol

Failure classes are RETRYABLE, NON_RETRYABLE and UNKNOWN_OUTCOME. Unknown target mutation resolves to COMMITTED, NOT_COMMITTED or UNRESOLVED before any retry decision. Quarantine REPLAY and FULL_REBUILD are explicit audited flows.

The remaining portable durability gap is a stable persistent target-operation key/journal that makes physical mutation idempotency explicit across attempts rather than depending only on executor convention.

## Read-only operator projection

`operator.py` is the supported reference query layer above the relational schema.

`get_dataset_operational_snapshot()` returns a typed projection containing:

- latest `dataset_run` plus optional attempt lineage/root/previous/reprocess identity;
- latest `capture_receipt` and native/provider correlation;
- current WATERMARK and/or CDC downstream progress;
- latest reconciliation result;
- unreplayed quarantine batch/row counts;
- latest schema-change observation;
- active PENDING/RUNNING reprocess requests.

`list_dataset_operational_snapshots()` returns dataset-id ordered overviews.

The CLI exposes the same models through:

```text
fabric-framework control-plane-status --database-url ... [--dataset-id ...] [--output ...]
```

This command is read-only. It does not mutate checkpoints, replay data or authorize recovery.

The operator API is intentionally typed so a future production repository can replace direct SQLAlchemy queries without changing runbook semantics unnecessarily.

## Source-boundary evidence

File/API guardrails currently remain provider-neutral capture contracts rather than dedicated relational index tables. Future durable indexing should be added through explicit environment-local migrations if provider integration needs it; do not overload CaptureReceipt with arbitrary opaque state.

## Operator questions the production store must answer

- which dataset/attempt failed and at which stage;
- framework/domain/config/deployment identity;
- concrete capture/apply engine/profile;
- source range/snapshot/file manifest/API window/native run/checkpoint evidence;
- row/mutation/quarantine/reconciliation counts;
- schema expected vs observed classification;
- state before/after and committing attempt;
- recovery root/previous/request lineage;
- target-operation idempotency/outcome evidence once implemented.

## Current proof vs production store

Implemented/reference-tested:

- additive schema creation/idempotency;
- real v2 -> v3 additive migration;
- definition/runtime promotion boundary;
- semantic materialization including schema and APPEND identity;
- CaptureReceipt/recovery/CDC/schema evidence;
- runtime-state preservation during materialization;
- typed read-only operator aggregation and JSON CLI.

Not production-proven:

- approved persistent control-plane technology;
- real parallel transaction behavior under production load;
- migration checksum/rollback/rolling compatibility;
- authenticated operator mutation/approval surface;
- retention/backup/restore;
- IAM/network/security integration.

SQLite/in-memory remain deterministic reference proof only.

## Next control-plane work

1. add target-operation idempotency journal/state with optimistic lifecycle transitions;
2. select/certify the production repository technology while preserving typed operator contracts;
3. persist richer provider source/idempotency evidence where real integration requires it;
4. add authenticated mutation workflows only if included in product scope;
5. add production migration governance once a real store is selected.
