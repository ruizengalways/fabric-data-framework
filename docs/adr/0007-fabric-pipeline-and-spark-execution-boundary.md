# ADR 0007 — Fabric Pipeline and Spark execution boundary

Status: Accepted
Date: 2026-08-28

## Context

The framework is evolving from pure Python/runtime-contract proof into a production Microsoft Fabric data-engineering platform.

A recurring design question is whether a reusable Fabric pipeline should contain many visible activities or simply invoke one generic Notebook. A one-Notebook pipeline can appear too simple, while a large visual pipeline can appear more sophisticated without actually improving correctness.

Fabric currently supports Pipeline control flow plus Copy, Notebook, Spark Job Definition, SQL and Invoke Pipeline activities. Spark Job Definition is explicitly designed to run packaged batch/streaming Spark applications, while Notebook remains an interactive code item that can also be orchestrated by pipelines. Fabric Environments are shared by Notebook and Spark Job Definition and can provide published stable library/runtime configuration.

The framework also needs to remain testable outside Fabric and must not duplicate FULL/WATERMARK/CDC/SCD/recovery logic in Pipeline expressions or notebook cells.

## Decision

### 1. Pipeline is the Fabric orchestration adapter

Fabric Data Factory Pipeline owns:

- schedule/trigger/operator entry;
- parameters and environment/run correlation;
- coarse control flow;
- dataset/group fan-out;
- child pipeline invocation;
- Fabric-visible activity status and failure routing.

Pipeline definitions do **not** own reusable capture/apply/recovery algorithms.

### 2. Spark Job Definition is the preferred generic headless Spark entrypoint

For repeatable production Spark batch workloads, prefer a thin Spark Job Definition that imports the released framework/domain wheels and executes a bounded `ExecutionPlan`/dataset request.

The SJD main file is an adapter, not the algorithm implementation.

### 3. Notebook remains a supported thin execution/interactive surface

Notebook is appropriate for interactive development, diagnostics, smoke tests, controlled recovery and workloads where notebook-specific capabilities are justified. A Notebook activity may also be used in production when it remains a thin adapter to released/tested package code.

The architecture does not ban production notebooks.

### 4. Activity count is not a professionalism metric

A child dataset pipeline with one SJD/Notebook activity is acceptable when the activity is a clean execution boundary with explicit parameters, durable control-plane evidence and parent orchestration visibility.

A parent domain pipeline that merely runs one opaque notebook for an entire multi-dataset platform, with no meaningful orchestration/failure/lineage boundary, is not the reference target.

### 5. Semantic template and physical execution plan are separate

Framework correctness is expressed by semantic capture/apply/recovery policy.

Physical execution may use:

- Fabric Copy;
- Spark Job Definition;
- Notebook;
- SQL/database-native execution;
- future provider-managed adapters.

The same `FULL -> REPLACE` semantics may therefore execute as `Copy -> Spark/SQL publish` or as one Spark application, depending on capability and correctness requirements.

### 6. Dispatcher becomes planner + execution backend

The current `ThreadPoolExecutor` dispatcher remains valid reference evidence but is not the final definition of orchestration.

The framework will separate provider-neutral planning/dependency/aggregation decisions from execution backends. Fabric Pipeline becomes one execution backend; in-process execution remains a deterministic reference/test backend.

## Consequences

Positive:

- avoids one bespoke visual pipeline per table;
- avoids a giant notebook becoming the platform implementation;
- makes Fabric monitoring and framework audit complementary;
- allows Copy/Spark/SQL to be chosen on technical merit;
- makes runtime logic unit/integration testable outside Fabric;
- creates a clear path to production SJD execution using released wheels and Fabric Environments;
- preserves domain/fabric-infra ownership boundaries.

Tradeoffs:

- two levels of observability must be correlated: Fabric activity runs and framework control-plane runs;
- some datasets will still look visually simple in Fabric because complexity intentionally lives in tested package code;
- execution-plan and adapter capability contracts add explicit architecture work before real tenant deployment;
- Fabric service limitations must be re-verified during implementation and cannot be treated as timeless constants.

## Rejected alternatives

### One bespoke Fabric pipeline per table

Rejected because table count should not multiply orchestration logic when only metadata differs.

### One giant orchestration notebook for the whole domain

Rejected as the default because it hides dataset-level execution/failure boundaries from Fabric monitoring and turns notebook code into a scheduler/platform.

### Put every semantic step on the Pipeline canvas

Rejected because fine-grained `EXTRACT/STAGE/VALIDATE/APPLY/RECONCILE/STATE_COMMIT` steps may share one Spark transaction/execution context. Forcing every step into a Fabric activity can weaken atomicity and duplicate framework state logic.

### Always use Spark because the framework is Python

Rejected because Fabric Copy/SQL/database-native execution may be superior for movement-centric or transaction-centric work.

## Follow-up

- add provider-neutral `ExecutionPlan` contracts;
- restructure the package by production ownership;
- split orchestration planner from execution backend;
- implement FULL -> REPLACE and SNAPSHOT_DIFF in the new structure;
- implement recovery/attempt lineage;
- add Fabric adapter contracts for Pipeline/SJD/Notebook/Copy/Environment;
- run a real approved Fabric DEV smoke only after the adapter contract is stable;
- do not publish `v0.4.0` solely because current `main` carries that development version.