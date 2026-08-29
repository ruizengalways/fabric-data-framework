# Guarantee Coverage — fabric-data-framework

Status: Canonical implementation-to-evidence map
Last updated: 2026-08-29

## 1. Evidence vocabulary

- `REFERENCE` — provider-neutral semantics/contracts implemented and deterministically tested.
- `ADAPTER CONTRACT` — provider adapter boundary/evidence conversion tested deterministically; no real service call implied.
- `CI PROVEN` — package/static/test/build workflow succeeded in GitHub Actions.
- `FABRIC PROVEN` — retained real Microsoft Fabric execution/run correlation. No new hardening capability currently has this level.
- `EXTERNAL` — enterprise/platform control this repository must not invent.

## 2. Current guarantee map

| Guarantee | Canonical owner | Representative evidence | Scope |
|---|---|---|---|
| Strict immutable dataset metadata | `config.py` | config tests | REFERENCE |
| Runtime override allow-list + deterministic effective-config hash | `config.py` | config tests | REFERENCE |
| Capture/apply semantic independence | `config.py` | config/execution-plan tests | REFERENCE |
| Independent capture/apply executor selection | `ExecutionPolicy`, `execution_plan.py` | stage tests | REFERENCE |
| Unsupported engine/profile/semantic combination fails before mutation | `metadata/capabilities.py` | engine tests | REFERENCE |
| Composite WATERMARK ordering/overlap | `watermark.py` | watermark tests | REFERENCE |
| Bronze lineage envelope | `bronze.py` | execution tests | REFERENCE |
| Row DQ/quarantine + no-silent-loss accounting | `quality/`, `operations.py` | quality/execution tests | REFERENCE |
| APPEND exact replay is idempotent | `apply/append.py` | append tests | REFERENCE |
| APPEND conflicting identity fails closed | `apply/append.py` | append tests | REFERENCE |
| APPEND identity is source-controlled and materialized | `LoadPolicy`, `delivery.py`, control-plane v3 | config/delivery/migration tests | REFERENCE |
| Guarded FULL -> REPLACE | capture/apply/execution modules | full-replace tests | REFERENCE |
| Complete SNAPSHOT + guarded SNAPSHOT_DIFF | snapshot modules | snapshot tests | REFERENCE |
| Ordered/idempotent SCD1 | `apply/current_state.py`, `apply/scd1.py` | SCD1 tests | REFERENCE |
| Ordered/idempotent UPSERT | `apply/current_state.py`, `apply/upsert.py` | UPSERT tests | REFERENCE |
| Deterministic SCD2 one-current-row invariant | `scd2.py` | SCD2 tests | REFERENCE |
| CDC -> UPSERT/SCD1/SCD2 | `apply/cdc.py`, `apply/cdc_scd2.py` | CDC apply tests | REFERENCE |
| Metadata-driven dependencies/concurrency/failure isolation | dispatcher/orchestration | dispatcher tests | REFERENCE |
| Immutable concrete ExecutionPlan | `contracts/execution_plan.py` | execution-plan tests | REFERENCE |
| One physical capture progress authority | `ProgressOwner` + capability validation | engine tests | REFERENCE |
| Typed native/external capture handoff | `CaptureReceipt` | receipt/control-plane tests | REFERENCE |
| Logical-name bounded extensions | extension registry/config | extension tests | REFERENCE |
| Fabric Copy Job/Copy Activity/Dataflow/Spark capture adapter boundary | `adapters/fabric/` | fabric-adapter tests | ADAPTER CONTRACT |
| Native FAILED/CANCELLED/UNKNOWN never yields success receipt | Fabric adapter | fabric-adapter tests | ADAPTER CONTRACT |
| Framework-bounded native movement verifies exact source range | Fabric adapter | fabric-adapter tests | ADAPTER CONTRACT |
| Conservative retry classification | `recovery/runtime.py` | recovery tests | REFERENCE |
| Attempt lineage and bounded retry | recovery runtime/contracts | recovery tests | REFERENCE |
| Unknown target commit reconciled before retry | recovery runtime | recovery tests | REFERENCE |
| Quarantine REPLAY validates original evidence/payload identity | `recovery/replay.py` | replay tests | REFERENCE |
| Quarantine replay marker advances only after state gate | recovery/control-plane IO | replay tests | REFERENCE |
| FULL_REBUILD stable destructive identity | `recovery/rebuild.py` | rebuild tests | REFERENCE |
| FULL_REBUILD optimistic state cutover after target/reconciliation gate | rebuild contracts/runtime | rebuild tests | REFERENCE |
| Canonical CDC I/U/D envelope/order/dedupe/window | `capture/cdc.py` | CDC tests | REFERENCE |
| Durable CDC apply checkpoint + optimistic concurrency | control plane/IO | checkpoint tests | REFERENCE |
| Snapshot/bootstrap -> CDC no-gap/no-double-apply fence | `capture/bootstrap_cdc.py` | bootstrap tests | REFERENCE |
| Debezium/Kafka c/u/d envelope maps to canonical CDC | `adapters/cdc/debezium_kafka.py` | adapter tests | ADAPTER CONTRACT |
| Kafka topic/partition/offset is canonical provider order | Debezium adapter | adapter tests | ADAPTER CONTRACT |
| Kafka safe resume derives from framework applied checkpoint | `adapters/cdc/resume.py` | resume tests | REFERENCE provider recovery |
| Kafka retention gap fails closed | `adapters/cdc/resume.py` | resume tests | REFERENCE provider recovery |
| Versioned typed schema contract | `schema_contract.py` | schema tests | REFERENCE |
| Stable schema fingerprint independent of declaration order | `schema_contract.py` | schema tests | REFERENCE |
| EXACT / ADDITIVE_ONLY / SAFE_EVOLUTION compatibility classification | `quality/schema_evolution.py` | schema tests | REFERENCE |
| Narrowing/removal/required-addition/uncertified type conversion fails closed | schema evolution | schema tests | REFERENCE |
| Versioned dataset contracts materialize without overwriting prior versions | `delivery.py`, `dataset_contract` | delivery/schema tests | REFERENCE |
| Runtime schema observations are append-only environment-local evidence | `control_plane_io.py`, `schema_change` | schema persistence tests | REFERENCE |
| File discovery must be explicitly complete before freeze | `capture/files.py` | file capture tests | REFERENCE |
| File URI/version ambiguity and non-ready objects fail closed | `capture/files.py` | file capture tests | REFERENCE |
| Retry/replay requires same frozen file-manifest fingerprint | `capture/files.py` | file capture tests | REFERENCE |
| API bounds/filter semantics freeze before pagination | `capture/api.py` | API capture tests | REFERENCE |
| API cursor chain/page numbering/cycle detection | `capture/api.py` | API capture tests | REFERENCE |
| API page/record limits, row accounting and terminal completion | `capture/api.py` | API capture tests | REFERENCE |
| Retry/replay requires same frozen API window | `capture/api.py` | API capture tests | REFERENCE |
| Promotable definitions/runtime-state classification | control plane | control-plane tests | REFERENCE |
| Existing v2 store receives real additive v3 APPEND migration | `control_plane.py` | migration tests | REFERENCE |
| Metadata materialization preserves runtime state | `delivery.py` | delivery tests | REFERENCE |
| Immutable v0.3.0 wheel/checksum release | release workflow | historical v0.3.0 release | RELEASE PROVEN for v0.3.0 |

## 3. Latest CI evidence

```text
f3521aa79b2cc66865d46a30e119a7dc4784d698
Actions 33220690474
197 passed
FULL_REBUILD

2466d6f254b37a1d79a716e8dd95c5dd16d21cf4
Actions 33222949040
215 passed
APPEND + control-plane v3 migration

6eb4ff275ed1aad9092f60f098d2a9272fd06779
Actions 33223276476
231 passed
schema contract/evolution + schema-change evidence

c326f062ad4e6be5185f17b9e6830946967361ab
Actions 33224558393
252 passed
file manifest + API frozen-window/pagination guards
```

These prove deterministic/reference/adapter-contract behavior only.

## 4. Required guarantees not yet complete

| Required guarantee | Current state | Next proof |
|---|---|---|
| Real Copy Job/Copy Activity/Dataflow/Spark invocation | adapter contract only | approved DEV Fabric run + retained native run ID |
| Native apply semantic equivalence | no generic native profile claims UPSERT/SCD1/SCD2 | profile-specific real certification |
| Debezium/Kafka real consumer/source-cursor commit coordination | reference adapter/resume only | live Kafka transport + commit/seek proof |
| Additional provider CDC adapters | only Debezium/Kafka built in | only as supported product scope requires |
| CDC transaction-boundary semantics where required | row event core exists | provider transaction tests |
| CDC partition/rebalance/source-epoch policy | ambiguity fails closed | explicit supported policy + tests |
| Retroactive SCD2 history correction | explicitly rejected | history rewrite policy only if required |
| Shared cross-strategy late/out-of-order taxonomy | PARTIAL | shared temporal policy wired across current/history paths |
| Remaining native-progress recovery | PARTIAL | Copy/Dataflow/Mirroring/provider-specific downstream-failure tests |
| Durable physical-target idempotency keys | PARTIAL | target-adapter persistence/unknown-outcome proof |
| Supported production control-plane repository | SQLAlchemy/SQLite reference only | approved persistent store + concurrency tests |
| Operator status/retry/backfill/replay/rebuild surface | runtime contracts only | query API/CLI |
| Fabric Pipeline backend | NOT IMPLEMENTED | real DEV orchestration |
| Enterprise IAM/network/secrets/RBAC/capacity | EXTERNAL | platform evidence |

## 5. Ownership invariants

```text
native/external source checkpoint authority
        !=
framework downstream semantic application checkpoint
```

For FABRIC_NATIVE/EXTERNAL progress, `CaptureReceipt` retains provider evidence. Framework state advances only on its own semantic target/reconciliation proof.

```text
semantic contract
    -> framework portable implementation
    -> optional provider stage delegation when capability/equivalence is certified
```

Provider success alone never proves full dataset semantic success.

## 6. Update rule

Every new guarantee must have:

1. one canonical implementation owner;
2. deterministic executable evidence;
3. explicit evidence level;
4. corresponding gap removed or narrowed here;
5. synchronized `PRODUCTION_REQUIREMENTS.md`, `PRODUCTION_READINESS_AUDIT.md`, relevant design docs and `CURRENT_STATUS.md`.
