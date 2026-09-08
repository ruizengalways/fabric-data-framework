# Code reading guide

This is the canonical guide for reading `fabric-data-framework` source code as an end-to-end system.

Use it to understand **where execution starts, what each layer owns, which file to read next, and how one dataset moves from semantic configuration to durable framework outcome**. It does not replace architecture, data-pattern, operations, repair, certification, or release runbooks.

## 1. Keep one mental model

Think of the framework as five cooperating layers:

```text
1. WHAT THE DATA MEANS
   DatasetConfig + source/capture/apply/DQ semantics

2. WHAT MUST HAPPEN
   capability resolution + immutable ExecutionPlan

3. WHEN IT MAY RUN
   dependency planning + ready waves + failure isolation

4. WHERE/HOW IT RUNS
   in-process or Fabric/provider backend + physical child executor

5. HOW SUCCESS IS PROVEN
   Control Plane audit + reconciliation + commit/checkpoint evidence
```

The normal runtime path is:

```text
DatasetConfig
    |
    v
semantic validation / effective config
    |
    v
capability resolution
    |
    v
ExecutionPlan
    |
    v
dependency plan / ready wave
    |
    v
backend
    |
    +-----------------------+
    |                       |
    v                       v
in-process              Fabric Pipeline
reference path          provider path
                            |
                            v
                    remote Pipeline child
                            |
                            v
              capture / stage / quality / apply
                            |
                            v
                  reconciliation / commit
                            |
                            v
                  durable framework outcome
                            |
                            v
                 parent reads exact outcome
                            |
                            v
                  aggregate Pipeline status
```

The most important invariant is:

```text
provider Completed != framework semantic success
```

A provider job can finish while the framework still fails because durable outcome, reconciliation, commit proof, or state-transition evidence is missing or contradictory.

## 2. Read the repository in this order

Start with the human-facing boundaries before reading implementation files:

```text
1. README.md
2. docs/ARCHITECTURE.md
3. docs/DATA_PATTERNS.md
4. docs/CODE_READING_GUIDE.md
5. src/fabric_data_framework/README.md
6. core runtime modules
7. tests for the owner module you just read
8. docs/OPERATIONS.md for transient runtime recovery
9. docs/REPAIR_AND_REBUILD.md for data-correctness reconstruction/cutover
10. docs/TESTING_AND_CERTIFICATION.md
11. docs/RELEASE.md
12. evidence/ and cli/ only after the core runtime is clear
```

Do not use `docs/OPERATIONS.md` as the canonical manual for bad Bronze/Silver/Gold data, `FULL_REBUILD` mechanics, contaminated descendants, v1/v2 cutover, UAT, or rollback. Those belong to `docs/REPAIR_AND_REBUILD.md`.

## 3. Package ownership

The installable code lives under `src/fabric_data_framework/`.

| Folder | Question it answers |
|---|---|
| `metadata/` | What is this dataset configured to mean/do? |
| `contracts/` | What immutable objects cross layer boundaries? |
| `capture/` | What source facts/windows/events were captured? |
| `apply/` | How do captured facts change target state/history? |
| `quality/` | What is valid, quarantined, reconciled, or blocked? |
| `data_plane/` | How are staging/Bronze helper contracts represented? |
| `orchestration/` | Which datasets may run, and in what dependency order? |
| `execution/` | How an immutable plan is executed by backends/children/helpers |
| `control_plane/` | Where framework config, checkpoints, audits, and outcomes live |
| `recovery/` | How retry/replay/rebuild/cutover/unknown commit remain safe |
| `adapters/` | How Fabric/provider APIs and transports are called |
| `certification/` | How exact installed wheel bytes prove framework behavior |
| `evidence/` | How approved environment facts become retained proof |
| `deployment/` | How project/candidate artifacts are materialized |
| `extensions/` | What bounded extension contracts projects may use |
| `cli/` | Presentation/composition only |

The useful dependency shape is:

```text
semantic contracts
  metadata / contracts / capture / apply / quality
            |
            v
planning + orchestration + execution
            |
            v
control plane + recovery
            |
            v
provider adapters
            |
            v
evidence / certification / deployment
            |
            v
CLI presentation
```

This is a reading model, not a claim that every Python import is perfectly linear.

## 4. Shortest useful core-runtime path

### Step 1 — Dataset semantics

Read:

```text
src/fabric_data_framework/metadata/config.py
```

Focus on `CaptureStrategy`, `ApplyStrategy`, `RunMode`, `ExecutionEngine`, `LoadPolicy`, `DatasetConfig`, `RuntimeOverride`, `EffectiveDatasetConfig`, and `resolve_effective_config(...)`.

Do not move on until this distinction is clear:

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

The capture layer may preserve source facts; it may not invent history the source did not provide.

```text
FULL snapshot -> current/snapshot facts
WATERMARK     -> bounded changed observations
CDC           -> ordered source change facts when the provider exposes them
```

### Step 3 — Capability resolution

Read:

```text
src/fabric_data_framework/metadata/capabilities.py
```

This decides which physical execution engines can truthfully satisfy the configured semantics.

Key rule:

```text
native capture does not imply native final-target apply
```

### Step 4 — Execution plan contract and current compiler

Read:

```text
src/fabric_data_framework/contracts/execution_plan.py
```

Current contents are intentionally described exactly as they exist today:

```text
immutable contracts
  ExecutionKind
  ExecutionRole
  ExecutionUnit
  ExecutionPlan

compiler/planning logic in the same module
  compile_execution_plan(...)
  build_default_execution_plan(...)
```

This mixed ownership is a known architecture issue. Until an explicit hard-cut refactor moves compiler logic, this file remains the current source of truth for both contract and compilation.

The immutable plan carries a deterministic `plan_hash` used later to prove the remote child executed the same plan the parent intended.

### Step 5 — Dependency planning

Read:

```text
src/fabric_data_framework/orchestration/planner.py
```

Focus on dependency validation, cycle detection, effective selection, ready datasets, blocking dependencies, concurrency, and aggregate Pipeline status.

The planner does not move data.

```text
planner = WHAT/WHEN MAY RUN
backend = WHERE/HOW IT RUNS
```

### Step 6 — Parent orchestration loop

Read:

```text
src/fabric_data_framework/orchestration/dispatcher.py
```

The parent creates a Pipeline run, builds the dispatch plan, repeatedly selects dependency-ready waves, executes them through a backend, blocks only descendants of failed dependencies, and finally aggregates the Pipeline outcome.

The default behavior is fail-at-end with dataset fault isolation: an unrelated sibling may continue even when another branch fails.

## 5. Choose one backend path

### In-process reference path

Read:

```text
src/fabric_data_framework/execution/backends/in_process.py
```

This is the easiest path for understanding contracts without Fabric REST noise. One dataset becomes a dispatch request, an execution plan, a dataset executor call, and finally a terminal dataset outcome.

### Real Fabric Pipeline parent path

Read:

```text
src/fabric_data_framework/execution/backends/fabric_pipeline.py
src/fabric_data_framework/adapters/fabric/pipeline.py
src/fabric_data_framework/adapters/fabric/rest.py
src/fabric_data_framework/execution/pipeline_child.py
```

Parent-side shape:

```text
compile exact plan
-> build provider invocation
-> invoke Fabric Data Pipeline
-> poll provider terminal state
-> read exact durable framework outcome
```

`Completed` is not enough. If the provider completes but the expected framework-owned durable result is absent, the framework fails closed.

## 6. Remote Pipeline child contract

Read:

```text
src/fabric_data_framework/execution/pipeline_child.py
```

The child receives exactly the framework correlation parameters defined by the current contract, including dataset/run identity, effective config hash, and execution plan hash.

Before physical mutation, it verifies that current deployed configuration and a freshly compiled plan still match the parent request. Only then may the domain/environment physical executor run.

Generic child flow:

```text
parameters
-> parse exact child request
-> validate dataset/effective-config hash/plan hash
-> physical executor
-> durable DatasetRunAudit / outcome
-> parent reads exact outcome
```

The child contract owns terminal framework outcome semantics. The project-specific physical executor owns project data mutation.

## 7. Where capture, Bronze, DQ, apply, and checkpoint fit

There is intentionally no universal monolithic `source -> Bronze -> Silver -> checkpoint` function.

A real physical executor composes the reusable primitives for that dataset:

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
12. return durable framework outcome
```

Owners:

```text
capture/       source/window/event truth
data_plane/    staging/Bronze helper contracts
quality/       validation + reconciliation
apply/         target transition semantics
recovery/      idempotency/ambiguous commit/reconstruction safety
control_plane/ durable operational state and evidence
```

For a bounded framework-owned composition, inspect:

```text
src/fabric_data_framework/certification/pipeline_child.py
```

That module is a certification executor, not a universal domain implementation.

## 8. Concrete trace: FULL + REPLACE

Useful owner path:

```text
src/fabric_data_framework/capture/full.py
-> src/fabric_data_framework/data_plane/staging.py
-> src/fabric_data_framework/apply/replace.py
-> src/fabric_data_framework/quality/full_refresh.py
```

Safety order:

```text
capture complete
-> build replacement candidate
-> reconcile
-> publish
-> commit semantic progress/outcome
```

Not:

```text
delete target first
-> hope validation passes later
```

## 9. Concrete trace: WATERMARK + SCD1/SCD2

For watermark capture, start with:

```text
src/fabric_data_framework/capture/watermark.py
```

Then read the target strategy you need:

```text
src/fabric_data_framework/apply/scd1.py
src/fabric_data_framework/apply/scd2.py
```

Keep this rule in mind:

```text
SCD2 is a target representation, not a source capture strategy
```

The source query, provider job, or target mutation alone does not authorize checkpoint advance. Reconciliation and framework state-commit rules still apply.

## 10. Concrete trace: WATERMARK + LOOKBACK + APPEND

For application audit/change-log data, Jira-style history, workflow logs, or other incrementally readable business-event tables, use this concrete reading path:

```text
src/fabric_data_framework/capture/watermark.py
    |
    v
src/fabric_data_framework/execution/append.py
    |
    v
src/fabric_data_framework/apply/append.py
    |
    v
src/fabric_data_framework/quality/append.py
```

Interpretation:

```text
capture/watermark.py
  bounded cursor + lookback/overlap observation semantics

execution/append.py
  capture-neutral APPEND batch coordination

apply/append.py
  stable append_identity
  exact replay -> no-op
  same identity + same payload -> idempotent
  same identity + different payload -> fail closed

quality/append.py
  APPEND reconciliation
```

Always keep these concepts distinct:

```text
entity key != event identity != incremental cursor
```

Raw/Event Bronze may retain repeated source observations from overlap. Silver APPEND deduplicates under the declared event identity. If two legitimate events cannot be distinguished by source-controlled identity, the framework cannot invent event fidelity.

For semantic selection rules, read `docs/DATA_PATTERNS.md`.

## 11. Control Plane before recovery

Read the framework repository protocol before diving into recovery internals:

```text
src/fabric_data_framework/control_plane/repository.py
```

It shows the durable state runtime code expects: deployed configs, checkpoints, Pipeline/dataset audits, capture receipts, step/reconciliation records, quarantine references, attempt lineage, and reprocess requests.

Mental split:

```text
Control Plane = small mutable operational truth
Data Plane    = large business rows / Bronze / Silver / Gold
```

## 12. Transient runtime recovery path

After the happy path is clear, read retry/unknown-commit behavior:

```text
src/fabric_data_framework/contracts/target_operation.py
src/fabric_data_framework/control_plane/target_operation_journal.py
src/fabric_data_framework/recovery/target_probe.py
src/fabric_data_framework/recovery/fabric_warehouse.py
src/fabric_data_framework/recovery/runtime.py
src/fabric_data_framework/recovery/replay.py
```

The dangerous case is an ambiguous commit:

```text
target may have committed
+ acknowledgement is lost
-> client sees exception
```

The framework classifies:

```text
COMMITTED     -> converge to success; do not mutate again
NOT_COMMITTED -> bounded retry may proceed
UNRESOLVED    -> stop; no blind retry
```

Then read `docs/OPERATIONS.md` for operator RETRY, REPLAY, BACKFILL, dependency recovery, and incident handling.

## 13. Data-correctness rebuild and cutover path

When Bronze/Silver/Gold data or logic is actually wrong, do **not** keep reading generic runtime recovery. Switch to this path:

```text
src/fabric_data_framework/contracts/rebuild.py
    |
    v
src/fabric_data_framework/recovery/rebuild.py
    |
    v
src/fabric_data_framework/contracts/rebuild_impact.py
    |
    v
src/fabric_data_framework/recovery/rebuild_impact.py
    |
    v
src/fabric_data_framework/contracts/target_version.py
    |
    v
src/fabric_data_framework/recovery/target_cutover.py
```

Interpretation:

```text
contracts/rebuild.py
  FULL_REBUILD scope + post-rebuild runtime-state contract

recovery/rebuild.py
  exact requested/completed scope
  target commit + reconciliation before state cutover

contracts/rebuild_impact.py
  RepairIssueOrigin + immutable RebuildImpactPlan

recovery/rebuild_impact.py
  root + downstream descendants only
  unrelated branches excluded
  disabled contaminated datasets still reported

contracts/target_version.py
  TargetVersionSpec + cutover request/gate/result contracts

recovery/target_cutover.py
  candidate/UAT/approval/generation/idempotency cutover coordinator
```

The three `FULL_REBUILD` scopes are:

```text
TARGET_ONLY
CAPTURE_AND_TARGET
AUTHORITATIVE_RESET
```

The canonical operator runbook for these decisions is `docs/REPAIR_AND_REBUILD.md`. It owns dependency contamination, v1/v2 strategy, UAT, cutover, rollback, and the rule that old v1 is never automatically deleted.

## 14. Real implementation/domain repository boundary

A consuming project such as `fabric-health` owns:

```text
DatasetConfig
source-to-target mappings
business DQ/reconciliation
execution groups/dependencies
Fabric environment bindings
physical v1/v2 target names
provider-specific logical binding
UAT/business approval
bounded project adapters/extensions where required
```

The framework owns reusable semantics, safety contracts, planning/runtime, recovery, and certification.

Read:

```text
docs/IMPLEMENTATION_PROJECT.md
src/fabric_data_framework/deployment/project.py
src/fabric_data_framework/deployment/delivery.py
src/fabric_data_framework/capture/onboarding.py
src/fabric_data_framework/metadata/capabilities.py
```

`project-init` must not guess source semantics or create infrastructure. Static project validation is not live Fabric proof.

## 15. Certification and release reading order

After runtime and recovery are understood, read:

```text
docs/TESTING_AND_CERTIFICATION.md
src/fabric_data_framework/certification/installed.py
src/fabric_data_framework/certification/semantic.py
src/fabric_data_framework/certification/bounded.py
src/fabric_data_framework/certification/simple.py
src/fabric_data_framework/certification/unified.py
```

The proof chain remains:

```text
source tests
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

## 16. How to read tests without drowning

Read tests after the owning production module, not before.

Recommended orchestration/runtime starting points are real repository files:

```text
tests/test_orchestration_planner.py
tests/test_dispatcher_backend_contract.py
tests/test_relational_dispatcher.py
```

Then search by the exact public function/class you are studying and read only the focused tests around that contract.

For rebuild/cutover work, the relevant source-contract tests include:

```text
tests/test_rebuild_impact.py
tests/test_target_version_cutover.py
```

The documentation path-existence guard in `tests/test_current_docs_consistency.py` intentionally fails closed on clear repo-root references such as `src/...`, `tests/...`, `.github/...`, `release/...`, and `certification/...` when they point to something that does not exist. Placeholder paths such as `release/<version>/...` are intentionally excluded.

## 17. Practical three-session reading plan

### Session 1 — semantics and plan

```text
docs/ARCHITECTURE.md
docs/DATA_PATTERNS.md
src/fabric_data_framework/metadata/config.py
src/fabric_data_framework/capture/semantic_contracts.py
src/fabric_data_framework/capture/onboarding.py
src/fabric_data_framework/metadata/capabilities.py
src/fabric_data_framework/contracts/execution_plan.py
```

Goal: explain what a dataset says it needs and how that becomes an immutable physical plan.

### Session 2 — orchestration and execution

```text
src/fabric_data_framework/orchestration/planner.py
src/fabric_data_framework/orchestration/dispatcher.py
src/fabric_data_framework/execution/backends/in_process.py
src/fabric_data_framework/execution/backends/fabric_pipeline.py
src/fabric_data_framework/execution/pipeline_child.py
src/fabric_data_framework/control_plane/repository.py
```

Goal: explain how one Pipeline run schedules datasets and proves remote results.

### Session 3 — choose one semantic/recovery path

For APPEND/change-log:

```text
src/fabric_data_framework/capture/watermark.py
src/fabric_data_framework/execution/append.py
src/fabric_data_framework/apply/append.py
src/fabric_data_framework/quality/append.py
```

For data correctness repair/cutover:

```text
src/fabric_data_framework/contracts/rebuild.py
src/fabric_data_framework/recovery/rebuild.py
src/fabric_data_framework/contracts/rebuild_impact.py
src/fabric_data_framework/recovery/rebuild_impact.py
src/fabric_data_framework/contracts/target_version.py
src/fabric_data_framework/recovery/target_cutover.py
docs/REPAIR_AND_REBUILD.md
```

Finish with certification/release only after the runtime path is clear.

## 18. Change-location map

| Change you want | First owner | Then follow |
|---|---|---|
| DatasetConfig field | `src/fabric_data_framework/metadata/config.py` | onboarding -> capabilities -> execution plan -> docs/tests |
| Source capture semantic | `src/fabric_data_framework/capture/` | contracts -> capabilities -> adapter -> tests |
| APPEND identity/dedup | `src/fabric_data_framework/apply/append.py` | execution/append -> quality/append -> tests/docs |
| SCD behavior | `src/fabric_data_framework/apply/` | quality/reconciliation -> executor -> tests |
| Dependency scheduling | `src/fabric_data_framework/orchestration/planner.py` | dispatcher -> backend contract -> tests |
| Execution-plan compilation | `src/fabric_data_framework/contracts/execution_plan.py` today | update all compiler consumers/tests/docs if ownership changes |
| Fabric Pipeline invocation | `src/fabric_data_framework/execution/backends/fabric_pipeline.py` | adapter -> REST -> child contract |
| Remote child contract | `src/fabric_data_framework/execution/pipeline_child.py` | parent backend -> certification child -> tests |
| Unknown commit | `src/fabric_data_framework/contracts/target_operation.py` | recovery -> journal -> operations docs |
| FULL_REBUILD scope/state | `src/fabric_data_framework/contracts/rebuild.py` | recovery/rebuild -> repair docs/tests |
| Rebuild dependency impact | `src/fabric_data_framework/contracts/rebuild_impact.py` | recovery/rebuild_impact -> repair docs/tests |
| Target version/cutover | `src/fabric_data_framework/contracts/target_version.py` | recovery/target_cutover -> repair docs/tests |
| Certification behavior | `src/fabric_data_framework/certification/` | testing docs -> exact Fabric evidence |
| Release criteria | `release/<version>/readiness-spec.json` | readiness evidence -> candidate aggregation -> release workflow |
| CLI command | reusable owner first | `src/fabric_data_framework/cli/` last |

## 19. Debug by identities, not filenames

When debugging a real run, trace:

```text
pipeline_run_id
    |
    +--> dataset_run_id
            |
            +--> effective_config_hash
            +--> execution_plan_hash
            +--> provider run identity
            +--> CaptureReceipt
            +--> reconciliation result
            +--> target operation evidence
            +--> DatasetRunAudit
```

A provider action can succeed while semantic state still fails later at evidence, reconciliation, or state commit.

## 20. Invariants worth memorizing

```text
capture and apply are orthogonal
truthful downstream history <= captured source fidelity
DatasetConfig -> effective config -> capability validation -> immutable ExecutionPlan
Fabric/provider Completed != framework semantic success
reconciliation may block state/checkpoint advance
UNRESOLVED commit -> no blind retry
runtime state stays environment-local
CLI/evidence consume core semantics; they do not redefine them
source CI != installed-wheel acceptance != Fabric PASS
framework candidate identity = framework_artifact_sha256 + integration_inputs_hash
rebuild != purge
cutover != delete old version
```

If you can trace one dataset from `metadata/config.py` through plan, orchestration, backend/child, capture/apply/reconciliation, durable outcome, and the appropriate recovery path, you understand the core runtime architecture.
