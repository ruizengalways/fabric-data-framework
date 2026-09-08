# Code reading guide

This is the canonical source-reading guide for `fabric-data-framework`. Use it to trace one dataset from semantic configuration through planning, orchestration, execution, durable outcome, recovery, certification, and release.

It does not replace `docs/ARCHITECTURE.md`, `docs/DATA_PATTERNS.md`, `docs/OPERATIONS.md`, `docs/REPAIR_AND_REBUILD.md`, `docs/TESTING_AND_CERTIFICATION.md`, or `docs/RELEASE.md`.

## 1. Core mental model

```text
DatasetConfig
-> effective config
-> capability validation
-> execution-plan compilation
-> immutable ExecutionPlan
-> dependency planning / ready waves
-> execution backend
-> physical child/executor
-> capture / quality / apply / reconciliation
-> durable framework outcome
-> recovery/evidence as required
```

The central invariant is:

```text
provider Completed != framework semantic success
```

A provider terminal status is only one execution fact. Reconciliation, commit proof, exact outcome identity, and state-transition rules still determine framework success.

## 2. Read the repository in this order

```text
1. README.md
2. docs/ARCHITECTURE.md
3. docs/DATA_PATTERNS.md
4. docs/CODE_READING_GUIDE.md
5. src/fabric_data_framework/README.md
6. core runtime modules
7. focused tests for the owner module
8. docs/OPERATIONS.md for transient runtime recovery
9. docs/REPAIR_AND_REBUILD.md for data-correctness reconstruction/cutover
10. docs/TESTING_AND_CERTIFICATION.md
11. docs/RELEASE.md
```

Do not use `docs/OPERATIONS.md` as the canonical manual for bad Bronze/Silver/Gold data, `FULL_REBUILD`, contaminated descendants, v1/v2 cutover, UAT, rollback, or physical target replacement. Those belong to `docs/REPAIR_AND_REBUILD.md`.

## 3. Package ownership

The installable package lives under `src/fabric_data_framework/`.

| Folder | Primary ownership |
|---|---|
| `metadata/` | DatasetConfig, execution metadata, effective config, capability resolution |
| `contracts/` | stable immutable cross-layer contracts only |
| `capture/` | source/capture fidelity, windows, events, onboarding |
| `apply/` | target state/history transition semantics |
| `quality/` | DQ, schema, quarantine, reconciliation |
| `data_plane/` | staging/Bronze helper contracts |
| `orchestration/` | dependency graph, ready waves, dispatch/failure isolation |
| `execution/` | plan compilation, execution backends, Pipeline child, bounded execution helpers |
| `control_plane/` | durable operational state, checkpoints, audits, outcomes |
| `recovery/` | retry/replay/rebuild/impact/cutover/unknown-commit safety |
| `adapters/` | Fabric/provider transports and auth |
| `evidence/` | approved environment facts and retained proof |
| `certification/` | installed-wheel and bounded framework certification |
| `deployment/` | project/candidate materialization and provenance |
| `extensions/` | bounded extension contracts/registry |
| `cli/` | presentation/composition leaf |

## 4. Shortest useful core-runtime path

### Step 1 — Dataset semantics

Read:

```text
src/fabric_data_framework/metadata/config.py
```

Keep capture and apply separate:

```text
capture_strategy = what source facts arrive
apply_strategy   = how captured facts alter the target
```

### Step 2 — Source truth and fidelity

Read:

```text
src/fabric_data_framework/capture/semantic_contracts.py
src/fabric_data_framework/capture/onboarding.py
src/fabric_data_framework/capture/full.py
src/fabric_data_framework/capture/watermark.py
src/fabric_data_framework/capture/cdc.py
```

The framework may preserve source facts; it may not invent history or delete fidelity the source does not expose.

### Step 3 — Capability resolution

Read:

```text
src/fabric_data_framework/metadata/capabilities.py
```

Native capture does not imply native final-target apply.

### Step 4 — Immutable execution-plan contracts

Read:

```text
src/fabric_data_framework/contracts/execution_plan.py
```

This module is deliberately contract-only. It owns:

```text
ExecutionKind
ExecutionRole
ExecutionUnit
ExecutionPlan
```

It does not import capability resolution or compile plans.

### Step 5 — Execution-plan compiler

Read:

```text
src/fabric_data_framework/execution/plan_compiler.py
```

This module owns:

```text
compile_execution_plan(...)
build_default_execution_plan(...)
```

The dependency direction is intentionally one-way:

```text
metadata/capabilities
        |
        v
execution/plan_compiler.py
        |
        v
contracts/execution_plan.py
```

`contracts/execution_plan.py` must never re-export compiler functions as compatibility aliases. This is a hard-cut ownership boundary.

The compiled immutable plan carries deterministic `plan_hash` identity used by parent/child correlation.

### Step 6 — Dependency planning and dispatch

Read:

```text
src/fabric_data_framework/orchestration/planner.py
src/fabric_data_framework/orchestration/dispatcher.py
```

The planner decides WHAT/WHEN may run. The backend decides WHERE/HOW it runs.

Recommended focused tests:

```text
tests/test_orchestration_planner.py
tests/test_dispatcher_backend_contract.py
tests/test_relational_dispatcher.py
```

## 5. Backend paths

### In-process reference backend

```text
src/fabric_data_framework/execution/backends/in_process.py
```

This uses `build_default_execution_plan(...)` from `execution/plan_compiler.py` to create a deterministic single-unit reference plan.

### Fabric Pipeline backend

```text
src/fabric_data_framework/execution/backends/fabric_pipeline.py
src/fabric_data_framework/adapters/fabric/pipeline.py
src/fabric_data_framework/adapters/fabric/rest.py
src/fabric_data_framework/execution/pipeline_child.py
```

Parent-side shape:

```text
compile exact plan
-> construct provider invocation
-> invoke Fabric Pipeline
-> observe provider terminal state
-> read exact durable framework outcome
```

The remote child recompiles the current effective config through `src/fabric_data_framework/execution/plan_compiler.py` and requires the resulting `plan_hash` to match the parent request before physical mutation proceeds.

## 6. Capture, Bronze, DQ, apply, checkpoint

There is intentionally no universal monolithic `source -> Bronze -> Silver -> checkpoint` function. A real physical executor composes reusable owners:

```text
1. read committed progress/checkpoint
2. freeze/derive source capture window
3. execute capture/provider read
4. retain CaptureReceipt/source evidence
5. stage/normalize source facts
6. run schema/DQ
7. quarantine if allowed
8. plan/apply target mutation
9. reconcile candidate/target state
10. prove target commit when required
11. advance semantic checkpoint only after proof
12. persist/return durable framework outcome
```

For a bounded framework-owned reference composition, inspect:

```text
src/fabric_data_framework/certification/pipeline_child.py
```

That is certification/reference execution, not a universal domain implementation.

## 7. Concrete data-pattern traces

### FULL + REPLACE

```text
src/fabric_data_framework/capture/full.py
-> src/fabric_data_framework/data_plane/staging.py
-> src/fabric_data_framework/apply/replace.py
-> src/fabric_data_framework/quality/full_refresh.py
```

Safety order is candidate -> reconcile -> publish -> state cutover, never delete-first-and-hope.

### WATERMARK + SCD1/SCD2

```text
src/fabric_data_framework/capture/watermark.py
-> src/fabric_data_framework/apply/scd1.py
or
-> src/fabric_data_framework/apply/scd2.py
```

SCD2 is a target representation, not a source capture strategy.

### WATERMARK + LOOKBACK + APPEND

```text
src/fabric_data_framework/capture/watermark.py
-> src/fabric_data_framework/execution/append.py
-> src/fabric_data_framework/apply/append.py
-> src/fabric_data_framework/quality/append.py
```

Keep these separate:

```text
entity key != event identity != incremental cursor
```

Raw/Event Bronze may retain repeated source observations from lookback. Silver APPEND deduplicates under `append_identity`. Exact replay is a no-op; same identity with different business payload fails closed. If two legitimate events are indistinguishable at source, the framework cannot invent event fidelity.

## 8. Control Plane and transient recovery

Read:

```text
src/fabric_data_framework/control_plane/repository.py
src/fabric_data_framework/contracts/target_operation.py
src/fabric_data_framework/control_plane/target_operation_journal.py
src/fabric_data_framework/recovery/target_probe.py
src/fabric_data_framework/recovery/fabric_warehouse.py
src/fabric_data_framework/recovery/runtime.py
src/fabric_data_framework/recovery/replay.py
```

Ambiguous commit classification is fail-closed:

```text
COMMITTED     -> converge to success; do not mutate again
NOT_COMMITTED -> bounded retry may proceed
UNRESOLVED    -> stop; no blind retry
```

Use `docs/OPERATIONS.md` for RETRY, BACKFILL, REPLAY, unknown commit, dependency recovery, and runtime incidents.

## 9. Data-correctness rebuild and cutover

Switch to this path when data or transformation logic is wrong:

```text
src/fabric_data_framework/contracts/rebuild.py
-> src/fabric_data_framework/recovery/rebuild.py
-> src/fabric_data_framework/contracts/rebuild_impact.py
-> src/fabric_data_framework/recovery/rebuild_impact.py
-> src/fabric_data_framework/contracts/target_version.py
-> src/fabric_data_framework/recovery/target_cutover.py
```

The three `RunMode.FULL_REBUILD` scopes are:

```text
TARGET_ONLY
CAPTURE_AND_TARGET
AUTHORITATIVE_RESET
```

Impact planning rebuilds only the first untrustworthy root plus downstream descendants; unrelated branches remain untouched, while disabled-but-contaminated datasets are still reported.

The canonical operator runbook is `docs/REPAIR_AND_REBUILD.md`. It owns v1/v2 build, UAT, approval, cutover, rollback, and the rule that old v1 is never automatically deleted.

## 10. Implementation/domain repository boundary

A real domain repo such as `fabric-health` owns:

```text
DatasetConfig
source-to-target mappings
business DQ/reconciliation
execution groups/dependencies
Fabric environment bindings
physical v1/v2 target names
provider-specific logical binding
UAT/business approval
bounded project extensions/adapters where required
```

The reusable framework owns semantics, immutable contracts, planning/runtime, recovery, certification, and exact candidate evidence.

Read:

```text
docs/IMPLEMENTATION_PROJECT.md
src/fabric_data_framework/deployment/project.py
src/fabric_data_framework/deployment/delivery.py
src/fabric_data_framework/capture/onboarding.py
src/fabric_data_framework/metadata/capabilities.py
```

## 11. Certification and release order

Read runtime first, then:

```text
docs/TESTING_AND_CERTIFICATION.md
src/fabric_data_framework/certification/installed.py
src/fabric_data_framework/certification/semantic.py
src/fabric_data_framework/certification/bounded.py
src/fabric_data_framework/certification/simple.py
src/fabric_data_framework/certification/unified.py
```

Proof levels are not interchangeable:

```text
source CI
!= installed-wheel acceptance
!= real Fabric certification
!= release authorization
```

Then read:

```text
docs/RELEASE.md
src/fabric_data_framework/deployment/candidate_artifact.py
src/fabric_data_framework/evidence/release_readiness.py
src/fabric_data_framework/evidence/candidate_certification.py
```

Framework candidate identity remains exactly:

```text
framework_artifact_sha256
+
integration_inputs_hash
```

No customer/domain release identity participates in framework candidate certification.

## 12. Practical reading sessions

### Session 1 — semantics and plan

```text
docs/ARCHITECTURE.md
docs/DATA_PATTERNS.md
src/fabric_data_framework/metadata/config.py
src/fabric_data_framework/capture/semantic_contracts.py
src/fabric_data_framework/metadata/capabilities.py
src/fabric_data_framework/contracts/execution_plan.py
src/fabric_data_framework/execution/plan_compiler.py
```

### Session 2 — orchestration and execution

```text
src/fabric_data_framework/orchestration/planner.py
src/fabric_data_framework/orchestration/dispatcher.py
src/fabric_data_framework/execution/backends/in_process.py
src/fabric_data_framework/execution/backends/fabric_pipeline.py
src/fabric_data_framework/execution/pipeline_child.py
src/fabric_data_framework/control_plane/repository.py
```

### Session 3 — choose the relevant semantic/recovery path

APPEND:

```text
src/fabric_data_framework/capture/watermark.py
src/fabric_data_framework/execution/append.py
src/fabric_data_framework/apply/append.py
src/fabric_data_framework/quality/append.py
```

Repair/cutover:

```text
src/fabric_data_framework/contracts/rebuild.py
src/fabric_data_framework/recovery/rebuild.py
src/fabric_data_framework/contracts/rebuild_impact.py
src/fabric_data_framework/recovery/rebuild_impact.py
src/fabric_data_framework/contracts/target_version.py
src/fabric_data_framework/recovery/target_cutover.py
docs/REPAIR_AND_REBUILD.md
```

## 13. Change-location map

| Change | First owner | Follow with |
|---|---|---|
| DatasetConfig field | `src/fabric_data_framework/metadata/config.py` | onboarding -> capabilities -> compiler -> docs/tests |
| ExecutionPlan structure | `src/fabric_data_framework/contracts/execution_plan.py` | compiler -> consumers -> tests/docs |
| Execution-plan compilation | `src/fabric_data_framework/execution/plan_compiler.py` | capabilities -> backends/child -> tests/docs |
| Source capture semantic | `src/fabric_data_framework/capture/` | capabilities -> adapter -> tests/docs |
| APPEND identity/dedup | `src/fabric_data_framework/apply/append.py` | execution/append -> quality/append -> tests/docs |
| Dependency scheduling | `src/fabric_data_framework/orchestration/planner.py` | dispatcher -> backend contract -> tests |
| Fabric Pipeline invocation | `src/fabric_data_framework/execution/backends/fabric_pipeline.py` | adapter -> REST -> child contract |
| Remote child contract | `src/fabric_data_framework/execution/pipeline_child.py` | parent backend -> certification child -> tests |
| Unknown commit | `src/fabric_data_framework/contracts/target_operation.py` | recovery -> journal -> operations docs |
| FULL_REBUILD scope/state | `src/fabric_data_framework/contracts/rebuild.py` | recovery/rebuild -> repair docs/tests |
| Rebuild impact | `src/fabric_data_framework/contracts/rebuild_impact.py` | recovery/rebuild_impact -> repair docs/tests |
| Target cutover | `src/fabric_data_framework/contracts/target_version.py` | recovery/target_cutover -> repair docs/tests |
| Certification | `src/fabric_data_framework/certification/` | testing docs -> exact Fabric evidence |
| Release criteria | `release/<version>/readiness-spec.json` | readiness evidence -> candidate aggregation -> release workflow |

## 14. Debug by identities

Trace:

```text
pipeline_run_id
-> dataset_run_id
-> effective_config_hash
-> execution_plan_hash
-> provider run identity
-> CaptureReceipt
-> reconciliation result
-> target operation evidence
-> DatasetRunAudit
```

## 15. Invariants worth memorizing

```text
capture and apply are orthogonal
truthful downstream history <= captured source fidelity
contracts contain stable immutable contracts; compiler lives in execution/plan_compiler.py
DatasetConfig -> effective config -> capability validation -> immutable ExecutionPlan
Fabric/provider Completed != framework semantic success
reconciliation may block state/checkpoint advance
UNRESOLVED commit -> no blind retry
runtime state stays environment-local
source CI != installed-wheel acceptance != Fabric PASS
framework candidate identity = framework_artifact_sha256 + integration_inputs_hash
rebuild != purge
cutover != delete old version
```

The documentation path-existence guard in `tests/test_current_docs_consistency.py` intentionally fails closed on clear concrete repo paths so code-reading documentation cannot silently drift to nonexistent files.