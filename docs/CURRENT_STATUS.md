# Current Status — fabric-data-framework

Last updated: 2026-08-29

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine: **COMPLETE AND RELEASED AS `v0.3.0`**.
- Phase 4 — metadata-driven multi-dataset dispatcher/failure isolation: **MERGED TO `main` AS UNRELEASED 0.4.0 DEVELOPMENT SOURCE**.
- Current milestone — **PRODUCTION FRAMEWORK HARDENING ON PR #13; RELEASE REMAINS PAUSED**.

## Release rule

Do **not** publish `v0.4.0` from the current branch.

`v0.3.0` remains the latest immutable public Framework release. The current `0.4.0` source version is an unreleased development line. A release requires a coherent enterprise product slice plus deterministic evidence and at least one real approved Fabric integration proof; reference contracts alone are insufficient.

Active work:

```text
PR #13
branch: architecture/production-framework-blueprint
base:   main
```

## Latest validated implementation evidence

### Fabric capture adapter contract

```text
commit b831d465c2f03117c323a0cbd90e22bbf081417c
GitHub Actions 33178765403
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
123 tests passed
```

### Recovery runtime

```text
commit dee5eee5a87da67a81e2ed787336898b71a5c473
GitHub Actions 33179289663
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
134 tests passed
```

### Recovery relational evidence + runtime hardening

```text
commit a5da06294dfba0c5ae756dcc1d8814931feebec7
GitHub Actions 33179754372
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
139 tests passed
```

The relational evidence commit immediately before the final hardening was also fully green:

```text
333d62ed5b06787026ec7f25481f37bed6c44ea1
GitHub Actions 33179523583
137 tests passed
```

## Implemented development runtime

The hardening branch now provides at reference/portable level:

- strict immutable semantic config and allow-listed runtime overrides;
- infrastructure/environment binding abstraction;
- independent capture semantics and apply semantics;
- independent capture/movement executor and apply executor selection;
- conservative engine/profile capability resolution;
- composite WATERMARK selection with tie-breaker/overlap;
- source-faithful Bronze lineage envelope;
- DQ/quarantine and no-silent-loss row accounting;
- deterministic SCD2 reference semantics;
- shared ordered current-state primitive;
- ordered/idempotent SCD1;
- ordered/idempotent UPSERT;
- guarded `FULL -> REPLACE`;
- guarded `SNAPSHOT -> SNAPSHOT_DIFF`;
- metadata-driven multi-dataset dispatcher/failure isolation;
- immutable `ExecutionPlan` / execution-unit contracts;
- typed `CaptureReceipt` native/external capture handoff;
- Fabric capture adapter contract layer for Copy Job, Copy Activity, Dataflow Gen2 and Spark;
- bounded logical-name extension registry;
- retry classification, bounded retry/backoff and immutable attempt lineage;
- audited `ReprocessRequest` contracts for RETRY/BACKFILL/REPLAY/FULL_REBUILD;
- fail-closed unknown-target-commit recovery;
- relational environment-local reprocess and attempt-lineage evidence;
- additive control-plane schema v2 development contract;
- immutable release/delivery contracts and CLI.

## Fabric capture adapter boundary

The framework now has a provider adapter boundary under:

```text
src/fabric_data_framework/adapters/fabric/
```

The contract is:

```text
compiled ExecutionPlan capture unit
    -> FabricCaptureRequest
    -> injected Fabric transport (REST / SDK / CLI / deterministic fake)
    -> FabricNativeRunEvidence
    -> adapter validation
    -> CaptureReceipt
```

Concrete wrappers exist for:

```text
CopyJobCaptureAdapter
CopyActivityCaptureAdapter
DataflowGen2CaptureAdapter
SparkJobCaptureAdapter
```

The adapter layer deliberately does **not** construct credentials, call a hard-coded workspace or pretend one Fabric API is universal. Transport mechanics remain injectable.

Fail-closed guarantees include:

- request engine/kind must match the selected adapter;
- a capture adapter requires `EXTRACT` + `STAGE` and rejects downstream `APPLY/PUBLISH/RECONCILE/COMMIT_STATE/FINALIZE` ownership;
- FAILED/CANCELLED/UNKNOWN native runs never produce a success receipt;
- native execution kind and landing reference must match;
- requested/observed snapshot identity must match;
- for FRAMEWORK-owned bounded movement, observed lower/upper source bounds must match the requested bounds;
- successful native evidence is correlated through immutable `CaptureReceipt.native_run_id`.

This is **adapter-contract/reference evidence only**. No real Fabric API, workspace, connection, capacity or dataset was invoked by these tests.

## Recovery core

Canonical recovery modes remain:

```text
NORMAL
RETRY
BACKFILL
REPLAY
FULL_REBUILD
```

The framework now implements the reusable recovery core rather than treating these as vocabulary only.

### Failure classification

```text
RETRYABLE
NON_RETRYABLE
UNKNOWN_OUTCOME
```

Unknown/unclassified Python exceptions are conservative `NON_RETRYABLE`; only explicitly classified transient failures are automatically retried.

### Attempt lineage

Every attempt receives immutable linkage:

```text
dataset_run_id
root_dataset_run_id
previous_dataset_run_id
attempt
run_mode
reprocess_request_id
```

The reference proof includes the required operational shape:

```text
attempt 1  FAILED / retryable
attempt 2  SUCCEEDED
```

### Unknown target-commit recovery

Blind retry after an ambiguous write is prohibited.

```text
UnknownCommitOutcomeError
    -> reconcile target outcome
         COMMITTED     -> converge SUCCEEDED; do not write again
         NOT_COMMITTED -> retry may proceed if policy allows
         UNRESOLVED    -> stop/fail; no blind duplicate write
```

A missing reconciliation callback is also fail-closed.

### Reprocess requests

`ReprocessRequest` validates source-controlled/operator intent boundaries:

- RETRY requires the original dataset run;
- BACKFILL requires explicit lower/upper range bounds;
- REPLAY requires original run or quarantine identifiers;
- FULL_REBUILD requires explicit `authoritative_reset=true` intent;
- semantic request identity is immutable while lifecycle status may move `PENDING -> RUNNING -> SUCCEEDED/FAILED/CANCELLED`.

`updated_at` is recorded when lifecycle status changes.

### Relational evidence

Control-plane v2 development schema now includes environment-local:

```text
reprocess_request
dataset_attempt_lineage
```

These rows are never promotable between DEV/UAT/PROD.

## Recovery scope that is still incomplete

Do not overread the core runtime as full strategy-specific recovery.

Still required:

- strategy-specific retained source boundary/restaging behavior for every capture family;
- quarantine payload replay wiring that marks `replayed_by_dataset_run_id` end to end;
- actual FULL_REBUILD target/state reset/rebuild orchestration;
- persistent production repository transaction/concurrency proof;
- Fabric-native resume/replay semantics for Copy Job/Dataflow/Mirroring where the native service owns progress;
- operator CLI/API (`status`, `retry`, `backfill`, `replay`, `rebuild`) on a supported persistent store.

## Capture/apply executor separation

Source-controlled execution policy:

```text
execution.engine
execution.capability_profile
execution.progress_owner
    -> capture / movement

execution.apply_engine
execution.apply_capability_profile
    -> apply
```

The immutable plan resolves both to concrete values before execution. `AUTO` is a policy input, not an execution-time hidden switch.

Generic native profiles do not automatically certify target `UPSERT/SCD1/SCD2`. The default framework apply path remains Spark/framework unless a named apply profile explicitly proves semantic equivalence.

## Dataflow Gen2 incremental hybrid

The named profile:

```text
dataflow_gen2_incremental_bucket_v1
```

certifies Dataflow only for its bounded incremental capture/staging role:

```text
capture_strategy = WATERMARK
capture engine   = DATAFLOW_GEN2
progress_owner   = FABRIC_NATIVE
composite WM     = NOT CERTIFIED
native apply     = NOT CERTIFIED
```

Valid plan:

```text
Dataflow Gen2 incremental capture/stage
    -> CaptureReceipt
    -> framework SCD1 or UPSERT
    -> reconcile / state / audit
```

Dataflow bucket replacement is not mislabeled as generic SCD1/UPSERT.

## Control-plane promotion boundary

Promotable definitions include:

```text
dataset
dataset_contract
load_policy
ordering_policy
execution_policy
apply_execution_policy
orchestration_policy
data_quality_policy
reconciliation_policy
```

Environment-local runtime state/evidence includes:

```text
schema_migration_history
runtime_override
watermark
dataset_state
dataset_lease
pipeline_run
dataset_run
dataset_attempt_lineage
capture_receipt
step_run
reconciliation_result
quarantine_batch
schema_change
reprocess_request
deployment_history
```

The two sets are disjoint and cover the current schema.

## Current external boundary

No enterprise Fabric workspace, capacity, tenant setting, RBAC, networking, gateway, connection, credential, production dataset or runtime state has been changed by this hardening work.

SQLAlchemy/SQLite, in-memory targets and fake Fabric transports are deterministic contract proof. They are not real Fabric production evidence.

## Exact next implementation sequence

1. Implement canonical **CDC event normalization**: I/U/D envelope, source event identity, ordering position and poison/invalid-event failure semantics.
2. Implement CDC dedupe/conflict/out-of-order handling and checkpoint commit gates.
3. Certify `CDC -> UPSERT`, `CDC -> SCD1` and `CDC -> SCD2` as separate capture/apply combinations.
4. Implement snapshot/bootstrap -> CDC handoff with no gap/double apply.
5. Complete strategy-specific recovery wiring for retained ranges, quarantine replay and FULL_REBUILD state reset.
6. Add APPEND identity/collision semantics.
7. Add general schema-evolution and cross-strategy late/out-of-order policy contracts.
8. Add a supported persistent control-plane repository/operator surface.
9. Implement a real Fabric transport/API adapter and prove at least one DEV hybrid: native capture -> `CaptureReceipt` -> framework SCD1/UPSERT.
10. Re-run production-readiness and guarantee audits, then decide the next immutable release scope/version.

## Documentation obligation

New conversations must read the canonical docs before substantive work:

```text
docs/ECOSYSTEM_BLUEPRINT.md
docs/PROJECT_BLUEPRINT.md
docs/PRODUCTION_REQUIREMENTS.md
docs/EXECUTION_ENGINE_STRATEGY.md
docs/FABRIC_EXECUTION_MODEL.md
docs/REPOSITORY_STRUCTURE.md
docs/CONTROL_PLANE_DESIGN.md
docs/CICD_DESIGN.md
docs/PRODUCTION_READINESS_AUDIT.md
docs/GUARANTEE_COVERAGE.md
docs/CURRENT_STATUS.md
```

If code/tests and docs differ, implementation evidence wins temporarily and the docs must be repaired in the same coherent slice.
