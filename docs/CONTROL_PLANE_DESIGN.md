# Control Plane and Metadata-Driven Runtime Design

Status: Canonical detailed design
Last updated: 2026-08-29

## Purpose

The control plane stores durable semantic definitions, environment-local runtime state and operational evidence for metadata-driven framework execution. It is an operational state store, not a business warehouse and not an unrestricted mutable configuration database.

Backend qualification is defined separately in `CONTROL_PLANE_CERTIFICATION.md`.

## Core principles

1. Git/source-controlled domain definitions are the semantic source of truth.
2. Deployment materializes a runtime-readable semantic snapshot.
3. Runtime overrides are allow-listed operational controls only.
4. Effective config is immutable and deterministically hashed per attempt.
5. Capture/apply semantics and physical engines are separate decisions.
6. One physical capture has one authoritative source-progress owner.
7. Native/external capture is correlated through immutable `CaptureReceipt` evidence.
8. Runtime state/evidence is environment-local and never promoted.
9. Dataset is the default failure/retry boundary.
10. Unknown target outcome is reconciled before retry.
11. Semantic target mutations have durable attempt-independent operation identity.
12. State progression is gated by target commit + required reconciliation.
13. Schema contract is promotable; schema observation is environment-local.
14. Operator-facing reads use typed projections instead of raw table coupling.
15. Physical control-plane products are replaceable only if they pass the same relational/concurrency certification contract.

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
CONTROL_PLANE_SCHEMA_VERSION = 4
```

Migration history:

```text
v1 phase1_initial_control_plane_schema
v2 execution_policy_ordering_capture_receipt_recovery_and_cdc
v3 append_identity_semantics
v4 durable_target_operation_journal
```

v3 explicitly adds `load_policy.append_identity` for an existing v2 store before recording migration success. v4 adds the durable target-operation current state and append-only event journal. `create_all()` alone is not treated as a general ALTER migration mechanism.

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
target_operation
target_operation_event
deployment_history
```

These never move DEV -> UAT -> PROD as deployment artifacts.

`cdc_checkpoint` records framework downstream CDC semantic application, not native/provider source cursor authority. `capture_receipt` retains native/provider correlation. `schema_change` records observation without rewriting source-controlled schema. `quarantine_batch` stores lineage/location/count, not large payloads. `target_operation` and `target_operation_event` make ambiguous target outcomes and safe retry decisions durable across physical attempts.

## State/progress ownership

Framework-owned progress:

```text
read state/version
  -> freeze source boundary
  -> claim semantic target operation
  -> execute or reconcile target mutation
  -> required reconciliation / DQ
  -> commit next framework state/checkpoint
```

Native/external progress:

```text
provider exposes source/native position
  -> framework derives bounded read from downstream state
  -> CaptureReceipt records correlation
  -> framework downstream semantic apply
  -> framework commits semantic state
  -> provider transport cursor may advance afterwards where applicable
```

No dual semantic checkpoint truth is allowed. For example, a Kafka consumer-group offset is transport state; it cannot override a framework downstream CDC checkpoint.

## Recovery protocol

Failure classes are `RETRYABLE`, `NON_RETRYABLE` and `UNKNOWN_OUTCOME`. Unknown target mutation resolves to `COMMITTED`, `NOT_COMMITTED` or `UNRESOLVED` before any retry decision. Quarantine `REPLAY` and `FULL_REBUILD` are explicit audited flows.

Durable target-operation state machine:

```text
new -> IN_PROGRESS
IN_PROGRESS -> SUCCEEDED | UNKNOWN | NOT_COMMITTED
UNKNOWN -> SUCCEEDED | UNKNOWN | NOT_COMMITTED
NOT_COMMITTED -> IN_PROGRESS
SUCCEEDED -> terminal
```

A re-entered `IN_PROGRESS` or `UNKNOWN` operation is reconciliation-required. Only durable `NOT_COMMITTED` evidence allows a later CAS claim to execute again.

Provider recovery contracts additionally fail closed on Kafka source-retention gaps and Delta CDF version-retention gaps. See `TARGET_OPERATION_IDEMPOTENCY.md` and `PROVIDER_NATIVE_RECOVERY.md`.

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

The operator API is intentionally typed so a future repository refactor can replace direct query mechanics without changing runbook semantics.

## Backend certification boundary

`control_plane_certification.py` qualifies the relational engine backing the current SQLAlchemy primitives; it does not add another state repository.

Built-in profiles:

```text
sqlite_reference_v1      reference only
fabric_sql_database_v1   production candidate
azure_sql_database_v1    production candidate
```

Certification is deliberately split:

```text
explicit migration
  -> static schema/dialect/history checks
  -> temporary transaction + CAS conformance probes
  -> external IAM/network/restore/availability/monitoring/retention evidence
  -> production certification
```

SQLite can pass deterministic/reference conformance but can never be production-certified.

The CLI is:

```text
fabric-framework control-plane-certify \
  --database-url ... \
  --profile ... \
  [--run-conformance] \
  [--external-evidence ...] \
  [--require-reference-certified | --require-production-certified]
```

Certification does not silently run migrations. `control-plane-migrate` remains the explicit state-changing deployment step.

## Source-boundary evidence

File/API guardrails currently remain provider-neutral capture contracts rather than dedicated relational index tables. Future durable indexing should be added through explicit environment-local migrations if real provider integration needs it; do not overload `CaptureReceipt` with arbitrary opaque state.

## Operator questions the production store must answer

- which dataset/attempt failed and at which stage;
- framework/domain/config/deployment identity;
- concrete capture/apply engine/profile;
- source range/snapshot/file manifest/API window/native run/checkpoint evidence;
- row/mutation/quarantine/reconciliation counts;
- schema expected vs observed classification;
- state before/after and committing attempt;
- recovery root/previous/request lineage;
- target-operation semantic key, state and event history;
- provider-native evidence used to resolve an ambiguous target mutation.

## Current proof vs production store

Implemented/reference-tested:

- additive schema creation/idempotency through v4;
- v2 -> v3 additive append-identity migration and v4 journal creation;
- definition/runtime promotion boundary;
- semantic materialization including schema and APPEND identity;
- CaptureReceipt/recovery/CDC/schema evidence;
- runtime-state preservation during materialization;
- CDC checkpoint expected-version CAS;
- target-operation expected-version CAS + append-only event journal;
- typed read-only operator aggregation and JSON CLI;
- backend certification contract and temporary rollback/CAS probe suite.

Still requiring real production evidence:

- an approved persistent production control-plane instance;
- concurrent/load/failover behavior in the selected service;
- authentication/RBAC and network/security integration;
- backup/restore drill and recovery objectives;
- monitoring/alerting and retention governance;
- production migration/rolling-compatibility procedures where required by release scope.

SQLite/in-memory remain deterministic reference proof only.

## Next control-plane work

1. run the certification suite against the selected real Fabric SQL Database or Azure SQL Database candidate and retain the report/evidence;
2. wire authenticated connection/environment binding into deployment without placing credentials in source control;
3. add production migration governance for the selected backend where operational requirements demand it;
4. add authenticated mutation workflows only if included in product scope;
5. persist richer provider-native evidence only where real transports prove it is required.
