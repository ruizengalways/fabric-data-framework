# Guarantee Coverage — fabric-data-framework

Status: Canonical implementation-to-evidence map
Last updated: 2026-08-29

## Evidence vocabulary

- `REFERENCE` — provider-neutral semantic/contract implementation with deterministic tests.
- `ADAPTER CONTRACT` — provider boundary/evidence conversion tested without claiming a real service run.
- `CI PROVEN` — package/static/test/build workflow succeeded.
- `FABRIC PROVEN` — retained real Fabric execution/run correlation. No current hardening capability has this level yet.
- `EXTERNAL` — enterprise/platform control this repo must not invent.

## Current guarantee map

| Guarantee | Canonical owner | Evidence | Scope |
|---|---|---|---|
| Strict immutable metadata + effective-config hashing | `config.py` | config tests | REFERENCE |
| Capture/apply semantic and physical-engine independence | config/execution plan | plan/engine tests | REFERENCE |
| Mainstream 14-pattern source/capture catalog | `capture/patterns.py` | capture-pattern tests | REFERENCE |
| Explicit change/delete/Bronze/history fidelity | capture pattern/onboarding | pattern/onboarding tests | REFERENCE |
| Domain CI can require source classification | `capture-onboarding-validate` | CLI tests | REFERENCE |
| Checked-in onboarding examples remain executable | `docs/examples/capture-patterns/` | example tests | CI PROVEN |
| Unsupported engine/profile fails pre-mutation | capabilities | engine tests | REFERENCE |
| Composite WATERMARK + overlap | watermark runtime | watermark tests | REFERENCE |
| Bronze lineage + DQ/quarantine/accounting | Bronze/quality | execution tests | REFERENCE |
| APPEND append-once identity/replay/conflict | `apply/append.py` | append tests | REFERENCE |
| Guarded FULL -> REPLACE | full/replace executor | full tests | REFERENCE |
| Guarded SNAPSHOT_DIFF | snapshot executor | snapshot tests | REFERENCE |
| Ordered/idempotent UPSERT/SCD1 | `apply/current_state.py` | current-state tests | REFERENCE |
| Deterministic SCD2 history | SCD2 modules | SCD2 tests | REFERENCE |
| Shared source-order/event-time taxonomy | temporal quality | temporal/apply tests | REFERENCE |
| CDC I/U/D order/dedupe/frozen window | `capture/cdc.py` | CDC tests | REFERENCE |
| CDC -> UPSERT/SCD1/SCD2 | CDC apply modules | CDC apply tests | REFERENCE |
| Durable optimistic downstream CDC checkpoint | control-plane IO | checkpoint tests | REFERENCE |
| Snapshot/bootstrap -> CDC fenced handoff | bootstrap CDC | bootstrap tests | REFERENCE |
| Debezium/Kafka normalization + safe resume | CDC adapter | adapter/resume tests | ADAPTER CONTRACT / REFERENCE |
| Delta CDF -> canonical CDC + bounded commit checkpoints | Delta CDF adapter | Delta CDF tests | ADAPTER CONTRACT / REFERENCE |
| Fabric Copy/Activity/Dataflow/Spark capture boundary | Fabric adapters | fake-transport tests | ADAPTER CONTRACT |
| Typed CaptureReceipt and single progress authority | contracts/capabilities | receipt/engine tests | REFERENCE |
| Bounded retry + attempt lineage | recovery runtime | recovery tests | REFERENCE |
| Quarantine REPLAY / guarded FULL_REBUILD | recovery modules | replay/rebuild tests | REFERENCE |
| Stable target operation key excludes attempt identity | `contracts/target_operation.py` | journal tests | REFERENCE |
| Frozen mutation scope participates in operation identity | target-operation contract | key/scope tests + documented executor contract | REFERENCE contract |
| Durable target-operation reserve/read state | `target_operation_io.py` | relational journal tests | REFERENCE |
| Target-operation lifecycle fail-closed transitions | target-operation contract/runtime | journal/recovery tests | REFERENCE |
| Optimistic target-operation CAS/stale-writer rejection | `target_operation_io.py` | journal tests | REFERENCE |
| Existing COMMITTED operation converges without target rewrite | `recovery/target_operation.py` | recovery tests | REFERENCE |
| Persisted IN_PROGRESS/COMMIT_UNKNOWN reconciled before replay | target-operation recovery | recovery tests | REFERENCE |
| Only NOT_COMMITTED is automatically re-executable | target-operation recovery | recovery tests | REFERENCE |
| New dataset attempts retain one operation key for same mutation | retry wrapper | recovery tests | REFERENCE |
| Generic post-mutation exception defaults to COMMIT_UNKNOWN | target-operation recovery | recovery tests | REFERENCE fail-closed |
| Control-plane v4 environment-local target-operation journal | `control_plane.py` | migration/journal tests | REFERENCE |
| Operator exposes latest target-operation state | `operator.py` | operator target-operation test | REFERENCE |
| Typed schema/evolution/evidence | schema modules | schema tests | REFERENCE |
| Replay-stable file manifest | `capture/files.py` | file tests | REFERENCE |
| API frozen window/cursor guards | `capture/api.py` | API tests | REFERENCE |
| Metadata dispatcher/failure isolation | dispatcher/orchestration | dispatcher tests | REFERENCE |
| Logical-name bounded extensions | extension registry | extension tests | REFERENCE |
| Typed read-only dataset operational snapshot + CLI | operator/CLI | operator/CLI tests | REFERENCE |
| Immutable v0.3.0 wheel/checksum release | release workflow | historical release evidence | RELEASE PROVEN for v0.3.0 |

## Latest deterministic evidence

Target-operation implementation baseline before final docs audit:

```text
dd148a0c8e329c19809986fa9a32ed7edbe5dbfb
GitHub Actions 33239441546
323 passed
Python 3.11 + 3.13 + static + wheel SUCCESS
```

Merged source-onboarding baseline:

```text
4b20300c822e16a398342e0cc97da90ee51b035a
main Actions 33238779139
310 passed
```

## Target-operation guarantee boundary

The portable runtime now guarantees:

```text
same frozen semantic mutation
  -> same operation key across dataset attempts

COMMITTED
  -> converge without blind target rewrite

IN_PROGRESS after restart/attempt loss
  -> uncertain; reconcile before replay

COMMIT_UNKNOWN
  -> reconcile before replay

NOT_COMMITTED
  -> retry may reissue same operation

stale journal version
  -> CAS conflict; no silent overwrite
```

It does **not** claim that a real Fabric Warehouse/Lakehouse/SQL target can already prove transaction outcome. Real target adapters must supply target-specific mutation scope and reconciliation evidence.

## Capture/history truth guarantees

```text
WATERMARK_INCREMENTAL / LOOKBACK
  history <= OBSERVED_CHANGES
  hard delete visibility = NONE without another signal

CDC_NET_CURRENT / CDC_NET_OBSERVATION
  history <= BATCH_GRAIN

FULL_SNAPSHOT / SNAPSHOT_DIFF
  history <= SNAPSHOT_GRAIN

CDC_FULL / TRANSACTION_LOG_CDC / DEBEZIUM_KAFKA / DELTA_CDF
  FULL_EVENT only when ordering/completeness/retention is proven

API_CURSOR_INCREMENTAL / FILE_INCREMENTAL
  history/delete = SOURCE_DEFINED until source contract proves more
```

An SCD2 target does not itself prove full capture fidelity.

## Required guarantees not yet complete

| Required guarantee | Current state | Next proof |
|---|---|---|
| Real target mutation-scope/outcome reconciliation | portable contract only | Fabric/Lakehouse/Warehouse/SQL target integration + retained transaction/job/version evidence |
| Production control-plane journal concurrency | SQLite/SQLAlchemy CAS reference | selected store + concurrency/isolation/failover certification |
| Append-only target-operation transition history | current-state journal only | add only if release/compliance scope requires it |
| Real Copy/Activity/Dataflow/Spark invocation | adapter contracts only | approved DEV Fabric run + retained native run ID |
| Real Delta CDF read + retention recovery | deterministic adapter/profile only | approved DEV Lakehouse CDF proof |
| Fabric Pipeline backend | design only | real DEV orchestration |
| Live Kafka seek/commit coordination | reference resume only | live Kafka transport proof |
| Remaining native/provider downstream-failure recovery | partial | strategy-specific recovery + provider evidence |
| Retroactive SCD2 history reconstruction | intentionally unsupported | explicit rewrite policy if required |
| Approved persistent production control-plane store | SQLAlchemy/SQLite reference | chosen store certification |
| Operator mutation/approval workflows | read-only status exists | authenticated recovery surface if required |
| Enterprise IAM/network/secrets/RBAC/capacity | EXTERNAL | platform evidence |

## Ownership invariants

```text
provider/native source cursor
        !=
framework watermark / cdc_checkpoint
        !=
target_operation outcome/idempotency
        !=
dataset attempt identity
```

```text
source fidelity
    -> truthful history/delete ceiling
    -> Bronze policy
    -> independently selected apply semantics
    -> physical engine/profile
```

```text
frozen mutation scope
    -> stable target operation key
    -> reserve before mutation
    -> reconcile unknown outcome
    -> retry only when NOT_COMMITTED
```

Provider success alone never proves full dataset semantic success. Target operation COMMITTED alone never bypasses required reconciliation/state gates.

## Update rule

Every new guarantee requires a canonical implementation owner, executable proof, explicit evidence level, gap update here and synchronization with `CURRENT_STATUS.md`, `PRODUCTION_REQUIREMENTS.md`, `PRODUCTION_READINESS_AUDIT.md` and the owning design guide.
