# Fabric Execution Model — fabric-data-framework

Status: Canonical design
Last updated: 2026-08-28

## 1. Purpose

This document defines how reusable framework semantics map onto Microsoft Fabric runtime items.

The key design rule is:

> Fabric items orchestrate and host execution; the Python framework owns reusable correctness semantics.

The framework must avoid both extremes:

- hundreds of table-specific visual pipelines that duplicate logic; and
- one opaque giant notebook that hides every operational boundary inside notebook code.

## 2. Current Microsoft Fabric capability baseline

Verified against Microsoft Learn on 2026-08-28:

- Fabric Data Factory Pipelines provide data-movement, transformation and control-flow activities.
- Pipelines support parameterization, `Lookup`, `ForEach`, `Until`, `If`, `Switch`, `Invoke pipeline`, Copy, Notebook, Spark Job Definition, SQL and other activities.
- The newer Invoke Pipeline activity supports modular child-pipeline composition and cross-workspace invocation subject to identity/connection rules.
- Notebook activities support parameters and session tags; notebook runs can emit an exit value.
- Spark Job Definition is a first-class Fabric item for submitting batch/streaming Spark applications and can be run through a Data Factory pipeline activity.
- Fabric Environment is shared by Notebook and Spark Job Definition and controls Spark runtime, compute and libraries.
- Environment Full library publish resolves dependencies and creates a stable library snapshot and is the preferred mode for production/pipeline workloads; Quick mode is primarily an iteration convenience.
- Variable Library can supply environment/lifecycle values to Fabric items, but semantic dataset behavior remains versioned source configuration in the framework/domain release model.
- Fabric pipeline limits and activity behavior are service details and must be re-verified before hard-coding concurrency assumptions.

## 3. Runtime layers

```text
Trigger / schedule / operator request
        |
        v
Fabric Data Factory Pipeline
  orchestration + activity visibility
        |
        +--> Copy Activity / SQL Activity when appropriate
        |
        +--> Spark Job Definition activity   [preferred generic headless Spark job]
        |
        +--> Notebook activity               [thin interactive/smoke/exception path]
        |
        v
released framework wheel + released domain wheel
        |
        v
EffectiveDatasetConfig / ExecutionPlan
        |
        v
capture -> normalize -> quality -> apply -> reconcile -> state commit
        |
        v
Lakehouse / Warehouse / control-plane store
```

The pipeline canvas is not the source of truth for capture/apply correctness. The released package and metadata contract are.

## 4. Notebook versus Spark Job Definition

### Spark Job Definition — preferred production application entrypoint

Use a Spark Job Definition when the workload is a repeatable non-interactive Spark application:

- scheduled or pipeline-triggered batch execution;
- framework/domain wheels installed through a published Environment;
- command-line/job arguments identify dataset/run/environment request;
- no dependency on notebook cells as the program structure;
- code is unit/integration tested outside the Fabric UI;
- execution can be promoted as an application item.

A generic SJD main file should remain thin. Conceptually:

```python
from fabric_data_framework.fabric.entrypoints import run_dataset_job

run_dataset_job(...)
```

The main file is not where FULL/WATERMARK/CDC algorithms live.

### Notebook — supported thin runtime surface

Notebooks remain valuable for:

- interactive development;
- diagnostics and controlled operational investigation;
- smoke tests;
- proof-of-concept integration;
- ad hoc bounded backfill/replay when policy permits;
- cases where Fabric notebook-specific capabilities materially improve the workload.

A production Notebook activity can still be valid. The anti-pattern is not `one notebook`; the anti-pattern is a notebook that owns every reusable algorithm, embeds physical IDs/secrets, cannot be tested independently, and is the only place to understand state/recovery behavior.

## 5. Does a one-Notebook pipeline look unprofessional?

No, not by itself.

A child pipeline such as:

```text
pl_dataset_execute
    |
    +-- Spark Job Definition / Notebook: execute_dataset(dataset_id, run_mode, pipeline_run_id)
```

can be perfectly professional if:

- the activity is a thin adapter;
- parameters are explicit;
- execution and retry policy are explicit;
- durable audit/state exists outside notebook logs;
- framework/domain code is released and tested as packages;
- the parent orchestration exposes dataset-level fan-out/failure state;
- the execution entrypoint is not table-specific code duplication.

What would be weak for this reference platform is:

```text
pl_full_refresh
    |
    +-- notebook_full_refresh
          contains extraction + transformations + DQ + truncate + insert
          + state update + logging + retries + hard-coded resources
```

That is an opaque script wrapped by a pipeline, not a reusable platform.

## 6. Recommended Fabric pipeline hierarchy

The target is a small number of reusable orchestration items, not one pipeline per table.

### 6.1 Domain batch orchestrator

```text
pl_domain_batch

Trigger / parameters
      |
      v
Initialize pipeline_run / request context
      |
      v
Resolve eligible execution groups / datasets
      |
      v
Bounded fan-out
      |
      +--> Invoke pl_dataset_execute(dataset=A)
      +--> Invoke pl_dataset_execute(dataset=B)
      +--> Invoke pl_dataset_execute(dataset=C)
      |
      v
Finalize aggregate outcome
```

The parent owns schedule/operator entry, coarse control flow and Fabric-visible orchestration.

### 6.2 Dataset execution child pipeline

```text
pl_dataset_execute

Parameters:
  pipeline_run_id
  dataset_id
  run_mode
  reprocess_request_id?

      |
      v
Select physical execution adapter
      |
      +--> Spark Job Definition
      +--> Notebook
      +--> Copy + Spark/SQL publish plan
      +--> SQL activity
      |
      v
Return/correlate dataset outcome
```

The child pipeline can legitimately contain only one SJD/Notebook activity for datasets whose complete execution belongs in one Spark application. The framework still records meaningful step-level audit inside the durable control plane.

### 6.3 Recovery pipeline

```text
pl_reprocess

Validate request
   -> resolve dataset/range/mode
   -> invoke normal dataset execution contract
   -> retain original/replay lineage
```

Recovery must reuse normal strategy implementations; do not create a separate copy of business logic for backfill/replay.

## 7. Full-refresh template

The semantic template is `FULL -> REPLACE`, not `full_refresh_notebook`.

Correctness stages:

```text
freeze source intent
   -> extract complete candidate
   -> isolated stage
   -> schema/DQ/completeness guards
   -> reconciliation
   -> atomic/safe publication
   -> committed run/state
```

How those stages map to Fabric activities depends on physical capability.

### Plan A — Fabric Copy for movement + Spark/SQL for publication

Use when supported source/target connectors and security constraints make Data Factory Copy the strongest movement mechanism.

```text
pl_dataset_execute
   |
   +-- Copy Activity: source -> isolated Bronze/stage
   |
   +-- SJD/Notebook: validate + normalize + reconcile candidate
   |
   +-- SJD/SQL: publish REPLACE atomically/safely
```

This is useful when ingestion volume is large and custom Spark extraction adds no value.

### Plan B — one Spark application

Use when consistent source extraction, transformation, connector behavior or target transaction semantics are best owned by Spark/framework code.

```text
pl_dataset_execute
   |
   +-- SJD execute_dataset(FULL, REPLACE)
```

This is not less professional. The Spark job still emits durable step audit for `EXTRACT`, `STAGE`, `VALIDATE`, `RECONCILE`, `PUBLISH`, `STATE_COMMIT`.

### Plan C — database-native publication

Use when the target database/warehouse is the correct transaction owner.

```text
Copy/Spark stage
   -> SQL Script / Stored Procedure publish
   -> framework final reconciliation/state commit
```

The framework selects/validates plans through adapter capability contracts; it should not force Spark where Fabric/database-native execution is better.

## 8. Semantic template versus physical execution plan

Keep two concepts separate.

### Semantic template

Describes correctness guarantees:

```text
capture=FULL
apply=REPLACE
complete_snapshot_required=true
empty_source_guard=...
reconciliation=...
delete_semantics=...
```

### Physical execution plan

Describes where steps execute:

```text
extract=FABRIC_COPY
validate=SPARK_JOB_DEFINITION
publish=SQL_SCRIPT
```

or:

```text
execute=SPARK_JOB_DEFINITION
```

This separation lets the same production guarantee run on different Fabric execution mechanisms without multiplying strategies such as `sqlserver_full_copy_pipeline`, `oracle_full_notebook`, and `postgres_full_spark`.

## 9. ExecutionPlan contract

The framework should add an explicit provider-neutral execution-plan model.

Conceptually:

```text
ExecutionPlan
  dataset_id
  run_mode
  semantic_profile
  source_boundary
  steps[]
    step_id
    semantic_role
    execution_kind
    retry_policy
    timeout
    state_gate
    reconciliation_gate
    idempotency_key
  required_bindings[]
```

Semantic roles include:

- `PREPARE`
- `EXTRACT`
- `STAGE`
- `VALIDATE`
- `NORMALIZE`
- `APPLY`
- `RECONCILE`
- `PUBLISH`
- `COMMIT_STATE`
- `FINALIZE`

Not every role becomes a Fabric activity. A single SJD may execute several roles while still persisting each step in `step_run`.

## 10. Dispatcher evolution

The current in-process dispatcher proves selection, dependency, bounded concurrency and failure isolation. It should evolve into two layers:

```text
orchestration planner
  pure/provider-neutral
  selects datasets
  validates dependency graph
  computes ready waves / aggregate policy

execution backend
  local/in-process reference
  Fabric Pipeline adapter
```

Do not make `ThreadPoolExecutor` the definition of enterprise orchestration. It is one reference execution backend.

The Fabric adapter may use execution groups/stages and child pipeline invocation so dataset runs remain visible in Fabric monitoring. Arbitrary DAG behavior should be added only where it improves real operational requirements.

## 11. Fabric-visible versus framework-visible observability

Both are required.

Fabric should show:

- parent pipeline run;
- child dataset invocation/activity;
- activity duration/status;
- SJD/Notebook/Copy execution identity;
- coarse dependency/failure routing.

Framework control plane should show:

- immutable effective config;
- source boundary;
- strategy/plan;
- fine-grained step attempts;
- row accounting;
- quarantine/reconciliation;
- watermark/state before/after;
- error classification/retryability;
- original/replay lineage;
- framework/domain/config provenance.

The operator should not need to choose between Fabric monitoring and framework state; correlation IDs link them.

## 12. Fabric Environment contract

For production Spark execution:

```text
Environment
  Spark runtime
  compute settings / approved pool
  fabric-data-framework exact wheel
  domain solution exact wheel
  other pinned libraries
```

Development may use faster iteration modes, but release/pipeline execution should use a published stable environment snapshot.

Environment identity/version must be captured in deployment/run evidence where available.

## 13. Variable/configuration contract

Use three layers:

1. source-controlled semantic dataset metadata;
2. deployed immutable semantic snapshot/hash;
3. environment-specific physical binding and operational overrides.

Fabric Variable Library may participate in layer 3 for non-secret environment values where appropriate. It must not become an alternate uncontrolled place to change merge keys, SCD policy or schema contracts.

Secrets remain connection/identity/enterprise-secret concerns.

## 14. Copy activity selection rule

Prefer Fabric Copy/Copy Job when the primary task is supported data movement and it can satisfy the required source boundary/replay contract.

Prefer Spark when the load requires one or more of:

- complex transformation/normalization;
- custom source consistency logic;
- application-level dedupe/order semantics;
- sophisticated schema/DQ rules;
- target mutation semantics not cleanly expressed by Copy;
- combined correctness boundary that would become weaker if split across activities.

Do not use Spark merely because the framework is written in Python.

## 15. High concurrency/session reuse

Fabric supports high-concurrency session sharing for pipeline notebooks under matching conditions and session tags. This can reduce startup overhead, but it is a performance optimization, not a correctness primitive.

Before enabling it for a workload, verify:

- workload/library/default-lakehouse compatibility;
- memory/CPU isolation risk;
- logs remain attributable to individual notebooks;
- concurrency does not defeat source/capacity throttles;
- failure/cancellation semantics remain acceptable.

Spark Job Definition and custom/live pool decisions should be benchmarked against the real estate rather than assumed.

## 16. Naming target

Representative domain Fabric items:

```text
pl_<domain>_batch
pl_<domain>_reprocess
pl_framework_dataset_execute

sjd_framework_dataset_job
nb_framework_smoke
nb_framework_diagnostics

env_<domain>_runtime
vl_<domain>_bindings
```

Actual naming may follow enterprise conventions; the important part is role clarity and no table-specific pipeline explosion.

## 17. Anti-patterns

Avoid:

- one bespoke pipeline per table;
- one bespoke notebook per table when only metadata differs;
- encoding merge/SCD/delete semantics in pipeline expressions;
- putting credentials or workspace/lakehouse GUIDs in notebooks;
- using notebook cells as the only audit/state system;
- creating visual activities solely so a pipeline looks more complex;
- using a single opaque notebook as parent orchestration for tens of datasets when Fabric-visible child execution is operationally valuable;
- using `notebook.runMultiple` as a substitute for the platform orchestration model without a deliberate reason;
- duplicating retry/reconciliation logic between Pipeline and Python package;
- silently falling back from a failed execution adapter to a semantically weaker path.

## 18. First implementation milestones

1. Introduce provider-neutral `ExecutionPlan` and execution-step contracts.
2. Refactor current dispatcher into planner + execution backend boundary.
3. Implement production-grade `FULL -> REPLACE` executor and tests.
4. Implement `SNAPSHOT -> SNAPSHOT_DIFF` executor and tests.
5. Add retry/backfill/replay attempt model.
6. Add Fabric adapter contracts for Pipeline, SJD, Notebook, Copy, Environment and run-ID correlation without requiring a real tenant.
7. Add domain-owned Fabric item definitions only after the generic adapter contract is stable.
8. Execute a real DEV smoke against an approved Fabric estate and record what is actually supported versus only modeled.

## 19. Release policy

Do not publish `v0.4.0` solely because the version string exists on `main`.

The next release should represent a meaningful production runtime milestone with the execution abstraction, broader strategy coverage and recovery/operability contracts described in `PRODUCTION_REQUIREMENTS.md`.