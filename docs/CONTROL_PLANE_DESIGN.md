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
8. Provider/native source progress, framework semantic progress and target-operation outcome are distinct state domains.
9. Runtime state/evidence is environment-local and never promoted.
10. Dataset is the default failure/retry boundary.
11. Dataset attempt identity is separate from stable target-operation identity.
12. Unknown target outcome is reconciled before target retry.
13. State progression is gated by target commit + required reconciliation.
14. Schema contract is promotable; schema observation is environment-local.
15. Operator reads use typed projections instead of raw table coupling.

## Configuration layers

```text
Git semantic definition
    -> deployed semantic snapshot
        + allow-listed RuntimeOverride
        + RunRequest / ReprocessRequest
    -> immutable EffectiveDatasetConfig
```

Runtime overrides cannot change semantic identities such as merge/append keys, capture/apply strategy, schema contract, execution profile or custom extension identity.

`DatasetCaptureSelection` is a source-controlled onboarding companion used by CI. It is intentionally not runtime control-plane state.

## Current schema version

```text
CONTROL_PLANE_SCHEMA_VERSION = 4
```

Migration history:

```text
v1 phase1_initial_control_plane_schema
v2 execution_policy_ordering_capture_receipt_recovery_and_cdc
v3 append_identity_semantics
v4 target_operation_idempotency_journal
```

v3 adds `load_policy.append_identity` to an existing v2 store. v4 additively creates `target_operation`. `create_all()` remains an idempotent baseline helper, not a substitute for explicit production migration governance.

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

These are definitions that may move through DEV/UAT/PROD as part of an immutable release.

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
target_operation
capture_receipt
step_run
reconciliation_result
quarantine_batch
schema_change
reprocess_request
deployment_history
```

These never move DEV -> UAT -> PROD.

## Three distinct progress/outcome domains

### Provider/native source cursor

Owned by FABRIC_NATIVE or EXTERNAL when the source platform is authoritative.

Examples:

```text
Copy Job native watermark/CDC state
Kafka consumer/connector position
external CDC source cursor
```

### Framework semantic source progress

Examples:

```text
watermark
cdc_checkpoint
```

These represent source progress that has successfully reached framework semantic completion.

### Target operation outcome

`target_operation` answers:

> Did this exact frozen semantic target mutation commit, not commit, fail, or remain uncertain?

These domains are not interchangeable.

```text
target_operation COMMITTED
        !=
automatic permission to advance watermark/cdc_checkpoint
```

Required dataset reconciliation/state gates still apply.

## `target_operation` schema

Environment-local v4 runtime table:

```text
operation_key PK
dataset_id
run_mode
apply_strategy
target_reference
effective_config_hash
mutation_scope_hash
first_dataset_run_id
last_dataset_run_id
status
attempts_started
outcome_reference
last_error_code
last_error_message
version
committed_at
created_at
updated_at
```

Stable operation identity is derived from:

```text
target-operation-v1
+ dataset_id
+ run_mode
+ apply_strategy
+ target_reference
+ effective_config_hash
+ mutation_scope_hash
```

Attempt IDs are deliberately excluded.

`mutation_scope_hash` is a deterministic hash of the exact frozen target-mutation input: watermark window, CDC range/batch, snapshot candidate, append event set, file/API frozen scope, replay/backfill/rebuild scope, etc.

Canonical detailed guidance: `docs/TARGET_OPERATION_IDEMPOTENCY.md`.

## Target-operation lifecycle

```text
PREPARED -> IN_PROGRESS
IN_PROGRESS -> COMMITTED | COMMIT_UNKNOWN | NOT_COMMITTED | FAILED
COMMIT_UNKNOWN -> COMMITTED | NOT_COMMITTED
NOT_COMMITTED -> IN_PROGRESS | FAILED
COMMITTED / FAILED terminal
```

Rules:

- reserve before mutation;
- exact reservation is idempotent;
- lifecycle transitions use optimistic `version` compare-and-swap;
- stale writers fail;
- COMMITTED converges without re-execution;
- persisted IN_PROGRESS is treated as uncertain after restart/attempt loss;
- COMMIT_UNKNOWN requires reconciliation;
- only NOT_COMMITTED may be re-issued automatically;
- generic exception after target mutation begins defaults to uncertain outcome unless rollback is proven.

`outcome_reference` retains a stable pointer to target-side evidence where integration supplies one, such as job/transaction/version/commit history identity.

## Recovery protocol

Dataset recovery and target-operation recovery compose:

```text
new dataset attempt
  -> same operation key if same frozen mutation
  -> inspect durable target operation
     -> COMMITTED      converge/no target write
     -> PREPARED       start mutation
     -> NOT_COMMITTED  start mutation
     -> IN_PROGRESS    reconcile first
     -> COMMIT_UNKNOWN reconcile first
     -> FAILED         stop
```

Known retryable failure means target did not commit. Permanent deterministic failure terminates the operation. Unknown/unclassified post-mutation failure records `COMMIT_UNKNOWN` and blocks blind retry.

## Read-only operator projection

`operator.py` is the supported reference query layer above the relational schema.

`get_dataset_operational_snapshot()` returns:

- latest dataset run + attempt lineage/root/previous/reprocess identity;
- latest CaptureReceipt/native-provider correlation;
- latest `target_operation` stable key/status/attempt count/outcome/version;
- WATERMARK and/or CDC downstream progress;
- latest reconciliation;
- unreplayed quarantine counts;
- latest schema observation;
- active PENDING/RUNNING reprocess requests.

`control-plane-status` exposes the same typed model as JSON. It is read-only and does not authorize a retry or transition a COMMIT_UNKNOWN operation.

## Operator questions the production store must answer

- which dataset/attempt failed and at which stage;
- framework/domain/config/deployment identity;
- concrete capture/apply engine/profile;
- source range/snapshot/file/API/native checkpoint evidence;
- stable target operation key and frozen mutation scope;
- whether target operation is PREPARED/IN_PROGRESS/COMMIT_UNKNOWN/COMMITTED/NOT_COMMITTED/FAILED;
- which attempts touched the operation and how many starts occurred;
- target-side outcome reference/error evidence;
- row/mutation/quarantine/reconciliation counts;
- schema expected vs observed classification;
- framework source state before/after;
- recovery root/previous/request lineage.

## Current proof vs production store

Implemented/reference-tested:

- additive schema creation/idempotency;
- real v2 -> v3 append-identity migration path and v4 journal addition;
- definition/runtime promotion boundary;
- target-operation stable semantic key;
- durable relational reserve/read/lifecycle state;
- optimistic journal CAS/stale-writer failure;
- operation convergence across retry attempts;
- typed operator target-operation projection;
- runtime-state preservation during semantic materialization.

Not production-proven:

- selected production control-plane technology;
- production isolation/locking/failover semantics under parallel load;
- target-side real transaction/job/version reconciliation;
- append-only history of every operation state transition — v4 stores durable current lifecycle state;
- migration checksum/rollback/rolling compatibility;
- authenticated operator mutation/approval surface;
- retention/backup/restore and IAM/network integration.

SQLite/in-memory evidence remains deterministic reference proof only.

## Next control-plane work

1. select/certify the production repository and re-prove journal CAS/concurrency there;
2. integrate real provider/target operation evidence and recovery coordination;
3. decide whether append-only operation transition history is required by release/compliance scope;
4. add authenticated mutation workflows only if included in product scope;
5. add production migration governance once a real store is selected.
