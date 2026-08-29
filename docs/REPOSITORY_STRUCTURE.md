# Repository Structure — fabric-data-framework

Status: Canonical ownership/target structure
Last updated: 2026-08-29

## 1. Purpose

The repository tree must make production ownership discoverable. Organize by stable concern, not by implementation chronology, and do not create empty folders merely to look enterprise.

## 2. Design rules

1. Capture semantics stay separate from apply semantics.
2. Physical engine/capability selection stays separate from semantic algorithms.
3. Provider-neutral core stays separate from Fabric/provider adapters.
4. Control-plane persistence stays separate from data-plane algorithms.
5. Recovery is first-class, not scattered flags.
6. Provider CDC parsing belongs outside canonical CDC semantics.
7. File/API source guardrails belong in capture contracts, not domain notebooks.
8. Schema contracts belong to metadata/quality ownership, not implicit engine auto-merge.
9. Domain-specific physical bindings do not enter this repo.
10. Public imports remain intentional and evidence-backed.

## 3. Durable project memory

```text
docs/
  CURRENT_STATUS.md
  PRODUCTION_READINESS_AUDIT.md
  GUARANTEE_COVERAGE.md
  PROJECT_BLUEPRINT.md
  PRODUCTION_REQUIREMENTS.md
  EXECUTION_ENGINE_STRATEGY.md
  FABRIC_EXECUTION_MODEL.md
  CDC_DESIGN.md
  CONTROL_PLANE_DESIGN.md
  REPOSITORY_STRUCTURE.md
  CICD_DESIGN.md
  ECOSYSTEM_BLUEPRINT.md
```

## 4. Current realized Python ownership

```text
src/fabric_data_framework/
├── contracts/
│   ├── dispatch.py
│   ├── execution_plan.py
│   ├── capture_receipt.py
│   ├── recovery.py
│   └── rebuild.py
├── metadata/
│   └── capabilities.py
├── capture/
│   ├── full.py
│   ├── snapshot.py
│   ├── cdc.py
│   ├── bootstrap_cdc.py
│   ├── files.py
│   └── api.py
├── apply/
│   ├── append.py
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
│   ├── rules.py
│   ├── append.py
│   ├── full_refresh.py
│   ├── snapshot_diff.py
│   └── schema_evolution.py
├── orchestration/
│   └── planner.py
├── execution/
│   ├── append.py
│   ├── dataset_runner.py
│   ├── full_replace.py
│   ├── snapshot_diff.py
│   └── backends/
├── recovery/
│   ├── runtime.py
│   ├── replay.py
│   └── rebuild.py
├── adapters/
│   ├── fabric/
│   └── cdc/
├── extensions/
├── schema_contract.py
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

Some compatibility-era concerns remain top-level. Do not move them cosmetically without preserving public imports and migration behavior.

## 5. Ownership rules

### `contracts/`
Dependency-light stable handoff/planning/recovery value objects and protocols.

### `metadata/`
Capability profiles and semantic execution validation. Named profiles bind an engine/profile to only the behavior the framework can certify.

### `capture/`
Owns source-boundary acquisition semantics/evidence, not target history behavior.

Current source-family contracts include:

```text
full.py          authoritative full-snapshot evidence
snapshot.py      snapshot completeness evidence
cdc.py           provider-neutral CDC event/checkpoint semantics
bootstrap_cdc.py snapshot -> CDC fenced handoff
files.py         immutable manifest/readiness/version/retry-drift guards
api.py           frozen source window + cursor-chain/completeness/limit guards
```

`files.py` and `api.py` are provider-neutral guardrails. Storage SDK/HTTP client details belong in adapters/connectors/domain integration.

### `apply/`
Owns portable target semantics:

```text
APPEND
REPLACE
UPSERT
SCD1
SCD2
SNAPSHOT_DIFF
```

`append.py` owns append identity/payload fingerprint semantics. `current_state.py` is shared by batch UPSERT/SCD1. CDC current/history apply remains separate from capture normalization.

### `schema_contract.py` + `quality/schema_evolution.py`
Own typed expected schema, stable fingerprint and compatibility classification. Physical Delta/Spark schema merge cannot silently redefine these semantics.

### `data_plane/`
Owns isolated staging/candidates and shared normalized data-plane structures.

### `quality/`
Owns row/batch/schema validation, quarantine and reconciliation gates. Quality can block progression but does not mutate checkpoints itself.

### `orchestration/`
Owns metadata selection, dependencies, concurrency and aggregate status.

### `execution/`
Owns lifecycle executors and physical backend boundaries. Thin Fabric SJD/notebook entrypoints call this package rather than embedding framework algorithms.

### `recovery/`
Owns retry classification/backoff, attempt lineage, quarantine replay, FULL_REBUILD and unknown-target-outcome coordination.

### `adapters/fabric/`
Translates compiled Fabric execution units into provider request/evidence boundaries. Actual REST/SDK/CLI transport/auth stays outside semantic code.

### `adapters/cdc/`
Owns provider-specific CDC envelope and recovery-range translation. Current built-in reference is Debezium/Kafka with topic/partition/offset ordering.

### `control_plane.py` / `control_plane_io.py` / `repository.py`
Current compatibility-era split for relational schema, persistence helpers and repository interfaces/reference implementations. Schema version is currently v3.

Long-term package target remains `control_plane/` only when compatibility-safe.

### `delivery.py` / `deployment.py` / `cli.py`
Own release identity, bindings, metadata materialization, provenance and operator/delivery commands.

### `extensions/`
Resolve controlled logical names. Metadata never imports arbitrary module paths.

## 6. Current test ownership

Representative tests now include:

```text
test_append.py
test_append_execution.py
test_schema_evolution.py
test_file_capture.py
test_api_capture.py
test_scd1.py
test_upsert.py
test_cdc.py
test_cdc_scd2.py
test_bootstrap_cdc.py
test_cdc_checkpoint_persistence.py
test_debezium_kafka_cdc_adapter.py
test_cdc_provider_registry.py
test_fabric_capture_adapters.py
test_recovery.py
test_replay.py
test_rebuild.py
```

Provider adapter tests prove mapping/evidence boundaries. Semantic tests remain runnable without Fabric/Kafka.

## 7. Target package shape

The long-term ownership model may evolve toward dedicated `state/`, `control_plane/`, `observability/`, `connectors/`, `delivery/` packages when real implementation warrants the move. Do not create them merely for appearance.

## 8. Production Fabric item structure

Recommended hierarchy:

```text
Domain/source parent Pipeline
  -> resolve metadata/execution groups
  -> bounded fan-out
  -> dataset/stage execution
       -> Copy Job / Copy Activity / Dataflow / SJD / thin Notebook
       -> framework semantic runtime
```

Activity count is not an architecture-quality metric. Split execution groups when source/gateway, engine, schedule/SLA, volume, dependency, capacity or blast radius differs materially.

## 9. Refactoring rule

When moving a public/released symbol:

1. preserve/re-export compatibility where required;
2. move tests with ownership;
3. update canonical docs;
4. run wheel + Python 3.11/3.13 CI;
5. record any intentional API break at an immutable release boundary.

## 10. Current structural next steps

1. add a shared temporal/late-event policy owner and route existing strategy-specific decisions through it;
2. add supported persistent repository/query ownership when a real store is selected;
3. add actual Fabric/Kafka transport/backend modules without leaking service APIs into semantic packages;
4. add additional provider adapters only as supported product scope requires.
