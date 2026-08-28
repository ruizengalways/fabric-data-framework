# Repository Structure — fabric-data-framework

Status: Canonical ownership/target structure
Last updated: 2026-08-29

## 1. Purpose

The tree should make production ownership discoverable. Organize by stable concern rather than implementation chronology, and do not create empty enterprise-looking folders without real ownership.

## 2. Design rules

1. Capture semantics stay separate from apply semantics.
2. Provider-neutral semantic code stays separate from provider adapters.
3. Capture/apply engine selection stays separate from semantic algorithms.
4. Control-plane persistence stays separate from data-plane mutation logic.
5. Recovery is a first-class package, not scattered retry flags.
6. Delivery/release tooling stays separate from runtime execution.
7. Domain/company-specific bindings do not enter this repository.
8. Public imports are intentional; internal layout does not automatically become API.
9. Each claimed guarantee maps to executable evidence in `GUARANTEE_COVERAGE.md`.

## 3. Current realized ownership

```text
src/fabric_data_framework/
├── contracts/
│   ├── capture_receipt.py
│   ├── dispatch.py
│   ├── execution_plan.py
│   └── recovery.py
├── metadata/
│   └── capabilities.py
├── capture/
│   ├── full.py
│   └── snapshot.py
├── apply/
│   ├── current_state.py
│   ├── replace.py
│   ├── scd1.py
│   ├── snapshot_diff.py
│   └── upsert.py
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
│   ├── __init__.py
│   └── runtime.py
├── adapters/
│   └── fabric/
│       ├── __init__.py
│       ├── contracts.py
│       └── adapter.py
├── config.py
├── extensions.py
├── control_plane.py
├── control_plane_io.py
├── repository.py
├── watermark.py
├── bronze.py
├── scd2.py
├── delivery.py
├── deployment.py
└── cli.py
```

Current tests include dedicated suites for current-state apply, Fabric capture adapters, recovery runtime/hardening and recovery relational control-plane evidence.

## 4. Ownership rules

### `contracts/`

Dependency-light stable value objects/interfaces. Current examples: ExecutionPlan, CaptureReceipt, dispatch request/outcome, ReprocessRequest and DatasetAttemptLineage.

No Fabric client/auth dependencies belong here.

### `metadata/`

Semantic validation, effective config and capability/profile resolution. Provider limitations are expressed here/adapters rather than leaking into SCD algorithms.

### `capture/`

Provider-neutral source-boundary/change semantics. Next major owner is `capture/cdc.py` plus bootstrap handoff.

### `apply/`

Provider-neutral target semantics.

Current realized core:

```text
current_state.py   shared ordered/idempotent primitive
replace.py
upsert.py
scd1.py
snapshot_diff.py
```

Top-level `scd2.py` remains for compatibility and may move behind stable imports later. APPEND remains future work.

### `orchestration/`

Dataset selection, dependency readiness, concurrency and aggregate policy. Does not own capture/apply algorithms.

### `execution/`

Reference dataset runners/backends that compose semantic primitives. Provider-specific API mechanics do not belong here.

### `recovery/`

Generic retry classification, backoff, attempt lineage, reprocess mode lifecycle and unknown-commit reconciliation behavior.

Strategy-specific replay/rebuild/restaging can split into dedicated modules as implementation grows; do not create placeholders prematurely.

### `adapters/fabric/`

Provider bridge from compiled framework plan to Microsoft Fabric invocation evidence.

Current realized boundary:

```text
contracts.py
  FabricCaptureRequest
  FabricNativeRunEvidence
  FabricCaptureTransport

adapter.py
  FabricCaptureAdapter
  CopyJobCaptureAdapter
  CopyActivityCaptureAdapter
  DataflowGen2CaptureAdapter
  SparkJobCaptureAdapter
  FabricAdapterRegistry
```

The transport interface is intentionally separate from semantic validation. Future real REST/SDK/CLI clients can be added without changing core semantics.

### control plane

`control_plane.py`, `control_plane_io.py`, `repository.py` currently own the reference schema/repository boundary. A future package split into schema/repository/migrations/queries is acceptable when real implementation volume justifies it.

### delivery

`delivery.py`, `deployment.py`, `cli.py` own immutable release identity, bindings, metadata materialization and deployment operations. Runtime state is not a release artifact.

## 5. Target evolution

Expected future additions as real capabilities land:

```text
capture/cdc.py
capture/bootstrap_cdc.py
apply/append.py
quality/schema_contracts.py
recovery/replay.py           # when real replay data-plane wiring exists
recovery/rebuild.py          # when real reset/rebuild execution exists
adapters/fabric/<real transport/client modules>
adapters/fabric/pipeline.py
control_plane/<persistent repository package>
observability/<operator/status package>
testing/<shared certification utilities>
```

Do not create these only to satisfy a diagram.

## 6. Dependency direction

Preferred internal direction:

```text
contracts/config
      |
      v
metadata/capabilities
      |
      +--> capture/apply/quality/recovery semantics
      |
      v
ExecutionPlan
      |
      +--> reference execution
      +--> adapters/fabric
      |
      v
repository/control-plane evidence
```

Provider adapters may depend on stable contracts/config. Semantic apply/capture modules must not depend on Fabric adapters.

## 7. Tests mirror guarantees

Representative test ownership:

```text
test_scd1.py / test_upsert.py
  ordered current-state correctness

test_full_replace.py / test_snapshot_diff.py
  destructive-load correctness

test_execution_engines.py / test_stage_execution_policy.py
  capability and capture/apply plan correctness

test_fabric_capture_adapters.py
  provider adapter/evidence fail-closed behavior

test_recovery.py / test_recovery_runtime_hardening.py
  retry/lineage/unknown-outcome correctness

test_recovery_control_plane.py
  relational reprocess/attempt evidence
```

## 8. Current next structural work

The next new package capability should be CDC, not a directory reorganization:

```text
capture/cdc.py
  canonical event envelope/normalization/order identity
```

Only after behavior exists should bootstrap/checkpoint/provider modules expand around it.
