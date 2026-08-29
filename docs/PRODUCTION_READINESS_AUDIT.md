# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-29

## Evidence model

This audit separates:

1. portable semantic implementation;
2. deterministic CI/reference certification;
3. real provider/Fabric/target integration evidence;
4. external enterprise controls.

Green Python CI proves levels 1/2 only. Adapter/reference tests do not become real service evidence until an approved provider/target execution is retained.

## Current assessment

```text
Portable semantic implementation       STRONG / broad core product slice
Deterministic certification             STRONG for implemented slices
Mainstream source onboarding            IMPLEMENTED reference
Durable target-operation idempotency    IMPLEMENTED reference
Provider adapter contract coverage      Fabric capture + Debezium/Kafka + Delta CDF
Read-only operator diagnostics          IMPLEMENTED reference
Real Fabric/Kafka/Delta/target proof     NOT YET PROVEN
External enterprise controls            EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest coherent PR #16 implementation before final docs audit:

```text
dd148a0c8e329c19809986fa9a32ed7edbe5dbfb
GitHub Actions 33239441546
323 tests passed
Python 3.11 / 3.13 / static / wheel SUCCESS
```

Latest merged source-onboarding main evidence:

```text
4b20300c822e16a398342e0cc97da90ee51b035a
GitHub Actions 33238779139
310 tests passed
```

`v0.3.0` remains the latest public release. **Do not publish v0.4.0 yet.**

## Capability assessment

| Capability | Portable/adapter code | Deterministic proof | Real service | Assessment |
|---|---:|---:|---:|---|
| Typed metadata/effective config | Yes | Yes | N/A | IMPLEMENTED |
| 14-pattern source/capture catalog + onboarding claims | Yes | Yes | N/A | IMPLEMENTED reference |
| Composite WATERMARK + overlap | Yes | Yes | No | IMPLEMENTED reference |
| Bronze/DQ/quarantine/accounting | Yes | Yes | No prod quarantine store | IMPLEMENTED reference |
| All six apply strategies | Yes | Yes | No | IMPLEMENTED reference |
| Shared source-order/event-time taxonomy | Yes | Yes | N/A | IMPLEMENTED reference |
| Retroactive SCD2 history rewrite | No | Fail-closed proof | No | INTENTIONALLY UNSUPPORTED |
| Capture/apply executor separation + capability profiles | Yes | Yes | Real profile proof pending | IMPLEMENTED contract |
| CaptureReceipt | Yes | Yes | No real native receipt | IMPLEMENTED contract |
| Fabric Copy/Activity/Dataflow/Spark capture adapters | Yes | Fake transport | No | ADAPTER CONTRACT ONLY |
| Canonical CDC + downstream checkpoint | Yes | Yes | No | IMPLEMENTED reference |
| Snapshot/bootstrap -> CDC | Yes | Yes | No real source fence | IMPLEMENTED reference |
| Debezium/Kafka normalization/resume | Yes | Yes | No live broker | ADAPTER/REFERENCE |
| Delta CDF normalization/profile | Yes | Yes | No live Lakehouse CDF read | ADAPTER/REFERENCE |
| File/API frozen replay scope | Yes | Yes | No real clients | IMPLEMENTED reference |
| Retry/attempt lineage | Yes | Yes | No provider drill | IMPLEMENTED reference |
| Quarantine REPLAY / FULL_REBUILD | Yes | Yes | No production target/payload store | IMPLEMENTED reference |
| Stable target-operation semantic key | Yes | Yes | N/A | IMPLEMENTED reference |
| Target-operation lifecycle + durable relational journal | Yes | Yes | No real target | IMPLEMENTED reference |
| Target-operation optimistic CAS | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| COMMITTED convergence without re-write | Yes | Yes | No real target | IMPLEMENTED reference |
| IN_PROGRESS/COMMIT_UNKNOWN reconciliation gate | Yes | Yes | No real target | IMPLEMENTED reference |
| Same operation key across retry attempts | Yes | Yes | No real target | IMPLEMENTED reference |
| Generic post-mutation exception -> unknown outcome | Yes | Yes | No real target | IMPLEMENTED fail-closed |
| Control-plane v4 target_operation table | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Operator latest target-operation projection | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Schema contract/evolution/evidence | Yes | Yes | No physical migration | IMPLEMENTED reference |
| Typed operator status + JSON CLI | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Approved persistent production control plane | Reference only | SQLite tests | No | GAP |
| Real target transaction/outcome reconciliation | Contract only | Fake/reference | No | P0 GAP |
| Fabric Pipeline backend | Design only | No | No | P0 GAP |
| Real Fabric/Kafka/Delta transports | Interfaces/adapters only | No live call | No | P0 GAP |
| Approved DEV hybrid execution | No | No | No | P0 GAP |

## Target-operation readiness

### What is now proven deterministically

- operation identity is stable across attempts because `dataset_run_id`/attempt are excluded;
- changes to target, apply strategy, run mode, effective config or frozen mutation scope change the key;
- reservation is durable/idempotent;
- lifecycle transitions are fail-closed;
- stale optimistic versions cannot overwrite newer journal state;
- known retryable NOT_COMMITTED failure can re-enter IN_PROGRESS;
- COMMITTED is terminal and later attempts converge without target mutation;
- persisted IN_PROGRESS is treated as uncertain after restart/attempt loss;
- COMMIT_UNKNOWN cannot be blindly retried;
- reconciliation may transition uncertain outcome to COMMITTED or NOT_COMMITTED;
- an unclassified exception after mutation begins is treated as unknown rather than assumed rollback;
- operator status exposes the latest operation and uncertain outcome.

### What mutation_scope_hash means

The journal does not generate a random retry token. The executor must hash the exact frozen semantic target input. Canonical guide/examples are in `docs/TARGET_OPERATION_IDEMPOTENCY.md` for:

```text
WATERMARK
CDC / Debezium / Delta CDF
FULL -> REPLACE
SNAPSHOT_DIFF
APPEND batch
File incremental
API cursor incremental
BACKFILL
Quarantine REPLAY
FULL_REBUILD
```

This requirement is essential: if retry recomputes a different source/candidate scope, it is a different operation and must not reuse the old key.

### Remaining target-operation gaps

1. no retained real Fabric Warehouse/Lakehouse/SQL transaction/job/version reconciliation;
2. final production control-plane store is unselected, so CAS/isolation/failover are reference-proven only;
3. current v4 table stores durable current lifecycle state, not append-only history of every transition;
4. real execution backends do not yet all construct mutation_scope_hash from provider evidence;
5. no authenticated operator workflow yet transitions/reconciles a COMMIT_UNKNOWN operation.

These limit production integration claims but no longer leave portable target-operation identity/retry semantics unspecified.

## Source-fidelity readiness

The framework prevents common overclaims such as watermark == full history, net CDC == full event history, incomplete snapshot absence == delete, or file/API transport == semantic history guarantee. `SOURCE_DEFINED` remains deliberate where the source contract must supply truth.

## Delta CDF readiness

Delta CDF adapter/profile proves typed row-change normalization, commit-version bounds, overlap replay and ambiguous same-key/commit fail-closed behavior. It does not prove real Lakehouse CDF enablement, retention, auth, performance or version-gap recovery.

Correct label remains `ADAPTER CONTRACT + REFERENCE CHECKPOINT SEMANTICS`.

## Strong portable guarantees

### Replay-stable source acquisition

WATERMARK/CDC/FULL/SNAPSHOT plus file/API/CDF contracts freeze source scope required for deterministic retry/replay.

### Target-mutation convergence

Frozen mutation scope is transformed into a stable operation key before target mutation. Unknown outcome is now durable state rather than only an exception-classification convention.

### Schema safety

Schema changes are checked against a source-controlled versioned contract; only explicitly certified widening/relaxation is compatible.

### Recovery and operability

Unknown target mutation is reconciled before target retry. REPLAY and FULL_REBUILD are explicit audited modes. Operator snapshots include target-operation state together with source progress and runtime evidence.

## Remaining release-significant gaps

### P0 integration proof

1. actual Fabric/Kafka/Delta transports;
2. Fabric Pipeline backend;
3. real target mutation/outcome reconciliation evidence;
4. approved DEV hybrid execution retaining source/native/target IDs and framework correlation.

### P0/P1 runtime durability

1. selection/certification of production control-plane store with journal CAS/isolation/migration governance;
2. remaining native/provider downstream-failure resume and live Kafka/Delta recovery;
3. target-side operation marker/transaction integration where needed;
4. authenticated operator mutation workflows if included in release scope;
5. append-only operation transition audit only if compliance/release scope requires it.

## Control-plane audit

Current development schema is v4:

```text
v1 phase1_initial_control_plane_schema
v2 execution_policy_ordering_capture_receipt_recovery_and_cdc
v3 append_identity_semantics
v4 target_operation_idempotency_journal
```

`target_operation` is environment-local runtime correctness state. It is not promoted between environments.

`DatasetCaptureSelection` remains a Git/CI companion and did not cause this v4; v4 exists because durable target-mutation outcome is runtime correctness state.

## Fabric/provider evidence boundary

Fabric capture adapters use injected/fake transports; Debezium/Kafka and Delta CDF prove normalization/reference recovery behavior. Target-operation tests use deterministic reference mutations and reconciliation callbacks. None prove live authentication, API versions, Kafka rebalance/commit, Delta retention, target transaction history or real run IDs.

## External evidence this repo must not fake

Fabric capacity/SKU/throttling, tenant/workspace provisioning, Entra/RBAC, gateway/private networking, secrets, source CDC/CDF retention, broker/database/API access, production target transaction retention, backup/restore, monitoring/on-call, privacy/retention and enterprise change controls remain external evidence.

## Release gate

Before the next public release:

```text
code == tests == canonical docs == control-plane/release contract
```

and product promises must match retained real integration evidence.

Current decision: **release remains blocked. Portable target-operation idempotency is implemented reference-level in PR #16; the next significant gaps are real provider/target integration and production control-plane certification.**
