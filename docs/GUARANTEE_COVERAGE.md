# Guarantee Coverage — fabric-data-framework

Status: Canonical implementation-to-evidence map
Last updated: 2026-08-29

## 1. Evidence vocabulary

- `REFERENCE` — provider-neutral semantics/contracts implemented and deterministically tested.
- `ADAPTER CONTRACT` — provider adapter boundary/evidence conversion tested with deterministic transport; no real service call implied.
- `CI PROVEN` — package/static/test/build workflow has succeeded in GitHub Actions.
- `FABRIC PROVEN` — requires a retained real Microsoft Fabric execution/run correlation. No new hardening capability currently has this level.
- `EXTERNAL` — enterprise/platform control that this repository must not invent.

## 2. Current guarantee map

| Guarantee | Canonical implementation owner | Representative evidence | Scope |
|---|---|---|---|
| Strict immutable dataset metadata | `config.py` | `tests/test_config.py` | REFERENCE |
| Runtime override allow-list + deterministic effective-config hash | `config.py` | config tests | REFERENCE |
| Capture/apply semantics are independent | `config.py` | config/execution-plan tests | REFERENCE |
| Capture executor and apply executor are independent | `config.ExecutionPolicy`, `contracts/execution_plan.py` | `tests/test_stage_execution_policy.py` | REFERENCE |
| Unsupported engine/profile/semantic combination fails before mutation | `metadata/capabilities.py` | execution-engine tests | REFERENCE |
| Composite WATERMARK ordering/overlap | `watermark.py` | watermark tests | REFERENCE |
| Invalid incremental positions fail rather than silently skip | watermark/capture boundary | watermark/execution tests | REFERENCE |
| Bronze source lineage envelope | `bronze.py` | execution tests | REFERENCE |
| Row DQ/quarantine + no-silent-loss accounting | `quality/`, `operations.py` | quality/execution tests | REFERENCE |
| Deterministic SCD2 + one-current-row invariant | `scd2.py` | SCD2 tests | REFERENCE |
| Guarded FULL -> REPLACE | `capture/full.py`, `apply/replace.py`, `execution/full_replace.py` | `tests/test_full_replace.py` | REFERENCE |
| Complete SNAPSHOT before delete inference | `capture/snapshot.py`, `apply/snapshot_diff.py` | `tests/test_snapshot_diff.py` | REFERENCE |
| Snapshot delete/quarantine guardrails | snapshot execution/apply | snapshot-diff tests | REFERENCE |
| Ordered/idempotent SCD1 | `apply/current_state.py`, `apply/scd1.py` | `tests/test_scd1.py` | REFERENCE |
| Ordered/idempotent UPSERT | `apply/current_state.py`, `apply/upsert.py` | `tests/test_upsert.py` | REFERENCE |
| Equal-position conflicting current-state payload fails closed | current-state primitive | SCD1/UPSERT tests | REFERENCE |
| Stale current-state update IGNORE/ERROR policy | current-state primitive | SCD1/UPSERT tests | REFERENCE |
| Metadata-driven selection/dependency/cycle validation | orchestration planner/dispatcher | dispatcher tests | REFERENCE |
| Bounded parallelism + sibling failure isolation | dispatcher/reference backend | dispatcher tests | REFERENCE |
| Failed dependency -> BLOCKED while unrelated branch continues | dispatcher | dispatcher tests | REFERENCE |
| Criticality-aware pipeline aggregate status | dispatcher | dispatcher tests | REFERENCE |
| Immutable concrete ExecutionPlan | `contracts/execution_plan.py` | execution-plan tests | REFERENCE |
| Dataflow Gen2 incremental capture can feed framework SCD1/UPSERT | named profile + execution plan | stage-execution tests | REFERENCE planner proof |
| One physical capture checkpoint authority | `ProgressOwner`, capability validation | execution-engine tests | REFERENCE |
| Typed native/external capture handoff | `contracts/capture_receipt.py` | capture-receipt/control-plane tests | REFERENCE |
| FULL/SNAPSHOT receipt requires snapshot identity/completeness evidence | CaptureReceipt | execution-engine tests | REFERENCE |
| Logical extension names only | `ExtensionConfig`, extension registry | extension tests | REFERENCE |
| Fabric capture request/native-run evidence contracts | `adapters/fabric/contracts.py` | `tests/test_fabric_capture_adapters.py` | ADAPTER CONTRACT |
| Copy Job capture adapter validates native evidence and emits receipt | `adapters/fabric/adapter.py` | fabric-adapter tests | ADAPTER CONTRACT |
| Copy Activity capture adapter validates bounded source range | same | fabric-adapter tests | ADAPTER CONTRACT |
| Dataflow Gen2 capture adapter preserves native progress ownership | same | fabric-adapter tests | ADAPTER CONTRACT |
| Spark capture adapter is available only for a pure capture unit | same | fabric-adapter tests | ADAPTER CONTRACT |
| FAILED/CANCELLED/UNKNOWN Fabric run never becomes success receipt | same | fabric-adapter tests | ADAPTER CONTRACT |
| Fabric landing/kind/snapshot mismatch fails closed | same | fabric-adapter tests | ADAPTER CONTRACT |
| Explicit Fabric adapter registry; no implicit client construction | same | fabric-adapter tests | ADAPTER CONTRACT |
| Conservative retry classification | `recovery/runtime.py` | `tests/test_recovery.py` | REFERENCE |
| Explicit transient failure may retry; unclassified failure does not | recovery runtime | recovery tests | REFERENCE |
| Attempt 1 FAILED -> attempt 2 SUCCESS lineage | recovery runtime/contracts | recovery tests | REFERENCE |
| Retry exhaustion is explicit | recovery runtime | recovery tests | REFERENCE |
| Unknown target commit is reconciled before retry | recovery runtime | recovery tests | REFERENCE |
| Unknown outcome COMMITTED converges without duplicate write | recovery runtime | recovery tests | REFERENCE |
| Unknown outcome NOT_COMMITTED may retry | recovery runtime | recovery tests | REFERENCE |
| Unknown outcome UNRESOLVED refuses blind retry | recovery runtime | recovery tests | REFERENCE |
| Process-control exceptions are not converted into retry decisions | recovery runtime | `test_recovery_runtime_hardening.py` | REFERENCE |
| RETRY request requires original dataset run | `contracts/recovery.py` | recovery tests | REFERENCE contract |
| BACKFILL request requires explicit lower/upper range | recovery contract | recovery tests | REFERENCE contract |
| REPLAY request requires source/quarantine lineage | recovery contract | recovery tests | REFERENCE contract |
| FULL_REBUILD requires explicit authoritative-reset intent | recovery contract | recovery tests | REFERENCE contract |
| Reprocess semantic identity cannot mutate during lifecycle | recovery repository/control-plane IO | recovery tests | REFERENCE |
| Dataset attempt root/previous lineage is immutable evidence | recovery contract/repository | recovery tests | REFERENCE |
| Reprocess/attempt lineage is environment-local, never promoted | `control_plane.py` | `tests/test_recovery_control_plane.py` | REFERENCE schema proof |
| Promotable definitions and runtime-state sets are disjoint/full coverage | `control_plane.py` | control-plane tests | REFERENCE |
| Metadata materialization preserves runtime state | `delivery.py` | delivery tests | REFERENCE |
| Release identity independent of environment binding | delivery/deployment | delivery tests | REFERENCE |
| GitHub PR CI builds/tests Python 3.11 and 3.13 | `.github/workflows/ci.yml` | run `33179754372` | CI PROVEN; 139 tests |
| Immutable v0.3.0 wheel/checksum release path | release workflow | historical v0.3.0 release | RELEASE PROVEN for v0.3.0 |

## 3. Required guarantees not yet complete

| Required guarantee | Current state | Next proof |
|---|---|---|
| Real Copy Job/Copy Activity/Dataflow/Spark transport/API invocation | Adapter contract exists; no real Fabric call | approved DEV Fabric integration with native run ID |
| Native apply semantic equivalence certification | no profile currently claims generic native UPSERT/SCD1/SCD2 | engine/profile-specific real tests |
| Strategy-specific retry source-range/restaging preservation | recovery core exists; not wired for all capture families | per-strategy recovery certification |
| Quarantine REPLAY payload execution and `replayed_by_dataset_run_id` end-to-end | request/lineage contract exists | replay executor + persistent quarantine tests |
| FULL_REBUILD target/state reset execution | request authorization contract exists | rebuild executor + state reset certification |
| Native-progress recovery after downstream apply failure | general receipt/recovery contracts exist | Copy/Dataflow/Mirroring-specific recovery tests |
| CDC canonical I/U/D envelope | NOT IMPLEMENTED | `capture/cdc.py` + tests |
| CDC event identity/order/dedupe/conflict | NOT IMPLEMENTED | CDC certification |
| CDC checkpoint commit gate | NOT IMPLEMENTED | CDC state/recovery tests |
| Snapshot/bootstrap -> CDC handoff | NOT IMPLEMENTED | bootstrap CDC proof |
| APPEND identity/collision semantics | NOT IMPLEMENTED | `apply/append.py` |
| General schema-evolution classification | NOT IMPLEMENTED | schema contract/classification tests |
| General cross-strategy late/out-of-order policy | PARTIAL in current-state/SCD2 | shared temporal/error taxonomy |
| Supported persistent production control-plane repository | SQLAlchemy/SQLite reference only | approved store + transaction/concurrency tests |
| Operator status/retry/backfill/replay/rebuild surface | runtime contracts exist, no supported operator API/CLI | repository queries + CLI/API tests |
| Fabric Pipeline backend | NOT IMPLEMENTED | real DEV orchestration |
| Native run IDs from actual Fabric executions | NOT PROVEN | real adapter integration |
| Enterprise IAM/network/secrets/RBAC/capacity | EXTERNAL | enterprise/platform evidence |

## 4. Framework-first delegation invariant

```text
semantic contract
    -> framework portable implementation
    -> capability resolver
    -> optional stage delegate only when equivalence/capability is proven
```

A provider run being `SUCCEEDED` is not sufficient evidence that the framework semantic contract succeeded. Native capture must first produce validated evidence/receipt, and non-delegated framework stages remain responsible for apply/reconciliation/state.

Representative hybrid:

```text
Dataflow Gen2 incremental capture
    -> validated FabricNativeRunEvidence
    -> CaptureReceipt
    -> framework UPSERT/SCD1
    -> reconciliation
    -> state/audit
```

## 5. Update rule

Every new guarantee must have:

1. one canonical implementation owner;
2. deterministic executable evidence;
3. an explicit evidence level;
4. the corresponding gap removed or narrowed here;
5. synchronized `PRODUCTION_REQUIREMENTS.md`, `PRODUCTION_READINESS_AUDIT.md` and `CURRENT_STATUS.md`.
