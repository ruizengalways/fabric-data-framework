# Current Status — fabric-data-framework

Last updated: 2026-08-29

## Current phase and release gate

`v0.3.0` remains the latest immutable public framework release. Source version `0.4.0` is an unreleased development line. **Do not publish v0.4.0 yet.**

Merged mainline baselines:

```text
PR #13 -> 9b2278822ff4c566051c69180c8ca63b021866e4
production-hardening product slice

PR #14 -> 4b20300c822e16a398342e0cc97da90ee51b035a
main Actions 33238779139
310 tests passed
mainstream capture/onboarding + Delta CDF

PR #15 -> 07923edfa30fe0e5957d98a68a224579816c6b50
post-merge durable docs checkpoint
```

Active work is PR #16 on `feature/target-operation-journal`. The durable target-operation idempotency slice is now implemented at REFERENCE/CI level and is being exact-head audited before merge.

Latest coherent implementation evidence before the final docs audit:

```text
dd148a0c8e329c19809986fa9a32ed7edbe5dbfb
GitHub Actions 33239441546
323 tests passed
Python 3.11 + 3.13 + static + wheel SUCCESS
```

No current hardening capability is yet `FABRIC PROVEN` through a retained real workspace/provider target execution.

## Product target

After an enterprise installs a released framework wheel, routine datasets should onboard through:

```text
source-controlled DatasetConfig
+ source/capture truth classification
+ environment bindings
+ capability profiles
+ bounded logical-name extensions
```

rather than edits to `fabric-data-framework` per dataset.

## Mainstream source/capture model

Canonical guide: `docs/CAPTURE_PATTERN_CATALOG.md`.

Fourteen executable patterns cover the common source families:

```text
FULL_SNAPSHOT
WATERMARK_INCREMENTAL
WATERMARK_LOOKBACK
WATERMARK_TOMBSTONE
CDC_NET_CURRENT
CDC_NET_OBSERVATION
CDC_FULL
TRANSACTION_LOG_CDC
DEBEZIUM_KAFKA
DELTA_CDF
EVENT_SOURCE
SNAPSHOT_DIFF
API_CURSOR_INCREMENTAL
FILE_INCREMENTAL
```

Key invariant:

> **Capture fidelity is an upper bound on truthful history fidelity.**

`DatasetCaptureSelection` and `capture-onboarding-validate --require-all` let domain CI reject overstated history/delete claims.

Executable examples live in `docs/examples/capture-patterns/`.

## Durable target-operation idempotency

Canonical guide: `docs/TARGET_OPERATION_IDEMPOTENCY.md`.

A dataset retry attempt is not the same identity as the target mutation it is retrying:

```text
dataset_run_id
  = one execution attempt

TargetOperation.operation_key
  = one frozen semantic target mutation across attempts/restarts
```

The stable operation key is derived from:

```text
target-operation-v1
+ dataset_id
+ run_mode
+ apply_strategy
+ target_reference
+ effective_config_hash
+ mutation_scope_hash
```

`mutation_scope_hash` must represent the exact frozen input/candidate being applied. It deliberately excludes attempt IDs and current timestamps.

Implemented lifecycle:

```text
PREPARED -> IN_PROGRESS
IN_PROGRESS -> COMMITTED | COMMIT_UNKNOWN | NOT_COMMITTED | FAILED
COMMIT_UNKNOWN -> COMMITTED | NOT_COMMITTED
NOT_COMMITTED -> IN_PROGRESS | FAILED
COMMITTED / FAILED terminal
```

Core safety rule:

> **Only `NOT_COMMITTED` is eligible for target re-execution.**

Existing `COMMITTED` converges without another target write. Persisted `IN_PROGRESS` or `COMMIT_UNKNOWN` must be reconciled before retry. A generic exception after target mutation begins is conservatively classified as unknown outcome rather than assumed rollback.

The retry wrapper creates a new `dataset_run_id` per attempt while retaining the same `operation_key` for the same frozen mutation.

## Control plane v4

Current development schema:

```text
CONTROL_PLANE_SCHEMA_VERSION = 4
v1 phase1_initial_control_plane_schema
v2 execution_policy_ordering_capture_receipt_recovery_and_cdc
v3 append_identity_semantics
v4 target_operation_idempotency_journal
```

v4 adds environment-local runtime state:

```text
target_operation
```

It records the stable operation identity, first/last dataset attempt, lifecycle status, attempts started, outcome evidence, last error, optimistic concurrency `version` and commit timestamp.

`target_operation` is never promoted between DEV/UAT/PROD.

`DatasetCaptureSelection` remains a Git/CI onboarding companion and is still not a control-plane table.

## Operator surface

`get_dataset_operational_snapshot()` / `control-plane-status` now include:

```text
latest dataset run + attempt lineage
latest CaptureReceipt/native-provider correlation
latest target operation/idempotency outcome
watermark / CDC downstream progress
latest reconciliation
quarantine backlog
latest schema observation
active reprocess requests
```

`latest_target_operation` exposes operation key/status/apply/target/attempt count/outcome reference/error/version so on-call can see `COMMIT_UNKNOWN` without raw SQL.

This remains a typed reference operator surface over the current relational contract; it does not certify SQLite as the production control-plane technology.

## Implemented development runtime

Current unreleased codebase provides:

- immutable metadata/effective config + allow-listed overrides;
- 14-pattern source-fidelity onboarding catalog + CI truth claims;
- independent capture/apply semantics, engines and progress ownership;
- composite WATERMARK + overlap;
- Bronze lineage, DQ/quarantine and no-silent-loss accounting;
- APPEND, REPLACE, UPSERT, SCD1, SCD2, SNAPSHOT_DIFF;
- canonical CDC + downstream checkpoints + snapshot/bootstrap handoff;
- Debezium/Kafka and Delta CDF provider adapters;
- Fabric capture adapter contracts;
- replay-stable file manifests and API frozen windows;
- bounded retry, attempt lineage, quarantine REPLAY and FULL_REBUILD;
- durable target-operation idempotency journal + unknown-outcome convergence;
- schema contracts/evolution/evidence;
- shared source-order/event-time taxonomy;
- control-plane v4 + typed read-only operator API/CLI;
- immutable release/delivery contracts.

## Evidence boundary

Reference/CI proof does not equal real provider proof. Still missing are real Fabric/Kafka/Delta transports, authentication/network bindings, Fabric Pipeline orchestration, live Kafka seek/commit, real Delta CDF bounded reads/retention drills, real target transaction/commit reconciliation and an approved DEV hybrid execution retaining provider/native/target correlation.

The current `target_operation` lifecycle is durable in the relational reference implementation and CAS-tested, but final production-database isolation/failover behavior is not yet certified.

## Exact next implementation sequence

After PR #16 is merged:

1. complete remaining native/provider downstream-failure recovery, including real Kafka cursor coordination and Delta CDF retention-gap recovery;
2. select/certify the production control-plane repository and re-prove target-operation CAS/transaction behavior there;
3. implement real Fabric/Kafka/Delta transports and Fabric Pipeline backend;
4. integrate real target adapters with mutation-scope generation and COMMITTED/NOT_COMMITTED reconciliation evidence;
5. prove approved DEV hybrid executions retaining source/native/target correlation;
6. add provider adapters only when supported scope requires them;
7. exact-candidate audit/docs/CI and next immutable release decision.

## Durable project memory

New conversations should read in this order:

```text
docs/CURRENT_STATUS.md
docs/PRODUCTION_READINESS_AUDIT.md
docs/GUARANTEE_COVERAGE.md
docs/PROJECT_BLUEPRINT.md
docs/PRODUCTION_REQUIREMENTS.md
docs/CAPTURE_PATTERN_CATALOG.md
docs/TARGET_OPERATION_IDEMPOTENCY.md
docs/EXECUTION_ENGINE_STRATEGY.md
docs/FABRIC_EXECUTION_MODEL.md
docs/CDC_DESIGN.md
docs/CONTROL_PLANE_DESIGN.md
docs/REPOSITORY_STRUCTURE.md
docs/CICD_DESIGN.md
docs/ECOSYSTEM_BLUEPRINT.md
```

If docs disagree with code/tests, inspect implementation and repair docs before continuing.
