# Repository Structure — fabric-data-framework

Status: Canonical ownership/target structure
Last updated: 2026-08-29

## 1. Purpose

The repository tree must make production ownership discoverable before a new engineer opens a file.

The early flat package was useful for proving vertical slices. The unreleased 0.4.0 hardening line is moving real implementations into stable production concerns rather than growing a flat module list.

Do not create empty folders merely to look enterprise. Introduce an ownership package when real code and guarantees belong there.

## 2. Design rules

1. Organize by stable production concern, not implementation chronology.
2. Keep capture semantics separate from apply semantics.
3. Keep physical execution/capability selection separate from semantic algorithms.
4. Keep provider-neutral core separate from Fabric/provider adapters.
5. Keep control-plane persistence separate from data-plane algorithms.
6. Keep recovery as a first-class package, not scattered flags.
7. Keep delivery/release tooling separate from runtime execution.
8. Provider CDC envelope parsing belongs outside canonical CDC semantics.
9. Domain/company-specific physical bindings do not enter this repository.
10. Public imports remain intentional; restructuring must not accidentally expand API promises.
11. Preserve released-consumer compatibility where reasonable.
12. Every claimed production guarantee maps to code + executable evidence.

## 3. Current top-level project memory

```text
fabric-data-framework/
├── .github/workflows/
├── docs/
│   ├── adr/
│   ├── runbooks/
│   ├── ECOSYSTEM_BLUEPRINT.md
│   ├── PROJECT_BLUEPRINT.md
│   ├── PRODUCTION_REQUIREMENTS.md
│   ├── EXECUTION_ENGINE_STRATEGY.md
│   ├── FABRIC_EXECUTION_MODEL.md
│   ├── CDC_DESIGN.md
│   ├── REPOSITORY_STRUCTURE.md
│   ├── CONTROL_PLANE_DESIGN.md
│   ├── CICD_DESIGN.md
│   ├── PRODUCTION_READINESS_AUDIT.md
│   ├── GUARANTEE_COVERAGE.md
│   └── CURRENT_STATUS.md
├── src/fabric_data_framework/
├── tests/
├── pyproject.toml
└── README.md
```

Docs are durable project memory, not secondary prose.

## 4. Current realized Python ownership

The hardening branch currently contains meaningful packages including:

```text
src/fabric_data_framework/
├── contracts/
│   ├── dispatch.py
│   ├── execution_plan.py
│   ├── capture_receipt.py
│   └── recovery.py
├── metadata/
│   └── capabilities.py
├── capture/
│   ├── full.py
│   ├── snapshot.py
│   ├── cdc.py
│   └── bootstrap_cdc.py
├── apply/
│   ├── current_state.py
│   ├── replace.py
│   ├── upsert.py
│   ├── scd1.py
│   ├── cdc.py
│   ├── cdc_scd2.py
│   └── snapshot_diff.py
├── data_plane/
│   └── staging.py
├── quality/
├── orchestration/
│   └── planner.py
├── execution/
│   ├── dataset_runner.py
│   ├── full_replace.py
│   ├── snapshot_diff.py
│   └── backends/
├── recovery/
│   └── runtime.py
├── adapters/
│   └── fabric/
│       ├── contracts.py
│       ├── adapter.py
│       └── __init__.py
├── extensions.py
├── config.py
├── control_plane.py
├── control_plane_io.py
├── repository.py
├── runtime.py
├── watermark.py
├── bronze.py
├── scd2.py
├── delivery.py
├── deployment.py
└── cli.py
```

Some older modules remain top-level for compatibility/incremental refactoring. New capabilities should land in their stable ownership package when the boundary is clear.

## 5. Ownership rules

### `contracts/`

Dependency-light stable value objects/interfaces: execution plan, capture receipt, recovery requests/lineage, dispatch/runtime/binding contracts. No Fabric client dependencies.

### `metadata/`

Turns source-controlled metadata into immutable effective semantics. Owns validation, hashing, compatibility and `(engine, capability_profile)` resolution.

### `capture/`

Owns bounded source acquisition semantics and source-boundary evidence. It does not decide target history/current-state behavior.

Current examples:

```text
capture/full.py
capture/snapshot.py
capture/cdc.py
capture/bootstrap_cdc.py
```

`capture/cdc.py` is provider-neutral. Debezium/LSN/binlog/Kafka/native Fabric envelope mapping belongs in adapters/connectors/extensions.

### `apply/`

Owns portable target semantics independent from movement mechanism.

Current examples:

```text
apply/current_state.py
apply/replace.py
apply/upsert.py
apply/scd1.py
apply/cdc.py
apply/cdc_scd2.py
apply/snapshot_diff.py
```

`apply/cdc.py` handles CDC current-state semantics for UPSERT/SCD1. `apply/cdc_scd2.py` handles history semantics while keeping source order separate from valid time.

APPEND remains future work.

### `data_plane/`

Owns normalized Bronze/staging/publication candidates/row accounting shared by strategies.

### `quality/`

Owns row/batch/schema quality, quarantine and reconciliation gates. Quality may block state/publication but must not secretly mutate checkpoints.

### `orchestration/`

Owns dataset selection, dependency readiness, concurrency and aggregate policy. It does not implement capture/apply algorithms.

### `execution/`

Owns lifecycle execution and physical backend boundaries. Thin Fabric SJD/notebook entrypoints should call this/runtime packages rather than embed algorithms.

### `recovery/`

Owns retry classification/backoff, attempt lineage, reprocess intent and unknown-target-outcome recovery. Future replay/rebuild executors belong here or under strategy-specific execution with explicit recovery contracts.

### `adapters/`

Provider-specific translation only. Semantic correctness remains in provider-neutral packages.

Current Fabric adapter layer handles physical capture request/evidence/receipt conversion. Future CDC provider adapters normalize provider envelopes into `CDCEvent`/`CDCCheckpoint`.

### `control_plane.py` / `control_plane_io.py` / `repository.py`

Current compatibility-era split for schema, small relational persistence helpers and repository interfaces/reference adapter.

Current environment-local state now includes `cdc_checkpoint` with optimistic concurrency.

Long-term package target remains `control_plane/` once migration can preserve public compatibility cleanly.

### `delivery.py` / `deployment.py` / `cli.py`

Release identity, bindings, metadata materialization, deployment planning/provenance and operator/delivery commands.

### extensions

Custom behavior is selected by registered logical name, not arbitrary module path from metadata.

## 6. Target package shape

```text
src/fabric_data_framework/
├── contracts/
├── metadata/
├── capture/
│   ├── base.py
│   ├── full.py
│   ├── watermark.py
│   ├── snapshot.py
│   ├── cdc.py
│   ├── bootstrap_cdc.py
│   ├── mirror.py
│   └── stream.py
├── apply/
│   ├── base.py
│   ├── append.py
│   ├── replace.py
│   ├── current_state.py
│   ├── upsert.py
│   ├── scd1.py
│   ├── scd2.py
│   ├── cdc.py
│   ├── cdc_scd2.py
│   └── snapshot_diff.py
├── data_plane/
├── quality/
├── orchestration/
├── execution/
├── recovery/
├── state/
│   ├── watermark.py
│   ├── cdc.py
│   ├── checkpoints.py
│   ├── leases.py
│   └── idempotency.py
├── control_plane/
│   ├── schema.py
│   ├── repository.py
│   ├── migrations.py
│   └── queries.py
├── observability/
├── connectors/
│   ├── base.py
│   ├── capabilities.py
│   ├── registry.py
│   └── cdc/
├── adapters/
│   ├── fabric/
│   ├── cdc/
│   └── testing/
├── delivery/
├── extensions/
└── testing/
```

Exact names may evolve; concern ownership must not blur.

## 7. CDC/provider boundary

Canonical direction:

```text
provider envelope
  Debezium / database-native / Copy Job / custom
        |
        v
adapter / connector
        |
        v
CDCEvent + CDCCheckpoint
        |
        v
capture/cdc.py
        |
        v
apply/cdc.py or apply/cdc_scd2.py
```

Do not put provider-specific JSON field names or LSN string parsing inside apply algorithms.

## 8. Production Fabric item structure

A professional production implementation does not require many visible activities merely to look complex.

Recommended hierarchy:

```text
Domain/source parent Pipeline
  -> resolve metadata/execution groups
  -> bounded fan-out
  -> dataset/stage child execution
       -> Copy Job / Copy Activity / Dataflow / SJD / thin Notebook as planned
       -> framework semantic runtime
```

A child pipeline with one thin SJD/notebook can be professional when the reusable algorithms/state/recovery/audit are in released packages/control plane and parameters/bindings are explicit. Activity count is not an architecture-quality metric.

Use separate pipelines/execution groups when operational boundaries differ materially: source/gateway, capture engine, schedule/SLA, volume, criticality, dependency, capacity or blast radius.

## 9. Test ownership

Tests should mirror ownership concerns rather than one giant integration file:

```text
test_scd1.py
test_upsert.py
test_cdc.py
test_cdc_scd2.py
test_bootstrap_cdc.py
test_cdc_checkpoint_persistence.py
test_fabric_capture_adapters.py
test_recovery.py
...
```

Provider adapter tests prove mapping/evidence boundaries. Semantic tests must remain runnable without Fabric.

## 10. Refactoring rule

Do not perform cosmetic package moves that create compatibility churn without adding ownership clarity.

When moving a public/released symbol:

1. preserve/re-export compatibility where required;
2. move tests with ownership;
3. update canonical docs;
4. run wheel + Python 3.11/3.13 CI;
5. record any intentional API break in the eventual release boundary.

## 11. Current structural next steps

1. add provider CDC adapter/connectors under a clear provider boundary;
2. implement APPEND under `apply/`;
3. add file/API capture guardrails under `capture/`/connectors;
4. complete recovery executors under `recovery/`;
5. move persistent state/query concerns toward `control_plane/` and `state/` only when compatibility-safe;
6. add actual Fabric transport/backend modules without leaking service APIs into semantic packages.
