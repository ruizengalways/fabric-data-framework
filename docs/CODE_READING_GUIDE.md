# Code reading guide

This is the canonical guide for reading `fabric-data-framework` source code as an end-to-end system.

Use this document when the repository feels too large to browse folder-by-folder. The framework is intentionally split into semantic contracts, orchestration, provider execution, durable state, recovery, evidence, certification and release. The fastest way to understand it is to follow one dataset through those boundaries in execution order.

This document explains **where execution starts, what each layer owns, which file to read next, and what not to read on a first pass**. It does not replace the architecture, data-pattern, operations, certification or release documents; it links those topics to concrete source files.

---

## 1. The one mental model to keep in your head

Do not think of this repository as one large ETL program.

Think of it as five cooperating layers:

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

The normal conceptual path is:

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
orchestration dependency plan
    |
    v
ready-wave backend
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

A Fabric job can finish successfully at the provider level while the framework still fails because the expected durable dataset outcome, reconciliation or commit proof is absent or contradictory.

---

## 2. First understand the repository root

Start with the root folders before opening `src/`.

```text
fabric-data-framework/
├── README.md
├── docs/              human-facing architecture and runbooks
├── src/               installable Python framework
├── tests/             source/unit/contract tests
├── certification/     exact-wheel certification inputs/scripts
├── release/           source-controlled release-readiness policy
├── examples/          examples, not semantic authority
├── .github/workflows/ CI/candidate/certification/release automation
└── pyproject.toml      package metadata, dependencies, CLI and plugin entry points
```

Read these root items in this order:

1. `README.md` — product-level orientation.
2. `docs/ARCHITECTURE.md` — durable system boundaries.
3. `docs/DATA_PATTERNS.md` — source/capture/apply semantics.
4. this file — code call flow.
5. `src/fabric_data_framework/README.md` — compact package lookup map.
6. only then start opening implementation files.

Do **not** start in `tests/`, `.github/workflows/` or `evidence/`. Those areas make much more sense after the runtime path is clear.

---

## 3. The package folders and what they mean

The installable code lives under:

```text
src/fabric_data_framework/
```

Use this ownership model:

| Folder | Question it answers | Read on first pass? |
|---|---|---|
| `metadata/` | What is this dataset configured to mean/do? | **Yes** |
| `contracts/` | What immutable objects cross layer boundaries? | **Yes** |
| `capture/` | What source facts/windows/events were captured? | **Yes** |
| `apply/` | How do captured facts change target state/history? | **Yes** |
| `quality/` | What is valid, quarantined, reconciled or blocked? | **Yes, after apply** |
| `orchestration/` | Which datasets run, in what dependency order? | **Yes** |
| `execution/` | How an immutable plan is executed by a backend/child | **Yes** |
| `control_plane/` | Where dataset config, checkpoints, audits and outcomes live | **Yes** |
| `adapters/` | How external/Fabric provider APIs are called | Second pass |
| `recovery/` | How retry/replay/unknown commit is made safe | Second pass |
| `data_plane/` | Bronze/staging/data-plane helper contracts | Second pass |
| `extensions/` | Controlled implementation-specific extension points | Second pass |
| `deployment/` | How project/config/release artifacts are materialized | After runtime |
| `evidence/` | How real environment facts become retained evidence | After runtime |
| `certification/` | How the framework wheel proves itself in real Fabric | After runtime |
| `cli/` | Command-line presentation/composition | Read last |

A useful dependency picture is:

```text
metadata / contracts / capture / apply / quality
                    |
                    v
             orchestration
                    |
                    v
               execution
                    |
                    v
       control_plane + recovery
                    |
                    v
                adapters
                    |
                    v
       evidence / certification
                    |
                    v
               deployment
                    |
                    v
                   cli
```

This is a reading model, not a statement that every Python import follows one perfectly linear chain.

---

## 4. The shortest useful reading path

If you only have a few hours, read these files in order.

### Step 1 — DatasetConfig: `metadata/config.py`

Start here:

```text
src/fabric_data_framework/metadata/config.py
```

Focus on:

```text
CaptureStrategy
ApplyStrategy
RunMode
ExecutionEngine
SourceConfig
TargetConfig
WatermarkConfig
LoadPolicy
OrchestrationPolicy
DataQualityPolicy
ReconciliationPolicy
ExecutionPolicy
DatasetConfig
RuntimeOverride
EffectiveDatasetConfig
resolve_effective_config(...)
```

After reading it you should be able to answer:

```text
What is the source?
What is the target?
FULL / WATERMARK / CDC / ... ?
REPLACE / UPSERT / SCD1 / SCD2 / ... ?
What key/order/watermark rules exist?
What datasets does this depend on?
Which execution engine is requested?
Is DQ/reconciliation required?
```

Do not move on until the difference between these two fields is completely clear:

```text
capture_strategy
apply_strategy
```

Capture describes **what source facts arrive**. Apply describes **how those facts alter the target**.

---

### Step 2 — Source truth: `capture/`

Next read the source-semantic side.

Start with:

```text
capture/semantic_contracts.py
capture/onboarding.py
capture/full.py
capture/watermark.py
capture/cdc.py
```

Then, only for the source type you care about:

```text
capture/api.py
capture/files.py
capture/bootstrap_watermark.py
capture/bootstrap_cdc.py
```

Key idea:

```text
capture code must not manufacture history the source did not provide
```

For example:

```text
FULL snapshot -> current snapshot facts
WATERMARK      -> bounded changed rows
CDC            -> ordered source change facts
```

The downstream SCD strategy does not change what the source actually delivered.

---

### Step 3 — Physical capability selection: `metadata/capabilities.py`

Read:

```text
metadata/capabilities.py
```

This answers:

```text
Given DatasetConfig semantics, which physical engine is allowed?
Can Fabric Copy perform this capture?
Must Spark perform apply?
Does the requested capability profile overclaim provider behavior?
```

The important design rule is:

```text
native capture does not imply native final-target apply
```

Capture engine and apply engine are validated independently.

---

### Step 4 — Immutable execution plan: `contracts/execution_plan.py`

Read:

```text
contracts/execution_plan.py
```

Focus on:

```text
ExecutionKind
ExecutionRole
ExecutionUnit
ExecutionPlan
compile_execution_plan(...)
```

This is where semantic configuration becomes an immutable physical plan.

Examples:

```text
Spark capture + Spark apply
  -> one Spark Job Definition unit may own
     EXTRACT/STAGE/NORMALIZE/VALIDATE/APPLY/RECONCILE/COMMIT_STATE

Native capture + Spark apply
  -> capture unit
  -> framework_process Spark unit

Native capture + native/non-Spark apply
  -> capture
  -> framework_prepare
  -> apply
  -> framework_finalize
```

The plan has a deterministic `plan_hash`. That hash is later used to prove that a remote child executed the exact plan the parent intended.

---

### Step 5 — Dataset/dependency planning: `orchestration/planner.py`

Read:

```text
orchestration/planner.py
```

Focus on:

```text
DispatchPlan
build_dispatch_plan(...)
blocking_dependencies(...)
ready_dataset_ids(...)
aggregate_pipeline_status(...)
```

The planner does **not** move data.

It decides:

```text
which deployed datasets are selected
which runtime overrides are effective
whether capability validation passes
whether dependencies exist
whether the graph has a cycle
what max concurrency is safe
what failure policy applies
```

It then produces an immutable `DispatchPlan`.

This separation is important:

```text
planner = WHEN/WHAT MAY RUN
backend = HOW/WHERE IT RUNS
```

---

### Step 6 — Parent orchestration loop: `orchestration/dispatcher.py`

Now read:

```text
orchestration/dispatcher.py
```

This is the closest thing to the top-level normal runtime loop.

Focus on:

```text
dispatch_datasets_with_backend(...)
dispatch_datasets(...)
```

The flow is:

```text
create pipeline_run_id
    |
    v
build_dispatch_plan(...)
    |
    v
record Pipeline RUNNING
    |
    v
while datasets remain:
    mark datasets BLOCKED if dependencies failed
    find dependency-ready datasets
    execute one ready wave through backend
    collect DatasetDispatchOutcome
    |
    v
aggregate final Pipeline status
    |
    v
record Pipeline SUCCESS / PARTIAL_SUCCESS / FAILED
```

The dispatcher intentionally uses **fail-at-end** style fault isolation: one dataset failure does not automatically stop unrelated siblings. Failed dependencies block only their dependent datasets.

---

## 5. At this point the code splits into two execution paths

You should now choose one of two branches.

### Path A — understand semantics cheaply: in-process backend

Read first:

```text
execution/backends/in_process.py
```

Important functions:

```text
execute_one_in_process(...)
execute_ready_wave(...)
```

For each dataset it:

```text
creates dataset_run_id
builds DatasetDispatchRequest
builds an ExecutionPlan
resolves a DatasetExecutor
calls the executor
requires a terminal DatasetDispatchOutcome
converts executor exceptions into a FAILED dataset audit/outcome
```

This path is the easiest way to understand the framework contracts without Fabric REST noise.

The important abstraction is:

```text
DatasetExecutor(request) -> DatasetDispatchOutcome
```

The framework deliberately does not force every domain/source/target into one universal physical function.

---

### Path B — understand real Fabric orchestration: Fabric Pipeline backend

Read:

```text
execution/backends/fabric_pipeline.py
adapters/fabric/pipeline.py
adapters/fabric/rest.py
execution/pipeline_child.py
```

The parent-side flow is:

```text
FabricPipelineBackend.execute_one(...)
    |
    v
create dataset_run_id
    |
    v
compile_execution_plan(...)
    |
    v
build FabricPipelineInvocation
    |
    v
FabricRestPipelineTransport.invoke(...)
    |
    v
Fabric REST starts Data Pipeline job
    |
    v
poll provider job to terminal status
```

But `Completed` is not the end.

After Fabric reports `Completed`, the parent does:

```text
outcome_reader(dataset_run_id)
```

The exact durable framework outcome must already exist. If it does not exist, the parent records:

```text
FABRIC_PIPELINE_RESULT_MISSING
```

and the dataset fails.

That boundary is one of the most important things in the repository.

---

## 6. Understand the seven-parameter remote child contract

Read:

```text
execution/pipeline_child.py
```

A Fabric Pipeline child receives exactly:

```text
framework_pipeline_run_id
framework_dataset_run_id
dataset_id
run_mode
attempt
effective_config_hash
execution_plan_hash
```

No silent aliases are accepted.

The remote child first validates:

```text
requested dataset exists
current effective config hash == parent's effective_config_hash
newly compiled execution plan hash == parent's execution_plan_hash
```

Only then may the physical executor run.

Generic flow:

```text
pipeline_child_request_from_parameters(...)
    |
    v
validate_pipeline_child_request(...)
    |
    v
physical executor(request, DatasetConfig, repository)
    |
    v
FabricPipelineChildResult
    |
    v
record exact DatasetRunAudit
    |
    v
read back exact DatasetDispatchOutcome
```

The child contract owns the **durable terminal framework outcome**.

The physical executor owns the environment/domain-specific data mutation.

---

## 7. Where capture, Bronze, DQ and apply actually fit

A common mistake is looking for a single file that performs:

```text
source -> Bronze -> Silver -> checkpoint
```

There is intentionally no universal monolithic implementation.

The framework provides reusable semantic primitives and contracts. A real implementation/domain executor composes the primitives appropriate for that dataset and environment.

Conceptually, a physical executor does:

```text
1. read committed framework progress/checkpoint
2. freeze/derive the source capture window
3. execute source/provider capture
4. retain CaptureReceipt / source evidence
5. stage/normalize source facts
6. run schema and DQ checks
7. quarantine if policy allows
8. plan/apply target mutation
9. reconcile candidate/target state
10. prove target commit where required
11. advance framework semantic checkpoint only after proof
12. return FabricPipelineChildResult / DatasetDispatchOutcome
```

The corresponding owners are:

```text
capture/       steps 1-4
data_plane/    staging/Bronze helper contracts
quality/       steps 5-6 and reconciliation gates
apply/         target state/history transition
recovery/      idempotency and ambiguous commit handling
control_plane/ durable framework state/evidence/checkpoints
```

For a concrete, bounded implementation of this composition, read:

```text
certification/pipeline_child.py
```

It is **not** the general production implementation. It is a framework-owned certification executor with fixed certification tables. It is useful because it demonstrates the same generic contracts end-to-end without a customer/domain codebase.

---

## 8. Concrete example: FULL snapshot + REPLACE

A useful first trace is the certification dataset:

```text
cert.full_replace
```

Read this code path:

```text
metadata/config.py
    CaptureStrategy.FULL
    ApplyStrategy.REPLACE
        |
        v
contracts/execution_plan.py
        |
        v
orchestration/planner.py
        |
        v
orchestration/dispatcher.py
        |
        v
execution/backends/fabric_pipeline.py
        |
        v
execution/pipeline_child.py
        |
        v
certification/pipeline_child.py::_execute_replace(...)
        |
        +--> capture/full.py::FullSnapshotEvidence
        |
        +--> data_plane/staging.py::stage_rows(...)
        |
        +--> apply/replace.py::plan_replace(...)
        |
        +--> quality/full_refresh.py::reconcile_full_replace(...)
        |
        v
publish target rows only after reconciliation PASS
        |
        v
return FabricPipelineChildResult(SUCCEEDED)
        |
        v
execution/pipeline_child.py persists DatasetRunAudit
        |
        v
parent FabricPipelineBackend reads durable outcome
```

The important safety order is:

```text
capture complete
-> plan candidate replacement
-> reconcile
-> publish
-> commit progress/outcome
```

Not:

```text
delete target first
-> hope validation passes later
```

---

## 9. Concrete example: WATERMARK + SCD1

Trace:

```text
DatasetConfig.load.capture_strategy = WATERMARK
DatasetConfig.load.apply_strategy   = SCD1
```

Important files:

```text
metadata/config.py
capture/watermark.py
capture/bootstrap_watermark.py
apply/scd1.py
quality/reconciliation.py
control_plane/repository.py
```

The conceptual flow is:

```text
committed watermark W0
    |
    v
freeze/select rows after W0
(+ tie breaker / overlap rules)
    |
    v
normalize ordering
    |
    v
apply SCD1 using merge key + ordering columns
    |
    v
reconcile target candidate
    |
    v
publish target mutation
    |
    v
commit new semantic watermark W1
```

The crucial rule is:

```text
source query success does not advance W1
provider completion does not advance W1
apply alone does not advance W1
```

The checkpoint advances only after the framework has enough proof that the corresponding semantic work is safe.

For a concrete working example, inspect the certification SCD1 branch in:

```text
certification/pipeline_child.py::_execute_scd1(...)
```

---

## 10. Concrete example: WATERMARK/CDC + SCD2

Read:

```text
apply/scd2.py
apply/cdc_scd2.py
apply/cdc.py
capture/cdc.py
adapters/cdc/
quality/reconciliation.py
```

Keep this rule in mind:

```text
SCD2 is a target representation, not a source capture strategy
```

A source with ordered CDC may support high-fidelity SCD2 history.
A periodic FULL snapshot can support only snapshot-grain inferred history unless stronger source evidence exists.

The SCD2 apply layer must never fabricate intermediate states that were not captured.

A good concrete certification trace is:

```text
certification/pipeline_child.py::_execute_scd2(...)
```

It demonstrates:

```text
read prior current/history state
-> read bounded ordered source rows
-> apply SCD2
-> reconcile one-current-row invariant
-> publish history/current representation
-> advance progress only after reconciliation
```

---

## 11. Understand the Control Plane before reading recovery

Read:

```text
control_plane/repository.py
```

Start with the `ControlPlaneRepository` protocol.

It tells you the minimum durable framework state that runtime code expects:

```text
deploy/get/list DatasetConfig
get/commit watermark
record PipelineRunAudit
record DatasetRunAudit
get DatasetDispatchOutcome
record CaptureReceipt
record StepRunAudit
record ReconciliationResult
record QuarantineBatch
record attempt lineage
record reprocess request
```

Then read the in-memory implementation in the same file.

Only after the protocol makes sense should you read the production relational implementation, especially:

```text
control_plane/sqlalchemy_repository.py
control_plane/schema.py
```

The recommended mental split is:

```text
Control Plane = small mutable operational truth
Data Plane    = large business rows / Bronze / Silver / Gold
```

Do not treat the Control Plane as a data lake.

---

## 12. Retry, replay and unknown commit

After the normal happy path is clear, read recovery.

Recommended order:

```text
contracts/target_operation.py
control_plane/target_operation_journal.py
recovery/target_probe.py
recovery/fabric_warehouse.py
recovery/
```

The key problem is an ambiguous target commit:

```text
client sends mutation
    |
    v
target commits
    |
    X  acknowledgement is lost
    |
    v
client sees exception
```

Blind retry can duplicate APPEND rows or corrupt history.

The framework distinguishes:

```text
COMMITTED
NOT_COMMITTED
UNRESOLVED
```

Rules:

```text
COMMITTED
  -> converge to success; do not mutate again

NOT_COMMITTED
  -> bounded retry may proceed

UNRESOLVED
  -> stop; never blind retry
```

Then read `docs/OPERATIONS.md` to connect these contracts to operator procedures such as retry, replay, backfill and rebuild.

---

## 13. How a real implementation/domain repository fits

`fabric-data-framework` does not own project-specific mappings, table names, business DQ or environment bindings.

A real project such as `fabric-health` owns those definitions and consumes the released framework wheel.

The relationship is:

```text
implementation repo
    |
    +--> DatasetConfig JSON/YAML/materialized config
    +--> source-to-target mapping
    +--> execution groups/dependencies
    +--> business DQ/reconciliation
    +--> environment bindings
    +--> bounded custom adapters/extensions if needed
    |
    v
fabric-data-framework wheel
```

For that lifecycle read:

```text
docs/IMPLEMENTATION_PROJECT.md
deployment/project.py
deployment/delivery.py
capture/onboarding.py
metadata/capabilities.py
```

A useful distinction is:

```text
framework repo       owns reusable HOW and safety semantics
implementation repo  owns project WHAT/WHERE
```

---

## 14. How the CLI fits

Read CLI code last.

Start with:

```text
cli/main.py
```

It is only the composition router.

Then open the specific command family:

```text
cli/project.py
cli/certification.py
cli/release.py
cli/business_path.py
cli/approved.py
cli/base.py
```

The rule is:

```text
cli -> reusable framework modules
reusable framework modules -X-> cli
```

If you find important business/runtime semantics implemented only in `cli/`, that is usually a design smell.

`pyproject.toml` binds the console script:

```text
fabric-framework = fabric_data_framework.cli:main
```

---

## 15. Framework certification flow

Certification is easier to understand after the runtime path.

Read:

```text
certification/installed.py
certification/semantic.py
certification/bounded.py
certification/simple.py
certification/unified.py
certification/fabric_assets.py
certification/fabric_job.py
```

Current high-level flow is:

```text
framework source
    |
    v
build exact wheel once
    |
    v
clean installed-wheel acceptance
    |
    v
select exact candidate wheel + CANDIDATE.json
    |
    v
bootstrap dedicated DEV Fabric certification assets
    |
    +--> Environment containing exact candidate wheel
    +--> Spark Job Definition
    +--> Copy Job
    +--> Data Pipeline
    |
    v
read back exact item definitions
    |
    v
build framework-owned integration inputs
    |
    v
certify_installed(...)
    |
    +--> attest active installed package bytes
    +--> semantic acceptance
    +--> bounded Fabric checks
    +--> environment-dependent integration checks
    +--> representative business-path checks
    |
    v
retained evidence
```

The primary public API is:

```python
from fabric_data_framework.certification import certify_installed
```

The exact candidate identity is the framework wheel SHA256. Environment-dependent certification also binds the exact framework-owned integration-input hash.

For operator steps read `docs/TESTING_AND_CERTIFICATION.md` rather than reconstructing the lifecycle from source.

---

## 16. Evidence: read only after runtime and certification

The `evidence/` folder is large because it proves many different environment boundaries.

Do not read every file.

Use this order:

```text
1. evidence/integration_evidence.py
2. evidence/integration_checks.py
3. evidence/integration_runner.py
4. evidence/integration_evidence_merge.py
5. the one approved_*_runner.py for the boundary you care about
```

Examples:

```text
Pipeline        -> approved_pipeline_runner.py
Copy / Spark    -> approved_capture_runner.py
Control Plane   -> approved_control_plane_runner.py
Warehouse       -> approved_warehouse_runner.py
ambiguous commit-> approved_warehouse_fault_runner.py
business path   -> approved_business_path_runner.py
```

The evidence layer must project facts from existing runtime/provider contracts. It must not invent a second definition of semantic success.

---

## 17. Release flow

Read release code last because release is an aggregation of everything before it.

Start with:

```text
docs/RELEASE.md
release/<version>/readiness-spec.json
deployment/candidate_artifact.py
evidence/release_readiness.py
evidence/candidate_certification.py
```

Then inspect workflows:

```text
.github/workflows/ci.yml
.github/workflows/wheel-certification.yml
.github/workflows/candidate-integration-inputs.yml
.github/workflows/candidate-integration-evidence.yml
.github/workflows/candidate-business-path-evidence.yml
.github/workflows/candidate-release-proofs.yml
.github/workflows/candidate-certification.yml
.github/workflows/release.yml
```

Conceptual chain:

```text
source + tests
    |
    v
exact wheel
    |
    v
installed-wheel acceptance
    |
    v
real Fabric/integration evidence
    |
    v
business-path evidence
    |
    v
release-readiness aggregation
    |
    v
explicit release authorization
    |
    v
promote the SAME wheel bytes
```

Do not mentally replace that with:

```text
version string -> build something new -> release
```

The exact bytes are part of the contract.

---

## 18. One complete normal-runtime call graph

Use this as the main map while reading code:

```text
implementation caller / orchestrator
    |
    v
orchestration.dispatcher.dispatch_datasets_with_backend(...)
    |
    +--> orchestration.planner.build_dispatch_plan(...)
    |       |
    |       +--> repository.list_datasets()
    |       +--> metadata.resolve_effective_config(...)
    |       +--> metadata.capabilities.validate(...)
    |       +--> dependency/cycle/concurrency validation
    |
    +--> repository.record_pipeline_run(RUNNING)
    |
    +--> planner.ready_dataset_ids(...)
    |
    v
ReadyWaveBackend.execute_ready_wave(...)
    |
    +---------------- IN_PROCESS ----------------+
    |                                             |
    | execution/backends/in_process.py            |
    |   -> DatasetDispatchRequest                  |
    |   -> build ExecutionPlan                     |
    |   -> DatasetExecutor                         |
    |   -> DatasetDispatchOutcome                  |
    |                                             |
    +----------------- FABRIC ---------------------+
                                                  |
                    execution/backends/fabric_pipeline.py
                        |
                        +--> compile_execution_plan(...)
                        +--> FabricPipelineInvocation
                        +--> adapters/fabric/pipeline.py
                        +--> adapters/fabric/rest.py
                        |
                        v
                    real Fabric Data Pipeline
                        |
                        v
                    remote child / SJD
                        |
                        v
                    execution/pipeline_child.py
                        |
                        +--> validate config hash
                        +--> validate plan hash
                        +--> domain physical executor
                        |      |
                        |      +--> capture/
                        |      +--> data_plane/
                        |      +--> quality/
                        |      +--> apply/
                        |      +--> recovery/
                        |
                        +--> record DatasetRunAudit
                        +--> read exact outcome
                        |
                        v
                    Fabric provider completes
                        |
                        v
                    parent outcome_reader(dataset_run_id)
                        |
                        v
                    exact DatasetDispatchOutcome
    |
    v
orchestration.dispatcher aggregates wave outcomes
    |
    v
planner.aggregate_pipeline_status(...)
    |
    v
repository.record_pipeline_run(final status)
```

If you lose track while browsing, return to this diagram and ask: **which arrow am I currently reading?**

---

## 19. One complete data-semantic flow

The runtime graph above explains orchestration. This graph explains the data itself:

```text
SOURCE
  |
  |  source semantics
  v
CAPTURE
  FULL / WATERMARK / CDC / MIRROR / STREAM / SNAPSHOT
  |
  |  CaptureReceipt / source window / cursor evidence
  v
BRONZE / STAGING
  source-faithful rows/events/snapshots
  |
  v
NORMALIZE + SCHEMA + DQ
  |                 |
  |                 +--> quarantine data + metadata if allowed
  v
APPLY
  APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF
  |
  v
RECONCILIATION
  |
  +--> FAIL -> no unsafe semantic checkpoint advance
  |
  v
TARGET COMMIT PROOF
  |
  v
FRAMEWORK CHECKPOINT / DURABLE OUTCOME
  |
  v
DOWNSTREAM DEPENDENCIES MAY RUN
```

This is why capture and apply are separate folders.

Examples:

```text
FULL       + REPLACE
WATERMARK  + SCD1
WATERMARK  + SCD2
CDC        + SCD2
CDC        + UPSERT
EVENTS     + APPEND
SNAPSHOTS  + SNAPSHOT_DIFF
```

Read `docs/DATA_PATTERNS.md` when deciding which combination is semantically valid.

---

## 20. Files you should deliberately skip on the first pass

Do not try to understand all of these immediately:

```text
all approved_* evidence runners
all CLI subcommands
all release merge/proof files
all provider-specific CDC adapters
all certification workflow YAML
all recovery fault-injection helpers
all tests
```

They are important, but they are downstream of the core mental model.

Your first pass is successful when you can explain, without opening the repo:

```text
DatasetConfig
-> effective config
-> capability validation
-> ExecutionPlan
-> dependency-ready wave
-> backend
-> child executor
-> capture/quality/apply/reconcile
-> durable dataset outcome
-> parent validation
-> final Pipeline status
```

Only then widen your reading.

---

## 21. How to read tests without drowning

Tests are best used as executable examples after you know the owner module.

Pattern:

```text
read one production module
-> search tests for that module/class/function
-> read 2-5 focused tests
-> return to production code
```

Useful starting tests include:

```text
tests/test_orchestration_dispatcher.py
tests/test_execution_plan.py
tests/test_fabric_pipeline_backend.py
tests/test_pipeline_child.py
tests/test_certification_pipeline_child.py
```

If a filename differs slightly, search by the public function/class name rather than browsing the whole test directory.

Certification tests are particularly useful because `certification/pipeline_child.py` composes FULL/REPLACE, SCD1, SCD2, retry and reconciliation fail-closed behavior in one bounded executor.

---

## 22. A practical three-session reading plan

### Session 1 — semantics and planning

Read only:

```text
docs/ARCHITECTURE.md
docs/DATA_PATTERNS.md
metadata/config.py
capture/semantic_contracts.py
metadata/capabilities.py
contracts/execution_plan.py
```

Goal: explain what a dataset says it needs and how that becomes a physical plan.

### Session 2 — runtime

Read:

```text
orchestration/planner.py
orchestration/dispatcher.py
execution/backends/in_process.py
execution/backends/fabric_pipeline.py
execution/pipeline_child.py
control_plane/repository.py
```

Goal: explain how one Pipeline run schedules datasets and proves each remote result.

### Session 3 — data mutation, recovery and delivery

Read only the pattern you care about, for example:

```text
capture/watermark.py
apply/scd2.py
quality/reconciliation.py
recovery/
certification/pipeline_child.py
```

Then finish with:

```text
docs/IMPLEMENTATION_PROJECT.md
docs/TESTING_AND_CERTIFICATION.md
docs/RELEASE.md
```

Goal: connect runtime semantics to a real project, Fabric certification and exact-byte release.

---

## 23. Where to start when changing something

| Change you want | First file | Then follow |
|---|---|---|
| Add/change DatasetConfig field | `metadata/config.py` | onboarding -> capabilities -> execution plan -> docs/tests |
| Add source capture semantic | `capture/` | contracts -> capabilities -> adapter -> tests |
| Add/modify SCD behavior | `apply/` | quality reconciliation -> executor -> tests |
| Change dependency scheduling | `orchestration/planner.py` | dispatcher -> backend contract -> tests |
| Add execution engine | `metadata/capabilities.py` | `contracts/execution_plan.py` -> adapter/backend |
| Change Fabric Pipeline invocation | `execution/backends/fabric_pipeline.py` | `adapters/fabric/pipeline.py` -> `rest.py` -> child contract |
| Change remote child contract | `execution/pipeline_child.py` | parent backend -> reference contract -> certification child -> tests |
| Change checkpoint/audit semantics | `control_plane/repository.py` | SQL repository -> orchestration/recovery -> tests |
| Fix unknown-commit behavior | `contracts/target_operation.py` | `recovery/` -> Control Plane journal -> operations docs |
| Change certification assets | `certification/fabric_assets.py` | `fabric_job.py` -> certification docs -> real Fabric evidence |
| Change release criteria | `release/<version>/readiness-spec.json` | readiness evidence -> candidate aggregation -> release workflow |
| Add CLI command | reusable owner module first | `cli/` only as final presentation layer |

---

## 24. Debugging: trace identities, not filenames

When debugging a real run, follow identities through the system:

```text
pipeline_run_id
    |
    +--> dataset_run_id
            |
            +--> effective_config_hash
            +--> execution_plan_hash
            +--> provider job_instance_id / root_activity_id
            +--> CaptureReceipt
            +--> reconciliation result
            +--> target operation evidence
            +--> DatasetRunAudit
```

This is usually more useful than asking “which Python file failed?” because a Fabric/provider action can complete while the semantic run still fails later at evidence/reconciliation/state commit.

Useful places to inspect are:

```text
Control Plane pipeline_run
dataset_run
step_run
capture receipt
reconciliation
quarantine metadata
target operation journal
provider native run identity
```

---

## 25. The invariants that make the whole repository easier to understand

Memorize these. Most design decisions follow from them.

### Invariant 1 — capture and apply are orthogonal

```text
WATERMARK is not SCD1
CDC is not SCD2
SCD2 is not a source type
```

### Invariant 2 — source fidelity is a ceiling

```text
truthful downstream history <= captured source fidelity
```

### Invariant 3 — plan before provider execution

```text
DatasetConfig -> effective config -> capability validation -> immutable ExecutionPlan
```

### Invariant 4 — provider status is evidence, not semantic truth

```text
Fabric Completed != framework success
```

### Invariant 5 — reconciliation may block state advance

```text
mutation candidate -> reconciliation PASS -> publish/commit state
```

### Invariant 6 — unknown commit is fail-closed

```text
UNRESOLVED -> no blind retry
```

### Invariant 7 — runtime state is environment-local

Promote code/config/definitions between DEV/UAT/PROD, not operational checkpoints and run state.

### Invariant 8 — CLI and evidence are leaves

They consume reusable semantics. They must not become a second semantic implementation.

### Invariant 9 — certification proves exact wheel bytes

Source tests, installed-wheel acceptance, real Fabric certification and release authorization are separate gates.

---

## 26. Final recommended reading order

If you want one numbered list to follow literally, use this:

```text
01 docs/ARCHITECTURE.md
02 docs/DATA_PATTERNS.md
03 src/fabric_data_framework/README.md
04 metadata/config.py
05 capture/semantic_contracts.py
06 capture/onboarding.py
07 metadata/capabilities.py
08 contracts/execution_plan.py
09 orchestration/planner.py
10 orchestration/dispatcher.py
11 execution/backends/in_process.py
12 execution/backends/fabric_pipeline.py
13 adapters/fabric/pipeline.py
14 adapters/fabric/rest.py
15 execution/pipeline_child.py
16 control_plane/repository.py
17 the capture module for your chosen pattern
18 the apply module for your chosen pattern
19 quality/reconciliation.py
20 recovery/ only after the happy path is clear
21 certification/pipeline_child.py as a concrete end-to-end example
22 docs/IMPLEMENTATION_PROJECT.md
23 docs/OPERATIONS.md
24 docs/TESTING_AND_CERTIFICATION.md
25 docs/RELEASE.md
26 evidence/ only for the exact proof boundary you need
27 cli/ last
```

You do not need to read every file in the repository to understand the framework.

If you can trace one dataset through items 4-21, you understand the core runtime architecture. Everything after that is deployment, proof, operations or presentation around the same core contracts.
