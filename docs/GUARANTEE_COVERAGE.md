# Guarantee Coverage — fabric-data-framework

Status: Canonical implementation-to-evidence map
Last updated: 2026-08-29

## 1. Evidence vocabulary

- `REFERENCE` — provider-neutral semantics/contracts implemented and deterministically tested.
- `ADAPTER CONTRACT` — provider adapter boundary/evidence conversion tested with deterministic transport; no real service call implied.
- `CI PROVEN` — package/static/test/build workflow succeeded in GitHub Actions.
- `FABRIC PROVEN` — retained real Microsoft Fabric execution/run correlation. No new hardening capability currently has this level.
- `EXTERNAL` — enterprise/platform control this repository must not invent.

## 2. Current guarantee map

| Guarantee | Canonical owner | Representative evidence | Scope |
|---|---|---|---|
| Strict immutable dataset metadata | `config.py` | config tests | REFERENCE |
| Runtime override allow-list + deterministic effective-config hash | `config.py` | config tests | REFERENCE |
| Capture/apply semantic independence | `config.py` | config/execution-plan tests | REFERENCE |
| Independent capture/apply executor selection | `ExecutionPolicy`, `execution_plan.py` | stage-execution tests | REFERENCE |
| Unsupported engine/profile/semantic combination fails before mutation | `metadata/capabilities.py` | engine tests | REFERENCE |
| Composite WATERMARK ordering/overlap | `watermark.py` | watermark tests | REFERENCE |
| Bronze lineage envelope | `bronze.py` | execution tests | REFERENCE |
| Row DQ/quarantine + no-silent-loss accounting | `quality/`, `operations.py` | quality/execution tests | REFERENCE |
| Guarded FULL -> REPLACE | capture/apply/execution modules | full-replace tests | REFERENCE |
| Complete SNAPSHOT + guarded SNAPSHOT_DIFF | snapshot modules | snapshot tests | REFERENCE |
| Ordered/idempotent SCD1 | `apply/current_state.py`, `apply/scd1.py` | SCD1 tests | REFERENCE |
| Ordered/idempotent UPSERT | `apply/current_state.py`, `apply/upsert.py` | UPSERT tests | REFERENCE |
| Deterministic SCD2 one-current-row invariant | `scd2.py` | SCD2 tests | REFERENCE |
| Equal-position current-state conflict fails closed | current-state primitive | SCD1/UPSERT tests | REFERENCE |
| Metadata-driven dependencies/concurrency/failure isolation | dispatcher/orchestration | dispatcher tests | REFERENCE |
| Immutable concrete ExecutionPlan | `contracts/execution_plan.py` | execution-plan tests | REFERENCE |
| Dataflow Gen2 incremental capture can feed framework SCD1/UPSERT | capability profile + plan | stage tests | REFERENCE planner proof |
| One physical capture progress authority | `ProgressOwner` + capability validation | engine tests | REFERENCE |
| Typed native/external capture handoff | `CaptureReceipt` | receipt/control-plane tests | REFERENCE |
| Logical-name bounded extensions | extension registry/config | extension tests | REFERENCE |
| Fabric capture request/native evidence contracts | `adapters/fabric/` | fabric-adapter tests | ADAPTER CONTRACT |
| Copy Job/Copy Activity/Dataflow/Spark capture adapters fail closed | `adapters/fabric/adapter.py` | fabric-adapter tests | ADAPTER CONTRACT |
| Native FAILED/CANCELLED/UNKNOWN never yields success receipt | Fabric adapter | fabric-adapter tests | ADAPTER CONTRACT |
| Framework-bounded native movement verifies exact source range | Fabric adapter | fabric-adapter tests | ADAPTER CONTRACT |
| Conservative retry classification | `recovery/runtime.py` | recovery tests | REFERENCE |
| Attempt 1 FAILED -> attempt 2 SUCCESS lineage | recovery runtime/contracts | recovery tests | REFERENCE |
| Unknown target commit reconciled before retry | recovery runtime | recovery tests | REFERENCE |
| UNKNOWN COMMITTED converges without duplicate write | recovery runtime | recovery tests | REFERENCE |
| UNKNOWN NOT_COMMITTED may retry | recovery runtime | recovery tests | REFERENCE |
| UNKNOWN UNRESOLVED refuses blind retry | recovery runtime | recovery tests | REFERENCE |
| RETRY/BACKFILL/REPLAY/FULL_REBUILD intent contracts | recovery contracts | recovery tests | REFERENCE contract |
| Reprocess semantic identity immutable | control-plane IO | recovery control-plane tests | REFERENCE |
| Attempt/reprocess evidence environment-local | control plane | recovery tests | REFERENCE schema proof |
| Canonical CDC INSERT/UPDATE/DELETE envelope | `capture/cdc.py` | `tests/test_cdc.py` | REFERENCE |
| CDC event identity + exact duplicate idempotency | `capture/cdc.py` | CDC tests | REFERENCE |
| Conflicting duplicate identity fails closed | `capture/cdc.py` | CDC tests | REFERENCE |
| Ambiguous shared source position fails closed | `capture/cdc.py` | CDC tests | REFERENCE |
| Same-key cross-partition ambiguity fails closed | `capture/cdc.py` | CDC tests | REFERENCE |
| Frozen CDC upper checkpoint + completeness evidence | `capture/cdc.py` | CDC tests | REFERENCE |
| Committed CDC overlap is ignored idempotently | `capture/cdc.py` | CDC tests | REFERENCE |
| CDC checkpoint cannot advance before target/reconciliation gate | `CDCCheckpointTransition` | CDC/checkpoint tests | REFERENCE |
| CDC -> UPSERT current-state semantics | `apply/cdc.py` | CDC tests | REFERENCE |
| CDC -> SCD1 current-state semantics | `apply/cdc.py` | CDC tests | REFERENCE |
| CDC current-state INSERT/UPDATE/DELETE/reinsert | `apply/cdc.py` | CDC tests | REFERENCE |
| CDC stale/equal-position/delete-policy behavior | `apply/cdc.py` | CDC tests | REFERENCE |
| CDC -> SCD2 source-order/valid-time separation | `apply/cdc_scd2.py` | `tests/test_cdc_scd2.py` | REFERENCE |
| Same event time can be disambiguated by source position | `apply/cdc_scd2.py` | CDC SCD2 tests | REFERENCE |
| Retroactive SCD2 valid-time correction fails closed | `apply/cdc_scd2.py` | CDC SCD2 tests | REFERENCE |
| Durable CDC apply checkpoint | `control_plane.py`, `control_plane_io.py` | checkpoint persistence tests | REFERENCE schema/transaction proof |
| CDC checkpoint optimistic concurrency rejects stale writer | control-plane IO | checkpoint tests | REFERENCE |
| CDC checkpoint is environment-local, never promoted | control plane/deployment classification | checkpoint tests | REFERENCE |
| Snapshot/bootstrap -> CDC no-gap fence | `capture/bootstrap_cdc.py` | bootstrap CDC tests | REFERENCE |
| Snapshot-covered CDC overlap is not double-applied | bootstrap normalization | bootstrap tests | REFERENCE |
| Bootstrap stream-after-fence/partition-change evidence fails closed | bootstrap contract | bootstrap tests | REFERENCE |
| Promotable definitions/runtime-state classification | control plane | control-plane tests | REFERENCE |
| Metadata materialization preserves runtime state | `delivery.py` | delivery tests | REFERENCE |
| Release identity independent of environment binding | delivery/deployment | delivery tests | REFERENCE |
| Immutable v0.3.0 wheel/checksum release | release workflow | historical v0.3.0 release | RELEASE PROVEN for v0.3.0 |

## 3. Current CI evidence

```text
Fabric adapter contract
b831d465c2f03117c323a0cbd90e22bbf081417c
Actions 33178765403
123 passed

Recovery core/hardening
a5da06294dfba0c5ae756dcc1d8814931feebec7
Actions 33179754372
139 passed

Canonical CDC + UPSERT/SCD1
ccf0fc8950efb1f4d338cadcaf83aac5fd49a7b9
Actions 33215409341
153 passed

CDC -> SCD2
ed6c13d4fcabe165ef86be2e547d794e15e5375c
Actions 33215708004
159 passed

CDC durable checkpoint
c41fbd00bb3d3c6bc71e20f958c4ec14106ac33c
Actions 33216133811
165 passed

Snapshot/bootstrap -> CDC
465a2c1e9ddf25b0ace2293f578c2c5bb3a653ae
Actions 33216281126
171 passed
```

These CI results prove deterministic/reference behavior only.

## 4. Required guarantees not yet complete

| Required guarantee | Current state | Next proof |
|---|---|---|
| Real Copy Job/Copy Activity/Dataflow/Spark invocation | adapter contract only | approved DEV Fabric run + native run ID |
| Native apply semantic equivalence | no generic native profile claims UPSERT/SCD1/SCD2 | profile-specific real tests |
| Built-in/provider CDC envelope adapters | canonical core exists | selected Debezium/database/Fabric mappings |
| Provider-specific CDC offset commit/resume after downstream failure | canonical apply checkpoint exists | adapter recovery integration |
| CDC transaction-boundary semantics where required | row event core exists | provider transaction tests |
| CDC partition/rebalance/source-epoch policy | current model fails closed on ambiguity | explicit supported policy + tests |
| CDC poison-event quarantine/replay | not wired end to end | quarantine/replay executor |
| Retroactive SCD2 history correction | explicitly rejected | history rewrite policy if product scope requires |
| Strategy-specific retry source-range/restaging preservation | recovery core exists | per-capture-family certification |
| Quarantine REPLAY payload execution | request/lineage contract exists | replay executor + persistent tests |
| FULL_REBUILD target/state reset execution | authorization contract exists | rebuild executor |
| Native-progress recovery after downstream failure | receipt/recovery contracts exist | Copy/Dataflow/Mirroring/CDC tests |
| APPEND identity/collision semantics | NOT IMPLEMENTED | `apply/append.py` |
| File manifest freeze/readiness | NOT IMPLEMENTED | file capture contract |
| API pagination/window guardrails | NOT IMPLEMENTED | API capture contract |
| General schema-evolution classification | NOT IMPLEMENTED | schema compatibility tests |
| Shared cross-strategy late/out-of-order taxonomy | PARTIAL | temporal/error policy model |
| Supported production control-plane repository | SQLAlchemy/SQLite reference only | approved store + concurrency tests |
| Operator status/retry/backfill/replay/rebuild surface | runtime contracts only | query API/CLI |
| Fabric Pipeline backend | NOT IMPLEMENTED | real DEV orchestration |
| Enterprise IAM/network/secrets/RBAC/capacity | EXTERNAL | platform evidence |

## 5. CDC ownership invariant

```text
native/external source checkpoint authority
        !=
framework downstream CDC application checkpoint
```

For FABRIC_NATIVE/EXTERNAL progress, `CaptureReceipt` retains native/external checkpoint evidence. `cdc_checkpoint` records framework semantic application progress and must not be used to claim ownership of the provider cursor.

## 6. Framework-first delegation invariant

```text
semantic contract
    -> framework portable implementation
    -> capability resolver
    -> optional stage delegate only when equivalence/capability is proven
```

A provider run being `SUCCEEDED` is not sufficient evidence that the full framework semantic contract succeeded.

## 7. Update rule

Every new guarantee must have:

1. one canonical implementation owner;
2. deterministic executable evidence;
3. explicit evidence level;
4. corresponding gap removed or narrowed here;
5. synchronized `PRODUCTION_REQUIREMENTS.md`, `PRODUCTION_READINESS_AUDIT.md`, domain-specific design docs and `CURRENT_STATUS.md`.
