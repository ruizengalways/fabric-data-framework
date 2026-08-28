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

Latest fully green implementation commit before the documentation audit:

```text
82bf3d97e6e08e9620bacdd1de25a14a2f7d489c
GitHub Actions run 33172961692
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
91 tests passed
```

The coherent audit/docs head immediately before this status-evidence commit was also fully green:

```text
21b0f83dc33bc16c472a3a69821a31324785e065
GitHub Actions run 33173705351
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
91 tests passed
```

That audit head includes the new readiness/guarantee maps and synchronized README/blueprint/requirements/execution/control-plane/repository-structure docs. This `CURRENT_STATUS` evidence commit must also remain green before further implementation proceeds.

## Implemented development runtime

The hardening branch now provides:

- strict typed semantic config and allow-listed runtime overrides;
- infrastructure/environment binding abstraction;
- composite WATERMARK selection with tie-breakers/overlap;
- normalized Bronze lineage envelope;
- row DQ/quarantine and row-accounting primitives;
- deterministic reference SCD2 behavior;
- deterministic ordered SCD1 current-state behavior;
- reconciliation/state commit gates for the implemented execution slices;
- metadata-driven dispatcher with dependency validation/failure isolation;
- provider-neutral orchestration planning separated from the in-process backend;
- immutable `ExecutionPlan` / execution-unit contracts;
- guarded `FULL -> REPLACE` with isolated staging, completeness/source-count/empty-source/row-drop guards, reconciliation and publication evidence;
- guarded `SNAPSHOT -> SNAPSHOT_DIFF` with complete-snapshot requirement, null/duplicate-key protection, delete-volume/delete-all guards, quarantine-aware delete blocking and reconciliation-before-publication;
- execution-engine and progress-owner metadata;
- named engine capability profiles, keyed by engine + profile rather than one optimistic global engine capability;
- typed `CaptureReceipt` for native/external capture handoff and native-run correlation;
- controlled logical-name domain extension registry;
- additive control-plane schema v2 with `execution_policy`, `ordering_policy` and environment-local `capture_receipt` persistence;
- immutable release/delivery contracts and CLI.

## SCD1 implementation scope

`src/fabric_data_framework/apply/scd1.py` is now the canonical provider-neutral SCD1 fallback for the certified scope.

It implements:

```text
composite merge key
source ordering tuple (event time / version / sequence / LSN-like values)
latest-row selection within one incoming batch
exact-rerun idempotency
stale-row IGNORE or ERROR policy
equal-position conflicting payload -> fail closed
unordered changed update -> fail closed unless explicitly authorized
separate duplicate / incoming-superseded / stale metrics
```

This is intentionally independent from the physical ingestion mechanism.

## Framework-first semantics and stage-level native delegation

Accepted ADR 0009 establishes the current product boundary:

```text
semantic requirement
    -> framework-owned contract + portable fallback implementation
    -> capability resolver
         -> delegate an individual stage to native Fabric only when certified
         -> otherwise use the framework implementation
```

Physical ownership is stage-level:

```text
capture / movement
    != normalize / transform
    != apply
    != reconcile / state
```

The current `execution.engine` field is interpreted as the **capture/movement execution boundary**, not ownership of the full dataset lifecycle.

Native final-target apply delegation is future work. It may be enabled only through an explicit capability profile that certifies semantic equivalence to the requested framework apply contract.

## Dataflow Gen2 incremental -> framework SCD1

The named profile:

```text
dataflow_gen2_incremental_bucket_v1
```

is implemented in `metadata/capabilities.py`.

It explicitly certifies only the bounded capture/staging role for Fabric Dataflow Gen2 DateTime-bucket incremental refresh:

```text
capture_strategy = WATERMARK
capture engine   = DATAFLOW_GEN2
progress_owner   = FABRIC_NATIVE
composite WM     = NOT CERTIFIED
```

The planner/reference test proves this valid composition:

```text
Dataflow Gen2 incremental capture/stage
    -> framework processing unit
    -> framework SCD1 apply
```

It does **not** claim Dataflow Gen2's bucket `replace` behavior is itself SCD1.

Equivalent hybrid patterns are intended for Copy Job, Copy Activity, Mirroring and external CDC feeds.

## Why native Fabric features are adapters, not the semantic foundation

Current Microsoft Fabric features are useful but product/connector/version constrained.

Verified against Microsoft Learn on 2026-08-28:

- Copy Job CDC supports a bounded connector set and has current limitations such as mixed CDC/non-CDC table behavior, net-changes-only capture and no custom capture instances;
- Copy Job SCD2 remains Preview and has source/schema restrictions;
- Dataflow Gen2 incremental refresh uses DateTime buckets and reprocesses/replaces changed destination buckets;
- Dataflow Gen2 incremental refresh does not provide arbitrary framework SCD1/UPSERT semantics as its destination update model.

Therefore the framework maintains portable semantics and uses native services through conservative capability profiles.

## Execution model

Independent concerns:

```text
Capture semantics
  FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM

Capture / movement engine
  FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 |
  SPARK | FABRIC_MIRRORING | EXTERNAL_CDC | SQL | CUSTOM

Apply semantics
  APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF

Authoritative physical-capture progress owner
  FRAMEWORK | FABRIC_NATIVE | EXTERNAL
```

A native Copy/Dataflow activity does not import the framework wheel. It hands off landing/run/checkpoint evidence through `CaptureReceipt` and the common control plane.

The next execution-planning evolution must make **apply executor/native apply delegation** a separate explicit decision rather than overloading the capture engine.

## Many-table metadata-driven topology

For tens/hundreds of tables, avoid both one bespoke pipeline per table and one opaque giant pipeline.

Use reusable metadata-selected execution groups, for example:

```text
pl_erp_daily
   +-- erp_full_reference
   +-- erp_incremental_current
   +-- erp_incremental_history
   +-- erp_cdc_transactional
   +-- erp_custom_complex
```

Grouping can reflect source limits, capture engine, schedule/SLA, volume, criticality/blast radius, dependencies, gateway/network boundary and Fabric capacity.

SCD1/SCD2 are apply semantics. They may consume data landed by Dataflow, Copy, Spark, Mirroring or external CDC when the capture contract is valid.

## Extension policy

Irregular datasets use typed source-controlled logical extension references rather than framework forks or arbitrary Python expressions in metadata.

Bounded extension categories include:

```text
custom capture adapter
batch/micro-batch parser
pre-apply transform
DQ rule provider
specialized apply adapter
```

Domain packages register implementations. Extensions may not bypass row accounting, reconciliation, publication/state boundaries, secrets/bindings or audit.

## Progress ownership

One physical capture operation has one authoritative checkpoint owner.

Examples:

```text
framework-bounded Copy Activity -> FRAMEWORK
Copy Job native incremental/CDC -> FABRIC_NATIVE
Dataflow Gen2 native incremental -> FABRIC_NATIVE
Debezium/Kafka -> EXTERNAL or explicit framework consumer
```

Progress ownership does not imply apply ownership.

## Durable audit documents

New conversations must read:

```text
docs/PRODUCTION_READINESS_AUDIT.md
docs/GUARANTEE_COVERAGE.md
```

`PRODUCTION_READINESS_AUDIT.md` separates portable semantics, deterministic certification, real Fabric evidence and external enterprise controls.

`GUARANTEE_COVERAGE.md` maps each claimed guarantee to its code owner and representative executable test, and explicitly lists uncovered guarantees.

The synchronized canonical reading order is also recorded in `README.md` and `PROJECT_BLUEPRINT.md`.

## Current external boundary

No enterprise Fabric workspace, capacity, tenant setting, RBAC, networking, connection, credential, production dataset or runtime state has been modified by this hardening work.

Portable/reference semantics and SQLAlchemy schema proof are not the same as real Fabric production evidence.

## Exact next implementation sequence

1. Implement/certify framework-owned **UPSERT** using the ordered/idempotent current-state foundations established by SCD1.
2. Make capture/movement executor and apply executor/native-apply delegation separate explicit execution-plan decisions.
3. Add Fabric Copy Job / Copy Activity / Dataflow Gen2 / Spark adapter contracts that emit immutable `CaptureReceipt` and native run correlation.
4. Implement RETRY/BACKFILL/REPLAY/FULL_REBUILD attempt lineage, retryability and unknown-commit recovery.
5. Implement CDC normalization -> UPSERT/SCD1/SCD2 plus snapshot-to-CDC bootstrap handoff, including external CDC adapters.
6. Add general schema-evolution/late/out-of-order/duplicate-conflict policies.
7. Add APPEND identity/collision semantics and broader strategy certification.
8. Add a supported persistent control-plane repository/operator query surface.
9. Prove at least one real hybrid Fabric DEV scenario: native capture -> `CaptureReceipt` -> framework SCD1/UPSERT.
10. Re-run production readiness/guarantee audits.
11. Only then decide the next immutable public framework release scope/version.

## Release gate

Do not create `v0.4.0` from the current state.

The next release may still use version `0.4.0` if no public 0.4.0 artifact exists, but publication requires a coherent broadly usable enterprise product slice and certification evidence.

Do not fake Fabric-estate, security, capacity or production evidence.
