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
| Mainstream 14-pattern source/capture catalog | `capture/patterns.py` | `test_capture_patterns.py` | REFERENCE |
| Explicit change/delete/Bronze/history fidelity per pattern | `capture/patterns.py` | pattern tests | REFERENCE |
| Overstated history/delete onboarding claim fails closed | `capture/onboarding.py` | onboarding tests | REFERENCE |
| Domain CI may require every DatasetConfig to be classified | `capture-onboarding-validate` | CLI tests | REFERENCE |
| Checked-in onboarding examples remain executable typed metadata | `docs/examples/capture-patterns/` | example certification test | CI PROVEN |
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
| Delta CDF insert/delete/update pre/post -> canonical CDC | `adapters/cdc/delta_cdf.py` | Delta CDF tests | ADAPTER CONTRACT |
| Delta CDF update pre/post pairing and ambiguous same-key/commit failure | Delta CDF adapter | Delta CDF tests | ADAPTER CONTRACT |
| Delta CDF commit-version bounded checkpoint | Delta CDF adapter | Delta CDF tests | REFERENCE provider recovery contract |
| `SPARK/delta_cdf_v1` capture profile with FRAMEWORK progress | capabilities + registry | Delta CDF profile tests | REFERENCE |
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
4b20300c822e16a398342e0cc97da90ee51b035a
main Actions 33238779139
310 passed
capture catalog + onboarding CI + Delta CDF adapter/profile + executable examples

9b2278822ff4c566051c69180c8ca63b021866e4
main Actions 33225627461
SUCCESS
PR #13 production-hardening merge

ae1eb99ab5fa9d7add5a62dda2d7448b6200d240
Actions 33225341709
268 passed
operator status API/CLI
```

## Capture/history truth guarantees

The catalog explicitly prevents several common overclaims:

```text
WATERMARK_INCREMENTAL / LOOKBACK
  history <= OBSERVED_CHANGES
  hard delete visibility = NONE unless another source signal exists

CDC_NET_CURRENT / CDC_NET_OBSERVATION
  history <= BATCH_GRAIN
  intermediate changes collapsed upstream cannot be reconstructed

FULL_SNAPSHOT / SNAPSHOT_DIFF
  history <= SNAPSHOT_GRAIN when comparing recurring snapshots

CDC_FULL / TRANSACTION_LOG_CDC / DEBEZIUM_KAFKA / DELTA_CDF
  FULL_EVENT is claimable for captured changes only when ordering/completeness/retention evidence is satisfied

API_CURSOR_INCREMENTAL / FILE_INCREMENTAL
  history/delete = SOURCE_DEFINED until the source contract proves stronger semantics
```

An SCD2 target is not evidence that capture was full-fidelity.

## Required guarantees not yet complete

| Required guarantee | Current state | Next proof |
|---|---|---|
| Durable target-operation idempotency journal | executor conventions + unknown-outcome reconciliation | stable operation key + persistent lifecycle/CAS proof |
| Real Copy/Activity/Dataflow/Spark invocation | adapter contracts only | approved DEV Fabric run + retained native run ID |
| Real Delta CDF bounded read + retention recovery | deterministic adapter/profile only | approved DEV Lakehouse CDF read across versions + retention-gap drill |
| Fabric Pipeline backend | design only | real DEV orchestration |
| Live Kafka consumer seek/commit/source cursor coordination | reference adapter/resume only | live Kafka transport proof |
| Remaining native/provider downstream-failure recovery | partial | strategy-specific recovery tests + real provider evidence |
| Retroactive SCD2 history reconstruction | intentionally unsupported | explicit rewrite policy only if product scope requires it |
| Approved persistent production control-plane store | SQLAlchemy/SQLite reference | chosen store + transaction/concurrency certification |
| Operator mutation/approval workflows | read-only status exists | authenticated retry/backfill/replay/rebuild surface if required |
| Additional provider adapters | Debezium/Kafka + Delta CDF built in | add only as supported scope requires |
| Enterprise IAM/network/secrets/RBAC/capacity | EXTERNAL | platform evidence |

## Ownership invariants

```text
provider/native source cursor
        !=
framework downstream semantic application checkpoint
```

```text
source fidelity
    -> truthful history/delete ceiling
    -> Bronze policy
    -> independently selected apply semantics
    -> physical engine/profile
```

```text
semantic contract
    -> framework portable implementation
    -> optional provider delegation only when capability/equivalence is certified
```

Provider success alone never proves full dataset semantic success.

## Update rule

Every new guarantee requires a canonical implementation owner, executable proof, explicit evidence level, gap update here and synchronization with `CURRENT_STATUS.md`, `PRODUCTION_REQUIREMENTS.md`, `PRODUCTION_READINESS_AUDIT.md`, `CAPTURE_PATTERN_CATALOG.md` where relevant, and the owning design docs.
