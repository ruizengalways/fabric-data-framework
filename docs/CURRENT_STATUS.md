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

The intended end state is a released wheel that an enterprise domain installs once and then uses primarily through source-controlled metadata, environment bindings and bounded extension points. Routine onboarding must not require modifying `fabric-data-framework` itself.

Framework `v0.3.0` remains the latest immutable GitHub Release. The 0.4.0 source version is a development line only.

Active PR/branch:

```text
PR #13
architecture/production-framework-blueprint
```

## Latest validated implementation evidence

Latest validated hardening commit before this documentation sync:

```text
f390d4befcbf93ce9e053942b2a6c83861239d84
GitHub Actions run 33171633197
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
79 tests passed
```

Implemented development runtime now includes:

- typed semantic config/runtime override contracts;
- infrastructure binding abstraction;
- composite WATERMARK selection with tie-breakers/overlap;
- normalized Bronze envelope;
- row DQ/quarantine primitives;
- deterministic reference SCD2 behavior;
- reconciliation/state commit gates;
- metadata-driven dispatcher with dependency validation/failure isolation;
- provider-neutral orchestration planning separated from the in-process backend;
- immutable `ExecutionPlan` / execution-unit contracts;
- guarded `FULL -> REPLACE` with isolated staging, completeness/source-count/empty-source/row-drop guards, reconciliation and publication evidence;
- guarded `SNAPSHOT -> SNAPSHOT_DIFF` with complete-snapshot requirement, null/duplicate-key protection, delete-volume/delete-all guards, quarantine-aware delete blocking and reconciliation-before-publication;
- execution-engine and progress-owner metadata;
- typed `CaptureReceipt` for native/external capture handoff and run correlation;
- controlled logical-name domain extension registry;
- additive control-plane schema v2 with `execution_policy`, `ordering_policy` and environment-local `capture_receipt` persistence;
- immutable release/delivery contracts and CLI.

## Framework-first semantics and stage-level native delegation

The framework must contain complete reusable implementations for mature Data Engineering semantics. Native Fabric features are optional stage executors/accelerators, not the only implementation of a semantic guarantee.

Canonical rule:

```text
semantic requirement
    -> framework-owned contract + portable fallback implementation
    -> capability resolver
         -> delegate a stage to native Fabric only when certified equivalent
         -> otherwise execute the framework implementation
```

This means one dataset may intentionally use different engines for different stages:

```text
capture / movement
    != transform / normalize
    != apply
    != reconciliation / state
```

The current `execution.engine` metadata should be interpreted as the **capture/movement execution boundary**, not as ownership of the entire dataset lifecycle. The compiled execution plan can already split native capture from framework processing.

Example required production pattern:

```text
Dataflow Gen2 incremental/bucket refresh
    -> landing / Bronze / staging
    -> CaptureReceipt
    -> framework SCD1 / UPSERT / SCD2
    -> reconciliation
    -> framework state/audit
```

This is necessary because Fabric-native ingestion/refresh semantics can be useful while the final apply semantics are insufficient for a domain requirement.

Native final-target apply delegation is allowed only when a capability profile explicitly certifies that the native behavior is equivalent to the requested framework semantic contract. Generic profiles must fail closed or use the framework fallback rather than assuming equivalence.

Accepted architecture decisions now include:

```text
ADR 0007 — Fabric Pipeline and Spark execution boundary
ADR 0008 — separate data semantics from physical execution engine
ADR 0009 — framework-first semantics with stage-level native delegation
```

## Why native Fabric features are not the framework foundation

Current Microsoft Fabric capabilities are useful but have product-specific limitations that make them unsuitable as the sole implementation of the framework semantics.

Examples verified against Microsoft Learn on 2026-08-28:

- Copy Job CDC supports only a bounded connector set and currently has limitations including mixed CDC/non-CDC table behavior, net-change capture only and no custom capture instances;
- Copy Job SCD2 remains Preview and has source/schema restrictions;
- Dataflow Gen2 incremental refresh uses DateTime buckets and replaces changed destination buckets;
- Dataflow Gen2 incremental refresh currently supports `replace` as the destination update method rather than arbitrary SCD1/UPSERT semantics.

Therefore native features are capability-profiled adapters. They may own capture, apply, both, or neither for a specific certified scenario.

## Execution-engine model

Independent concerns remain:

```text
Capture semantics
  FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM

Capture / movement engine
  FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 |
  SPARK | MIRROR | EXTERNAL_CDC | SQL | CUSTOM

Apply semantics
  APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF

Authoritative capture progress owner
  FRAMEWORK | FABRIC_NATIVE | EXTERNAL
```

A native Copy/Dataflow activity does not import the Python wheel. It participates through a typed capture/landing receipt and common control-plane lineage.

Future metadata/compiler work must make apply-executor delegation explicit rather than overloading one engine field for the whole lifecycle.

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

SCD1/SCD2 are apply semantics, not ingestion methods. They may consume data landed by Copy Job, Copy Activity, Dataflow Gen2, Spark, Mirroring or external CDC as long as the capture contract and receipt are valid.

## Custom logic policy

Irregular datasets are supported through typed source-controlled extension references rather than framework forks.

Bounded extension points include or will include:

```text
custom capture adapter
batch/micro-batch parser
pre-apply transform
DQ rule provider
specialized apply adapter
```

Metadata references stable logical names. Domain wheels register implementations. Extensions may not bypass row accounting, reconciliation, publication/state boundaries, secrets/bindings or audit.

## Progress ownership

One physical capture operation has one authoritative checkpoint owner.

Examples:

```text
framework-bounded Copy Activity
  -> FRAMEWORK

Copy Job native incremental/CDC
  -> FABRIC_NATIVE

Debezium/Kafka
  -> EXTERNAL or an explicitly selected framework consumer
```

The framework must never maintain a competing independent watermark for a native checkpoint.

## Current external boundary

No enterprise Fabric workspace, capacity, tenant setting, RBAC, networking, connection, credential, production dataset or runtime state has been modified.

Portable/reference semantics and relational schema contracts are not the same as real Fabric production evidence. Real adapters must still be exercised against an approved Fabric estate.

## Exact next implementation sequence

1. Implement/certify framework-owned `SCD1` and `UPSERT` current-state semantics, including ordering/version/event-time conflict handling and idempotent rerun behavior.
2. Refine execution metadata/compiler so capture/movement executor and apply executor/native delegation are explicit independent decisions.
3. Add Fabric Copy Job / Copy Activity / Dataflow Gen2 / Spark adapter contracts that emit immutable `CaptureReceipt` and native run correlation.
4. Implement retry/backfill/replay/attempt lineage and unknown-commit recovery.
5. Implement CDC normalization -> UPSERT/SCD1/SCD2 plus bootstrap-to-CDC handoff, including external CDC adapters.
6. Add explicit schema-evolution/late/out-of-order/duplicate-conflict policies across current-state and history strategies.
7. Add APPEND identity/collision semantics and broader strategy certification.
8. Add real persistent control-plane repository/operator query surface.
9. Prove hybrid Fabric scenarios in DEV, including at least one native-capture + framework-apply path.
10. Only then decide the scope/version of the next immutable public framework release.
11. Keep Customer expansion and `fabric-infra` secondary until the framework product boundary is substantially stronger.

## Release gate

Do not create `v0.4.0` from the current state.

The next release may still use version `0.4.0` if no public 0.4.0 artifact exists, but release only when the framework represents a coherent broadly usable enterprise product slice and passes certification.

Do not fake Fabric-estate, security, capacity or production evidence.
