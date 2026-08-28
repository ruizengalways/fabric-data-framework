# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine: **COMPLETE AND RELEASED AS `v0.3.0`**.
- Phase 4 — metadata-driven multi-dataset dispatcher/failure isolation: **MERGED TO `main` AS UNRELEASED 0.4.0 DEVELOPMENT SOURCE**.
- Current milestone — **PRODUCTION FRAMEWORK HARDENING; RELEASE PAUSED UNTIL THE PRODUCT SLICE IS MATERIALLY BROADER**.

## Latest architecture decision

Do **not** publish `v0.4.0` now.

The dispatcher is useful, but the framework is still too narrow to make the next public release represent the intended production platform. Current work is intentionally focused on `fabric-data-framework` before further Customer-domain expansion.

Architecture branch:

```text
architecture/production-framework-blueprint
```

adds the durable production requirements, target package structure and Fabric execution model.

## Released baseline

Framework `v0.3.0` remains the latest immutable GitHub Release.

Release run `33156000907` published:

```text
fabric_data_framework-0.3.0-py3-none-any.whl
SHA256SUMS
```

Customer exact released-wheel integration passed against those assets and Customer Phase 3 was merged. That release boundary remains frozen and should not be moved.

## Current development baseline

Framework PR #9 was rebuilt on the released 0.3.0 baseline and squash-merged as:

```text
aaf346ba048f20d113208de566c648b0da58e373
```

Merge-triggered `main` CI run `33158188037` passed:

```text
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
```

The source version on `main` is `0.4.0`, but that number is currently a development version only. No immutable `v0.4.0` Release should be created yet.

## Current implemented runtime

The framework currently provides:

- typed semantic config/runtime override contracts;
- infrastructure binding abstraction;
- logical control-plane schema and repository contracts;
- composite WATERMARK selection with tie-breakers/overlap;
- normalized Bronze envelope;
- row DQ/quarantine primitives;
- deterministic reference SCD2 behavior;
- reconciliation/state commit gate;
- one WATERMARK -> Bronze -> DQ -> SCD2 execution slice;
- metadata-driven dispatcher with dependency validation, bounded parallelism, dataset fault isolation, dependent blocking and criticality-aware aggregate outcome;
- immutable release/delivery contracts and CLI;
- 44 framework tests.

These are a strong foundation, not yet the full production product.

## Why the package is being restructured

The current source tree is still flat:

```text
config.py
runtime.py
operations.py
control_plane.py
repository.py
dispatcher.py
execution.py
watermark.py
bronze.py
quality.py
reconciliation.py
scd2.py
delivery.py
deployment.py
cli.py
```

As FULL/SNAPSHOT/CDC/recovery/schema/delete/Fabric adapters are added, this shape would become difficult to navigate and encourage mixed ownership.

Target ownership is documented in `docs/REPOSITORY_STRUCTURE.md` and centers on:

```text
contracts
metadata
capture
apply
data_plane
quality
orchestration
execution
recovery
state
control_plane
observability
connectors
adapters/fabric
delivery
testing
```

The restructure will be compatibility-conscious because `v0.3.0` already exists.

## New durable production requirements

`docs/PRODUCTION_REQUIREMENTS.md` is the canonical capability/backlog matrix.

It now explicitly requires production handling for:

- FULL/complete-snapshot correctness;
- safe REPLACE publication and empty/incomplete-source guards;
- SNAPSHOT_DIFF delete safety;
- APPEND/UPSERT/SCD1/SCD2 semantics;
- ordered CDC and bootstrap-to-CDC handoff;
- retry/backfill/replay/full rebuild;
- unknown target-commit outcome;
- row/batch quarantine and no-silent-loss accounting;
- reconciliation completion gates;
- schema evolution and breaking-change policy;
- late/out-of-order/conflicting duplicate policy;
- state/lease/idempotency correctness;
- source/capacity-aware concurrency;
- durable observability/operator status;
- SLO/alerting hooks;
- identity/secrets/binding boundaries;
- Fabric Pipeline/SJD/Notebook/Copy/Environment integration;
- performance/cost evidence requirements;
- certification classes and real Fabric smoke evidence.

## Fabric execution decision

ADR 0007 and `docs/FABRIC_EXECUTION_MODEL.md` define the accepted runtime boundary.

Key decision:

```text
Fabric Pipeline
  = orchestration / trigger / control flow / fan-out / activity visibility

Spark Job Definition
  = preferred generic headless production Spark application entrypoint

Notebook
  = supported thin interactive/smoke/diagnostic execution surface;
    production use is allowed where justified

Python framework/domain wheels
  = reusable correctness/business implementation
```

A child dataset pipeline containing one SJD/Notebook activity is not considered unprofessional when it is a deliberate thin execution boundary with durable framework state/audit.

The anti-pattern is one opaque notebook owning the whole domain scheduler plus extraction, DQ, publication, state and recovery logic.

Fabric Copy/SQL/database-native execution should be used when those engines are better suited than Spark.

## FULL refresh target

The first new strategy implementation after structural hardening is `FULL -> REPLACE`.

Required flow:

```text
freeze source intent
  -> extract complete candidate
  -> isolated stage
  -> schema/DQ/completeness guards
  -> reconciliation
  -> safe/atomic publication
  -> state/audit commit
```

An unexpected zero-row or incomplete source must not automatically wipe the target.

`SNAPSHOT -> SNAPSHOT_DIFF` follows as a separate strategy family with explicit complete-snapshot and delete-volume guards.

## Dispatcher evolution

The current dispatcher embeds `ThreadPoolExecutor`. This remains valid deterministic reference evidence, but enterprise orchestration will be split into:

```text
provider-neutral orchestration planner
  -> in-process reference backend
  -> Fabric Pipeline execution backend
```

This allows Fabric-visible dataset child execution without moving correctness algorithms into pipeline expressions.

## Current external boundary

No enterprise Fabric workspace, capacity, tenant setting, RBAC, networking, connection, credential, production dataset or runtime state has been modified.

Fabric service details used in the new architecture were checked against current Microsoft Learn documentation on 2026-08-28, but real adapter support must be proven against an approved Fabric estate before production claims are made.

## Exact next implementation sequence

1. Merge the production-framework architecture/docs slice after CI.
2. Restructure the Python package/tests by ownership while preserving current behavior and public compatibility.
3. Add provider-neutral `ExecutionPlan` / `ExecutionStep` contracts.
4. Split dispatcher planning from execution backend.
5. Implement `FULL -> REPLACE` with staging, completeness/empty-source guards, reconciliation and publication recovery.
6. Implement `SNAPSHOT -> SNAPSHOT_DIFF` with explicit delete safety.
7. Implement retry/backfill/replay/attempt/unknown-outcome recovery.
8. Add explicit delete/schema-evolution/late-out-of-order contracts.
9. Add connector capability registry.
10. Add Fabric adapter contracts for Pipeline, Spark Job Definition, Notebook, Copy, Environment, Variable Library and run correlation.
11. Add CDC -> UPSERT and bootstrap-to-CDC correctness.
12. Add a real persistent control-plane adapter/operator queries.
13. Only then decide the scope/version of the next immutable public framework release.
14. Keep Customer and `fabric-infra` secondary until the framework product boundary is substantially stronger.

## Release gate

Do not create `v0.4.0` from the current state.

The next release version may remain `0.4.0` if no public 0.4.0 artifact is created, but the release occurs only after the larger milestone passes CI/certification and represents a coherent product capability.

Do not fake Fabric-estate, security, capacity or production evidence.