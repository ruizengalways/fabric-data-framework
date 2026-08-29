# Guarantee Coverage — fabric-data-framework

Status: Canonical implementation-to-evidence map
Last updated: 2026-08-29

## Evidence vocabulary

- `REFERENCE` — provider-neutral semantic/contract implementation with deterministic tests.
- `ADAPTER CONTRACT` — provider boundary/evidence conversion tested without claiming a real service run.
- `CI PROVEN` — package/static/test/build workflow succeeded.
- `FABRIC PROVEN` — retained real Fabric execution/run correlation. No new hardening capability currently has this level.
- `EXTERNAL` — enterprise/platform control this repo must not invent.

## Current guarantee map

| Guarantee | Canonical owner | Evidence | Scope |
|---|---|---|---|
| Strict immutable metadata + effective-config hashing | `config.py` | config tests | REFERENCE |
| Capture/apply semantic and physical-engine independence | config/execution plan | plan/engine tests | REFERENCE |
| Unsupported engine/profile combination fails pre-mutation | `metadata/capabilities.py` | engine tests | REFERENCE |
| Composite WATERMARK + overlap | watermark runtime | watermark tests | REFERENCE |
| Bronze lineage + DQ/quarantine/accounting | bronze/quality/operations | execution tests | REFERENCE |
| APPEND append-once identity/replay/conflict semantics | `apply/append.py` | append tests | REFERENCE |
| Guarded FULL -> REPLACE | full/replace executor | full tests | REFERENCE |
| Guarded SNAPSHOT_DIFF | snapshot executor | snapshot tests | REFERENCE |
| Ordered/idempotent UPSERT/SCD1 | `apply/current_state.py` | current-state tests | REFERENCE |
| Deterministic SCD2 history | `scd2.py` | SCD2 tests | REFERENCE |
| Shared source-order taxonomy | `quality/temporal.py` | temporal + apply tests | REFERENCE |
| Shared event/valid-time taxonomy | `quality/temporal.py` | temporal + CDC-SCD2 tests | REFERENCE |
| Newer source + earlier valid time explicitly requires history rewrite | temporal + CDC-SCD2 | temporal/CDC-SCD2 tests | REFERENCE fail-closed |
| CDC I/U/D order/dedupe/frozen window | `capture/cdc.py` | CDC tests | REFERENCE |
| CDC -> UPSERT/SCD1/SCD2 | CDC apply modules | CDC apply tests | REFERENCE |
| Durable optimistic downstream CDC checkpoint | control-plane IO | checkpoint tests | REFERENCE |
| Snapshot/bootstrap -> CDC fenced handoff | bootstrap CDC | bootstrap tests | REFERENCE |
| Debezium/Kafka normalization + topic/partition/offset order | CDC adapter | adapter tests | ADAPTER CONTRACT |
| Kafka retention-aware safe resume | CDC adapter resume | resume tests | REFERENCE provider recovery |
| Fabric Copy/Activity/Dataflow/Spark capture boundary | Fabric adapter package | fake-transport tests | ADAPTER CONTRACT |
| Typed CaptureReceipt and single progress authority | contracts/capabilities | receipt/engine tests | REFERENCE |
| Bounded retry/attempt lineage/unknown-outcome tri-state | recovery runtime | recovery tests | REFERENCE |
| Quarantine REPLAY coordination | recovery replay | replay tests | REFERENCE |
| Guarded FULL_REBUILD state cutover | recovery rebuild | rebuild tests | REFERENCE |
| Typed versioned schema contract/fingerprint | `schema_contract.py` | schema tests | REFERENCE |
| EXACT/ADDITIVE_ONLY/SAFE_EVOLUTION classification | schema evolution | schema tests | REFERENCE |
| Versioned schema materialization + append-only observation evidence | delivery/control-plane IO | schema persistence tests | REFERENCE |
| Replay-stable file manifest | `capture/files.py` | file tests | REFERENCE |
| API frozen window/cursor/completeness/limit guards | `capture/api.py` | API tests | REFERENCE |
| Metadata dispatcher/dependency/failure isolation | dispatcher/orchestration | dispatcher tests | REFERENCE |
| Logical-name bounded extensions | extension registry | extension tests | REFERENCE |
| Real v2 -> v3 additive APPEND migration | `control_plane.py` | migration tests | REFERENCE |
| Typed read-only dataset operational snapshot | `operator.py` | operator tests | REFERENCE |
| Latest run + lineage/capture/progress/reconciliation/quarantine/schema/reprocess aggregation | `operator.py` | operator tests | REFERENCE |
| `control-plane-status` JSON CLI | `cli.py` | CLI tests | REFERENCE |
| Immutable v0.3.0 wheel/checksum release | release workflow | historical release evidence | RELEASE PROVEN for v0.3.0 |

## Latest CI evidence

```text
ae1eb99ab5fa9d7add5a62dda2d7448b6200d240
Actions 33225341709
268 passed
operator status API/CLI

1ee22d5828a5f53a3f9050722bdb5b7f7b28de43
Actions 33225064570
261 passed
shared temporal taxonomy wired into apply paths

c326f062ad4e6be5185f17b9e6830946967361ab
Actions 33224558393
252 passed
file/API replay-stable capture guards
```

## Required guarantees not yet complete

| Required guarantee | Current state | Next proof |
|---|---|---|
| Durable target-operation idempotency journal | executor conventions + unknown-outcome reconciliation | stable operation key + persistent lifecycle/CAS proof |
| Real Copy/Activity/Dataflow/Spark invocation | adapter contracts only | approved DEV Fabric run + retained native run ID |
| Fabric Pipeline backend | design only | real DEV orchestration |
| Live Kafka consumer seek/commit/source cursor coordination | reference adapter/resume only | live Kafka transport proof |
| Remaining native/provider downstream-failure recovery | partial | strategy-specific recovery tests + real provider evidence |
| Retroactive SCD2 history reconstruction | intentionally unsupported | explicit rewrite policy only if product scope requires it |
| Approved persistent production control-plane store | SQLAlchemy/SQLite reference | chosen store + transaction/concurrency certification |
| Operator mutation/approval workflows | read-only status exists | authenticated retry/backfill/replay/rebuild surface if required |
| Additional provider CDC adapters | Debezium/Kafka only | add only as supported scope requires |
| Enterprise IAM/network/secrets/RBAC/capacity | EXTERNAL | platform evidence |

## Ownership invariants

```text
provider/native source cursor
        !=
framework downstream semantic application checkpoint
```

```text
semantic contract
    -> framework portable implementation
    -> optional provider delegation only when capability/equivalence is certified
```

Provider success alone never proves full dataset semantic success.

## Update rule

Every new guarantee requires a canonical implementation owner, executable proof, explicit evidence level, gap update here and synchronization with `CURRENT_STATUS.md`, `PRODUCTION_REQUIREMENTS.md`, `PRODUCTION_READINESS_AUDIT.md` and relevant design docs.
