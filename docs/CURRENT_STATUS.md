# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine: **COMPLETE AND RELEASED AS `v0.3.0`**.
- Phase 4 — metadata-driven multi-dataset dispatcher/failure isolation: **MERGED TO `main` AS UNRELEASED 0.4.0 DEVELOPMENT SOURCE**.
- Current milestone — **PRODUCTION FRAMEWORK HARDENING; RELEASE PAUSED UNTIL THE PRODUCT SLICE IS MATERIALLY BROADER**.

## Product requirement

Do **not** publish `v0.4.0` now.

The target is a released wheel that an enterprise domain installs and then uses mainly through source-controlled metadata, environment bindings and bounded domain extensions. Routine dataset onboarding must not require editing `fabric-data-framework` itself.

Framework `v0.3.0` remains the latest immutable GitHub Release. The 0.4.0 source version is an unreleased development line.

Active PR/branch:

```text
PR #13
architecture/production-framework-blueprint
```

## Latest validated implementation evidence

The latest coherent code/control-plane slice is fully green:

```text
60d4d1362f504a51b3ecedfcb93c7c6ceb3d4578
GitHub Actions run 33175724889
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
106 tests passed
```

That run includes ordered UPSERT, independent capture/apply planning, Dataflow-to-framework apply certification and apply-execution control-plane materialization.

The synchronized canonical documentation/audit head immediately before this status-evidence commit is also fully green:

```text
1d3c60af060e828107a9f06d6449e983c38ffb46
GitHub Actions run 33176317779
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
106 tests passed
```

The docs head includes updated ADR 0009, Project Blueprint, Production Requirements, Execution Engine Strategy, Control Plane Design, Guarantee Coverage and Production Readiness Audit. This final status-evidence commit must also remain green before further implementation proceeds.

## Implemented development runtime

The hardening branch now provides:

- strict typed semantic config and allow-listed runtime overrides;
- infrastructure/environment binding abstraction;
- composite WATERMARK selection with tie-breakers/overlap;
- normalized Bronze lineage envelope;
- row DQ/quarantine and row-accounting primitives;
- deterministic reference SCD2 behavior;
- shared ordered current-state primitive for SCD1 and UPSERT;
- deterministic ordered SCD1 current-state behavior;
- deterministic ordered UPSERT behavior;
- reconciliation/state commit gates for implemented execution slices;
- metadata-driven dispatcher with dependency validation/failure isolation;
- provider-neutral orchestration planning separated from the in-process backend;
- immutable `ExecutionPlan` / execution-unit contracts;
- independent capture/movement executor and apply executor selection;
- guarded `FULL -> REPLACE` with isolated staging, completeness/source-count/empty-source/row-drop guards, reconciliation and publication evidence;
- guarded `SNAPSHOT -> SNAPSHOT_DIFF` with complete-snapshot requirement, null/duplicate-key protection, delete-volume/delete-all guards, quarantine-aware delete blocking and reconciliation-before-publication;
- named engine capability profiles keyed by engine + profile;
- typed `CaptureReceipt` for native/external capture handoff and native-run correlation;
- controlled logical-name domain extension registry;
- additive control-plane schema v2 including capture `execution_policy`, `apply_execution_policy`, `ordering_policy` and environment-local `capture_receipt` persistence;
- immutable release/delivery contracts and CLI.

## Shared current-state apply foundation

`src/fabric_data_framework/apply/current_state.py` is the shared provider-neutral correctness primitive used by SCD1 and UPSERT.

Certified behavior:

```text
composite merge key
source ordering tuple: event time / version / sequence / LSN-like value
latest-row selection within one incoming batch
exact-rerun idempotency
stale-row IGNORE or ERROR policy
equal-position conflicting payload -> fail closed
unordered changed update -> fail closed unless explicitly authorized
duplicate / incoming-superseded / stale metrics
```

For existing keys, incoming fields merge over the current target row while target-only fields are retained.

SCD1 remains the dimensional current-state semantic name. UPSERT is the generic insert-or-update current-state semantic. They intentionally share hard ordering/idempotency logic rather than maintaining two drifting implementations.

Representative proof:

```text
tests/test_scd1.py
tests/test_upsert.py
```

## Capture executor and apply executor are now independent

ADR 0009 is now implemented at metadata/planning/control-plane contract level.

Source-controlled execution policy:

```text
execution.engine
execution.capability_profile
execution.progress_owner
    -> capture / movement policy

execution.apply_engine
execution.apply_capability_profile
    -> independent final-target apply policy
```

`AUTO` may appear in source-controlled policy, but the immutable `ExecutionPlan` must contain concrete engines:

```text
ExecutionPlan.capture_engine
ExecutionPlan.capture_capability_profile
ExecutionPlan.apply_engine
ExecutionPlan.apply_capability_profile
```

Default apply resolution is conservative:

```text
apply_engine = AUTO
    -> SPARK / framework apply
```

Generic native profiles currently certify **no** final-target apply semantic. SQL/native apply therefore fails closed unless a future named apply profile explicitly certifies the requested `ApplyStrategy`. `CUSTOM` apply is allowed only with a controlled `extensions.apply` logical reference.

Representative proof:

```text
tests/test_stage_execution_policy.py
```

## Dataflow Gen2 incremental -> framework SCD1/UPSERT

The named capture profile:

```text
dataflow_gen2_incremental_bucket_v1
```

certifies only the bounded Dataflow Gen2 incremental capture/staging role:

```text
capture_strategy = WATERMARK
capture engine   = DATAFLOW_GEN2
progress_owner   = FABRIC_NATIVE
composite WM     = NOT CERTIFIED
native apply     = NOT CERTIFIED
```

The planner explicitly produces this hybrid plan:

```text
Dataflow Gen2 incremental capture/stage
    -> framework normalize/validate
    -> framework SCD1 or UPSERT
    -> reconcile
    -> state/audit
```

The Dataflow capture profile cannot be reused as a fake native SCD1 apply profile. The negative case is executable-tested.

This is the key product invariant: use Fabric-native movement where strong without allowing native destination limitations to redefine the requested semantic contract.

## Control-plane representation

The deployed semantic/control plane mirrors the stage separation:

```text
execution_policy
  dataset_id
  execution_engine          # capture/movement policy
  progress_owner
  capability_profile
  extensions

apply_execution_policy
  dataset_id
  execution_engine          # apply policy
  capability_profile

ordering_policy
  event_time_column
  version_column
  sequence_column
```

`apply_execution_policy` is a promotable semantic definition and is created by the normal baseline schema/CLI path. It is idempotently materialized from source-controlled metadata.

Representative proof:

```text
tests/test_apply_execution_policy.py
```

The control-plane schema remains version 2 because this broader v2 definition has not been publicly released; no published v2 production migration contract is being rewritten.

## Framework-first semantics and stage-level native delegation

Canonical invariant:

```text
semantic requirement
    -> framework-owned contract + portable fallback implementation
    -> capability resolver
         -> delegate an individual stage to native Fabric only when certified
         -> otherwise use the framework implementation
```

Physical ownership:

```text
capture / movement
    != normalize / transform
    != apply
    != reconcile / state
```

Progress ownership applies only to physical capture/checkpoint authority and never implies apply ownership.

## Durable audit documents

New conversations must read:

```text
docs/ECOSYSTEM_BLUEPRINT.md
docs/PROJECT_BLUEPRINT.md
docs/PRODUCTION_REQUIREMENTS.md
docs/PRODUCTION_READINESS_AUDIT.md
docs/GUARANTEE_COVERAGE.md
docs/EXECUTION_ENGINE_STRATEGY.md
docs/CONTROL_PLANE_DESIGN.md
docs/CICD_DESIGN.md
docs/CURRENT_STATUS.md
```

`PRODUCTION_READINESS_AUDIT.md` separates portable semantics, deterministic certification, real Fabric evidence and external enterprise controls.

`GUARANTEE_COVERAGE.md` maps claimed guarantees to code/test owners and explicitly lists remaining gaps.

## Current external boundary

No enterprise Fabric workspace, capacity, tenant setting, RBAC, networking, connection, credential, production dataset or runtime state has been modified by this hardening work.

Portable/reference semantics and SQLAlchemy schema proof are not the same as real Fabric production evidence.

## Exact next implementation sequence

1. Implement Fabric-stage adapter contracts for Copy Job, Copy Activity, Dataflow Gen2 and Spark that emit/correlate immutable `CaptureReceipt` evidence without weakening the semantic plan.
2. Implement RETRY/BACKFILL/REPLAY/FULL_REBUILD attempt lineage, retryability classification and unknown-target-commit recovery.
3. Implement CDC normalization -> UPSERT/SCD1/SCD2, including event identity/order/dedup/delete semantics and checkpoint commit gates.
4. Implement snapshot/bootstrap -> CDC handoff so bootstrap changes have no gap/double apply.
5. Add APPEND identity/collision semantics.
6. Add general schema-evolution and late/out-of-order policy contracts beyond the currently certified SCD1/UPSERT/SCD2 scopes.
7. Add a supported persistent control-plane repository/operator query surface.
8. Prove at least one real hybrid Fabric DEV scenario: native capture -> `CaptureReceipt` -> framework SCD1/UPSERT.
9. Re-run production readiness/guarantee audits against real adapter evidence.
10. Only then decide the next immutable public framework release scope/version.

## Release gate

Do not create `v0.4.0` from the current state.

The next release may still use version `0.4.0` if no public 0.4.0 artifact exists, but publication requires a coherent broadly usable enterprise product slice and certification evidence.

Do not fake Fabric-estate, security, capacity or production evidence.
