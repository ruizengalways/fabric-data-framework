# Repository Structure — fabric-data-framework

Status: Canonical ownership/target structure
Last updated: 2026-08-29

## Purpose and rules

The tree must make production ownership discoverable. Organize by stable concern, not implementation chronology, and do not create empty enterprise-looking packages without real ownership.

Core rules: keep capture separate from apply; physical execution separate from semantics; provider-neutral core separate from adapters; recovery first-class; provider CDC parsing outside canonical CDC; file/API guards in capture; schema and temporal compatibility in quality/contracts; domain bindings outside this repo; public imports intentional and evidence-backed.

## Durable project memory

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

## Current realized Python ownership

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
│   ├── schema_evolution.py
│   └── temporal.py
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
├── operator.py
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

## Ownership highlights

### `capture/`
Owns source-boundary evidence, not target history. `files.py` freezes immutable file manifests; `api.py` freezes logical windows/cursor chains. Provider storage/HTTP SDKs stay outside these semantic guards.

### `apply/`
Owns portable APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF semantics. `current_state.py` is shared by batch UPSERT/SCD1. CDC apply remains separate from provider normalization.

### `quality/temporal.py`
Owns shared provider-neutral source-order/event-time classification. Strategy modules choose actions/errors but do not invent independent comparison semantics.

### `schema_contract.py` + `quality/schema_evolution.py`
Own typed expected schema, stable fingerprint and compatibility classification. Physical engine auto-merge does not own this semantic decision.

### `recovery/`
Owns retry classification/backoff, attempt lineage, quarantine replay, FULL_REBUILD and unknown-target-outcome coordination. Durable target-operation idempotency belongs here/control-plane state as the next hardening slice.

### `adapters/fabric/`
Translates compiled Fabric execution units into provider request/evidence boundaries. Actual REST/SDK/CLI transport/auth stays outside semantic code.

### `adapters/cdc/`
Owns provider-specific CDC envelope and recovery-range translation. Current built-in reference is Debezium/Kafka with topic/partition/offset ordering.

### `operator.py`
Read-only typed operational projection over the relational control-plane contract. It aggregates evidence required by on-call workflows without exposing raw SQLAlchemy rows or mutating runtime state.

### `control_plane.py` / `control_plane_io.py` / `repository.py`
Compatibility-era split for schema, persistence helpers and repository interfaces/reference implementations. Current schema is v3. Long-term package restructuring should happen only when compatibility-safe.

### `delivery.py` / `deployment.py` / `cli.py`
Release identity, bindings, metadata materialization, provenance and operator/delivery commands. `control-plane-status` is intentionally read-only.

## Test ownership

Representative suites now include append/execution, schema evolution, file/API capture, temporal, operator/CLI, SCD1/UPSERT/SCD2, CDC/CDC-SCD2/bootstrap/checkpoint, Debezium/Kafka adapters, Fabric capture adapters, recovery/replay/rebuild.

Provider adapter tests prove mapping/evidence boundaries; semantic tests remain runnable without Fabric/Kafka.

## Production Fabric item structure

```text
Domain/source parent Pipeline
  -> resolve metadata/execution groups
  -> bounded fan-out
  -> dataset/stage execution
       -> Copy Job / Copy Activity / Dataflow / SJD / thin Notebook
       -> framework semantic runtime
```

Activity count is not an architecture-quality metric. Split groups when source/gateway, engine, SLA, volume, dependency, capacity or blast radius differs materially.

## Current structural next steps

1. add durable target-operation idempotency journal/state ownership;
2. select/certify a real persistent control-plane repository without changing operator-facing contracts unnecessarily;
3. add actual Fabric/Kafka transport/backend modules without leaking service APIs into semantic packages;
4. add provider adapters only as supported scope requires.
