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

The intended end state is a released wheel that an enterprise domain can install and then use primarily through source-controlled metadata, environment bindings and bounded extension points. Routine onboarding must not require modifying `fabric-data-framework` itself.

Framework `v0.3.0` remains the latest immutable GitHub Release. The 0.4.0 source version is currently a development line only.

Active PR/branch:

```text
PR #13
architecture/production-framework-blueprint
```

## Current implemented development runtime

The hardening branch now provides:

- typed semantic config/runtime override contracts;
- infrastructure binding abstraction;
- logical control-plane schema and repository contracts;
- composite WATERMARK selection with tie-breakers/overlap;
- normalized Bronze envelope;
- row DQ/quarantine primitives;
- deterministic reference SCD2 behavior;
- reconciliation/state commit gates;
- metadata-driven dispatcher with dependency validation/failure isolation;
- provider-neutral orchestration planning separated from the in-process execution backend;
- immutable `ExecutionPlan` / execution-unit contracts;
- compatibility-preserving `execution/` package restructuring;
- guarded `FULL -> REPLACE` implementation with staging, completeness/source-count/empty-source/row-drop guards, reconciliation and publication evidence;
- immutable release/delivery contracts and CLI.

Latest validated CI after `FULL -> REPLACE`:

```text
GitHub Actions run 33168301404
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
59 tests passed
```

`SNAPSHOT -> SNAPSHOT_DIFF` is the next implementation slice and must not be marked complete until committed and CI-validated.

## Canonical architecture documents

The current production design is recoverable from:

```text
docs/PRODUCTION_REQUIREMENTS.md
docs/REPOSITORY_STRUCTURE.md
docs/FABRIC_EXECUTION_MODEL.md
docs/EXECUTION_ENGINE_STRATEGY.md
docs/PROJECT_BLUEPRINT.md
docs/CONTROL_PLANE_DESIGN.md
docs/CICD_DESIGN.md
```

Accepted architecture decisions include:

```text
ADR 0007 — Fabric Pipeline and Spark execution boundary
ADR 0008 — separate data semantics from physical execution engine
```

## Execution-engine decision

The framework does **not** require every dataset to be ingested by Notebook/Spark/Python.

The following are independent axes:

```text
Capture semantics
  FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM

Physical execution/movement engine
  FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 |
  SPARK | MIRROR | EXTERNAL_CDC | SQL | CUSTOM

Apply semantics
  APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF

Authoritative progress owner
  FRAMEWORK | FABRIC_NATIVE | EXTERNAL
```

A capability resolver/compiler will validate the selected combination and emit one immutable `ExecutionPlan`.

Native Fabric movement is first-class:

- Copy Job for supported multi-table/full/incremental/native-CDC replication where its semantics are sufficient;
- Copy Activity when framework-controlled bounds/pipeline orchestration/custom source queries are required;
- Dataflow Gen2 for suitable low-code Power Query ingestion/transformation, not as a mandatory hundred-table ingestion engine;
- Spark/framework execution for composite ordering, irregular formats, custom micro-batches, advanced SCD/recovery or other code-level correctness requirements;
- external Debezium/Kafka CDC where a governed CDC feed already exists.

A native Copy/Dataflow activity does not import the Python wheel. It participates through a typed capture/landing receipt and common control-plane lineage.

## Many-table metadata-driven topology

For a source with tens or hundreds of tables, avoid both one bespoke pipeline per table and one giant opaque pipeline.

Use a small number of reusable metadata-selected execution groups, for example:

```text
pl_erp_daily
   +-- erp_full_reference
   +-- erp_incremental_current
   +-- erp_incremental_history
   +-- erp_cdc_transactional
   +-- erp_custom_complex
```

Useful grouping dimensions include source limits, movement engine, capture semantics, schedule/SLA, volume, criticality/blast radius, dependencies and Fabric capacity.

SCD2 remains an apply/history semantic rather than an ingestion method. A separate SCD2 pipeline is allowed when operationally useful but is not required by the framework architecture.

## Custom logic policy

Irregular datasets are supported through typed source-controlled extension references rather than framework forks.

Planned bounded extension points include:

```text
custom capture adapter
batch/micro-batch parser
pre-apply transform
DQ rule provider
specialized apply adapter
```

Extensions may not bypass framework row accounting, reconciliation, publication/state boundaries or secret/binding policy.

## Progress ownership

One physical capture operation has one checkpoint authority.

Examples:

```text
framework-bounded Copy Activity
  -> FRAMEWORK progress owner

Copy Job incremental/native CDC
  -> FABRIC_NATIVE progress owner

Debezium/Kafka
  -> EXTERNAL or explicitly selected framework consumer owner
```

The framework must never maintain a competing independent watermark for a native Copy Job checkpoint.

## Current external boundary

No enterprise Fabric workspace, capacity, tenant setting, RBAC, networking, connection, credential, production dataset or runtime state has been modified.

Current Fabric product capabilities were re-checked against Microsoft Learn on 2026-08-28. Real adapter support still requires execution evidence from an approved enterprise Fabric estate.

## Exact next implementation sequence

1. Finish and CI-validate `SNAPSHOT -> SNAPSHOT_DIFF` with complete-snapshot/delete guards.
2. Add execution-engine/progress-owner/capture-receipt contracts and capability registry to deployed metadata/planning.
3. Add Fabric Copy Job / Copy Activity / Dataflow / Spark adapter contracts and immutable native-run correlation.
4. Implement retry/backfill/replay/attempt lineage and unknown-commit recovery.
5. Add explicit delete/schema-evolution/late/out-of-order/duplicate-conflict policies.
6. Implement CDC normalization -> UPSERT and bootstrap-to-CDC handoff, including external CDC adapters.
7. Add APPEND/SCD1 completeness and native-delegation capability validation.
8. Add real persistent control-plane repository/operator query surface.
9. Prove the first real Fabric Environment + Pipeline + native-copy/Spark execution in DEV.
10. Only then decide the scope/version of the next immutable public framework release.
11. Keep Customer expansion and `fabric-infra` secondary until the framework product boundary is substantially stronger.

## Release gate

Do not create `v0.4.0` from the current state.

The next release may still use version `0.4.0` if no public 0.4.0 artifact exists, but release only when the framework represents a coherent, broadly usable enterprise product slice and passes certification.

Do not fake Fabric-estate, security, capacity or production evidence.
