# Guarantee Coverage — fabric-data-framework

Status: Canonical implementation-to-evidence map
Last updated: 2026-08-28

## 1. Purpose

This file is the fastest way for a new conversation or engineer to answer:

```text
What production guarantee do we claim?
Where is it implemented?
Which executable test proves the current scope?
What is still missing?
```

A row marked `REFERENCE` means portable/reference correctness is implemented and tested; it does **not** mean a real Fabric adapter or enterprise control has been proven.

## 2. Current guarantee map

| Guarantee | Canonical implementation owner | Representative executable evidence | Scope/status |
|---|---|---|---|
| Strict immutable dataset metadata | `src/fabric_data_framework/config.py` | `tests/test_config.py` | REFERENCE |
| Runtime override allow-list and deterministic effective-config hash | `config.py` | `tests/test_config.py` | REFERENCE |
| Capture and apply are independent semantics | `config.py` (`CaptureStrategy`, `ApplyStrategy`) | config/execution-plan tests | REFERENCE |
| Composite watermark ordering | `src/fabric_data_framework/watermark.py` | `tests/test_watermark.py` | REFERENCE |
| Watermark overlap selection | `watermark.py` / runtime state contracts | `tests/test_watermark.py`, execution tests | REFERENCE; broader recovery pending |
| Invalid/null incremental positions fail rather than silently skip | watermark/execution capture boundary | watermark/execution tests | REFERENCE |
| Bronze source lineage envelope | `src/fabric_data_framework/bronze.py` | execution tests | REFERENCE |
| Row DQ and explicit quarantine | `src/fabric_data_framework/quality/` | execution/full/snapshot tests | REFERENCE |
| No-silent-loss row accounting | `src/fabric_data_framework/operations.py`, quality/execution | operations/execution tests | REFERENCE |
| Deterministic SCD2 apply | `src/fabric_data_framework/scd2.py` | SCD2/execution tests | REFERENCE |
| One-current-row SCD2 invariant | `scd2.py` | SCD2 tests | REFERENCE |
| SCD2 late/conflict failure for certified scope | `scd2.py` | SCD2 tests | REFERENCE; general history repair pending |
| FULL snapshot completeness evidence | `src/fabric_data_framework/capture/full.py` | `tests/test_full_replace.py` | REFERENCE |
| FULL -> REPLACE isolated candidate/publication guard | `capture/full.py`, `apply/replace.py`, `execution/full_replace.py`, `data_plane/staging.py` | `tests/test_full_replace.py` | REFERENCE |
| Empty/incomplete/drastic-drop protection for REPLACE | `apply/replace.py` | `tests/test_full_replace.py` | REFERENCE |
| Snapshot completeness before delete inference | `capture/snapshot.py`, `apply/snapshot_diff.py` | `tests/test_snapshot_diff.py` | REFERENCE |
| Snapshot null/duplicate merge-key protection | `apply/snapshot_diff.py` | `tests/test_snapshot_diff.py` | REFERENCE |
| Snapshot delete-all/delete-fraction guard | `apply/snapshot_diff.py` | `tests/test_snapshot_diff.py` | REFERENCE |
| Quarantine cannot silently become snapshot deletion | `execution/snapshot_diff.py`, `apply/snapshot_diff.py` | `tests/test_snapshot_diff.py` | REFERENCE |
| Reconciliation before destructive publication | full/snapshot execution modules | full/snapshot tests | REFERENCE |
| Ordered SCD1 current-state apply | `src/fabric_data_framework/apply/scd1.py` | `tests/test_scd1.py` | REFERENCE |
| SCD1 composite merge key | `apply/scd1.py` | `tests/test_scd1.py` | REFERENCE |
| SCD1 event/version/sequence tuple ordering | `apply/scd1.py` (`ordering_columns`) | `tests/test_scd1.py` | REFERENCE |
| SCD1 exact rerun idempotency | `apply/scd1.py` | `test_scd1_exact_rerun_is_idempotent` | REFERENCE |
| SCD1 stale-row ignore/error policy | `apply/scd1.py` | `tests/test_scd1.py` | REFERENCE |
| SCD1 equal-position conflict fails closed | `apply/scd1.py` | `tests/test_scd1.py` | REFERENCE |
| SCD1 distinguishes duplicates/superseded/stale evidence | `apply/scd1.py` | `tests/test_scd1.py` | REFERENCE |
| Unordered changed SCD1 update fails unless explicitly authorized | `apply/scd1.py` | `tests/test_scd1.py` | REFERENCE |
| Metadata-driven dataset selection | `orchestration/planner.py`, `dispatcher.py` | `tests/test_dispatcher.py` | REFERENCE |
| Dependency/cycle validation | `orchestration/planner.py` | dispatcher tests | REFERENCE |
| Bounded dataset parallelism | planner/dispatcher reference backend | dispatcher tests | REFERENCE |
| Sibling failure isolation | dispatcher | dispatcher tests | REFERENCE |
| Failed dependency -> BLOCKED while unrelated sibling continues | planner/dispatcher | dispatcher tests | REFERENCE |
| Criticality-aware aggregate status | planner/dispatcher | dispatcher tests | REFERENCE |
| Immutable provider-neutral execution plan | `contracts/execution_plan.py` | `tests/test_execution_plan.py`, `test_dispatch_execution_plan.py` | REFERENCE |
| Native capture stage separated from framework process/apply stage | `contracts/execution_plan.py` | `tests/test_execution_engines.py` | REFERENCE contract |
| Conservative AUTO selection | `metadata/capabilities.py` | execution-engine tests | REFERENCE |
| Unsupported engine/semantic combinations fail before mutation | `metadata/capabilities.py` | execution-engine tests | REFERENCE |
| Named engine capability profiles | `metadata/capabilities.py` | execution-engine tests | REFERENCE |
| Dataflow Gen2 incremental bucket capture can feed framework SCD1 | named Dataflow profile + `compile_execution_plan` + `apply/scd1.py` | `tests/test_execution_engines.py`, `tests/test_scd1.py` | REFERENCE/planner proof; no real Dataflow run |
| Dataflow incremental profile does not claim composite watermark support | `metadata/capabilities.py` | execution-engine tests | REFERENCE |
| One physical capture checkpoint authority | `ProgressOwner`, capability validation | execution-engine tests | REFERENCE contract |
| Typed native/external capture handoff | `contracts/capture_receipt.py` | execution-engine/control-plane-v2 tests | REFERENCE |
| FULL receipt requires snapshot completeness identity/evidence | `contracts/capture_receipt.py` | execution-engine tests | REFERENCE |
| External stateful receipt requires checkpoint reference | `contracts/capture_receipt.py` | execution-engine tests | REFERENCE |
| Logical extension names only | `config.ExtensionConfig`, `extensions.py` | execution-engine tests | REFERENCE |
| Duplicate/missing extension registration fails explicitly | `extensions.py` | execution-engine tests | REFERENCE |
| Control-plane environment-local state separated from promotable definitions | `control_plane.py`, deployment contracts | control-plane/deployment tests | REFERENCE |
| Additive control-plane schema v2 | `control_plane.py` | `tests/test_control_plane_v2.py` | REFERENCE schema proof |
| Persist execution/profile/extensions metadata | `control_plane.py`, `delivery.py` | `test_control_plane_v2.py`, delivery tests | REFERENCE |
| Persist CaptureReceipt as environment-local evidence | control-plane/repository delivery helpers | `test_control_plane_v2.py` | REFERENCE |
| Metadata materialization preserves runtime state | `delivery.py` | `tests/test_delivery.py` | REFERENCE |
| Release identity independent of environment bindings | delivery/deployment | delivery/deployment tests | REFERENCE |
| Runtime state is never promoted with release definitions | deployment/control-plane sets | deployment/control-plane tests | REFERENCE |
| Build wheel + PR validation on supported Python versions | `.github/workflows/ci.yml` | GitHub Actions run evidence | CI PROVEN |
| Immutable v0.3.0 release/checksum path | `.github/workflows/release.yml`, delivery CLI | historical release run | RELEASE PROVEN for v0.3.0 |

## 3. Required guarantees not yet covered

These are intentionally explicit so a new chat does not infer them from adjacent code.

| Required guarantee | Current state | Intended owner/next proof |
|---|---|---|
| Ordered/idempotent UPSERT | NOT IMPLEMENTED | `apply/upsert.py` + certification tests |
| APPEND identity/collision policy | NOT IMPLEMENTED | `apply/append.py` + replay/collision tests |
| Explicit apply executor/native apply delegation | NOT IMPLEMENTED | execution metadata/plan capability layer |
| Native apply semantic equivalence certification | NOT IMPLEMENTED | engine/profile-specific certification |
| Retry attempt lineage | NOT IMPLEMENTED end to end | `recovery/retry.py`, dataset-run attempts |
| BACKFILL bounded range | NOT IMPLEMENTED | recovery + source-boundary tests |
| REPLAY/quarantine lineage | NOT IMPLEMENTED end to end | recovery/quarantine tests |
| FULL_REBUILD state reset/rebuild | NOT IMPLEMENTED | recovery tests |
| Unknown target-commit recovery | NOT IMPLEMENTED | idempotency/reconciliation recovery drill |
| CDC canonical I/U/D envelope | NOT IMPLEMENTED | `capture/cdc.py` |
| CDC event identity/order/dedup/conflict | NOT IMPLEMENTED | CDC certification |
| CDC checkpoint commit gate | NOT IMPLEMENTED | state/recovery + CDC tests |
| Snapshot -> CDC bootstrap handoff | NOT IMPLEMENTED | `capture/bootstrap_cdc.py` |
| General schema evolution classification | NOT IMPLEMENTED | `quality/schema_contracts.py` |
| Additive/breaking schema migration proof | NOT IMPLEMENTED | schema certification |
| General late/out-of-order correction policy | PARTIAL only in SCD1/SCD2 scopes | shared temporal policy tests |
| Physical persistent production control-plane repository | NOT IMPLEMENTED | approved relational/Fabric store adapter |
| Operator `status/retry/backfill/replay` surface | NOT IMPLEMENTED | CLI/query/integration tests |
| Fabric Pipeline backend | NOT IMPLEMENTED | real DEV integration |
| Fabric Copy Activity adapter | NOT IMPLEMENTED | real DEV capture receipt proof |
| Fabric Copy Job adapter | NOT IMPLEMENTED | connector/profile native run proof |
| Dataflow Gen2 adapter | NOT IMPLEMENTED | real incremental landing + receipt proof |
| Spark Job Definition/Environment adapter | NOT IMPLEMENTED | real SJD/wheel/environment proof |
| Native run IDs persisted from real Fabric executions | NOT PROVEN | adapter integration tests |
| Enterprise IAM/network/secrets/RBAC | EXTERNAL | approved company estate evidence |

## 4. Framework-first delegation invariant

ADR 0009 is a cross-cutting guarantee:

```text
core semantic contract
    -> framework-owned portable implementation
    -> optional native stage delegation only when capability-certified
```

The capability registry must remain conservative. A product feature name does not imply semantic equivalence.

For example:

```text
WATERMARK + SCD1

Dataflow Gen2 profile:
  capture/stage = DATAFLOW_GEN2
  capture progress owner = FABRIC_NATIVE
  apply = framework SCD1

Framework fallback:
  capture/stage = SPARK/framework
  progress owner = FRAMEWORK
  apply = same framework SCD1 contract
```

This invariant is what allows domains to keep stable semantic metadata while physical Fabric capabilities evolve.

## 5. Updating this file

When adding a production capability:

1. add the canonical implementation owner;
2. add at least one deterministic executable proof;
3. state the evidence scope (`REFERENCE`, `FABRIC PROVEN`, etc.);
4. remove/update the matching gap row;
5. update `PRODUCTION_READINESS_AUDIT.md`, `PRODUCTION_REQUIREMENTS.md` and `CURRENT_STATUS.md` in the same coherent slice.
