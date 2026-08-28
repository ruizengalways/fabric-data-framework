# Repository Structure — fabric-data-framework

Status: Canonical ownership/target structure
Last updated: 2026-08-28

## 1. Purpose

The repository tree should make production ownership discoverable before a new engineer opens a file.

The early flat package was useful for proving the first vertical slice. The unreleased 0.4.0 hardening branch is now migrating real implementations into stable production concerns rather than continuing to grow one flat module list.

Do not create empty folders merely to make the tree look enterprise. Ownership boundaries appear when real implementations move into them.

## 2. Design rules

1. Organize by stable production concern, not implementation chronology.
2. Keep capture semantics separate from apply semantics.
3. Keep physical execution/capability selection separate from semantic algorithms.
4. Keep provider-neutral core code separate from Fabric adapters.
5. Keep control-plane persistence separate from data-plane algorithms.
6. Keep recovery as a first-class package, not flags scattered across normal execution.
7. Keep delivery/release tooling separate from runtime execution.
8. Domain code and company-specific physical bindings do not enter this repository.
9. Public imports remain intentional; internal restructuring must not accidentally expand API promises.
10. Preserve compatibility with released consumers where reasonable.
11. Every claimed production guarantee must map to code + executable evidence; see `GUARANTEE_COVERAGE.md`.

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

The docs are durable project memory. Audit/status documents are deliberately first-class files rather than chat-only context.

## 4. Current realized Python ownership

The hardening branch already contains meaningful ownership packages including:

```text
src/fabric_data_framework/
├── contracts/
│   ├── dispatch.py
│   ├── execution_plan.py
│   └── capture_receipt.py
├── metadata/
│   └── capabilities.py
├── capture/
│   ├── full.py
│   └── snapshot.py
├── apply/
│   ├── replace.py
│   ├── scd1.py
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
├── extensions.py
├── config.py
├── control_plane.py
├── repository.py
├── watermark.py
├── bronze.py
├── scd2.py
├── delivery.py
├── deployment.py
└── cli.py
```

Some older modules remain top-level for compatibility/incremental refactoring. New capabilities should land in the final ownership package when that ownership is clear.

## 5. Target Python package shape

```text
src/fabric_data_framework/
├── __init__.py
├── contracts/
│   ├── config.py
│   ├── runtime.py
│   ├── audit.py
│   ├── infrastructure.py
│   ├── execution_plan.py
│   ├── capture_receipt.py
│   └── errors.py
├── metadata/
│   ├── loader.py
│   ├── validation.py
│   ├── effective_config.py
│   ├── compatibility.py
│   ├── hashing.py
│   └── capabilities.py
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
│   ├── upsert.py
│   ├── scd1.py
│   ├── scd2.py
│   └── snapshot_diff.py
├── data_plane/
│   ├── bronze.py
│   ├── staging.py
│   ├── publication.py
│   └── row_accounting.py
├── quality/
│   ├── rules.py
│   ├── quarantine.py
│   ├── reconciliation.py
│   └── schema_contracts.py
├── orchestration/
│   ├── planner.py
│   ├── dependencies.py
│   ├── concurrency.py
│   └── aggregation.py
├── execution/
│   ├── dataset_runner.py
│   ├── executor_registry.py
│   ├── step_runner.py
│   └── backends/
│       ├── base.py
│       └── in_process.py
├── recovery/
│   ├── retry.py
│   ├── backfill.py
│   ├── replay.py
│   ├── rebuild.py
│   ├── unknown_outcome.py
│   └── requests.py
├── state/
│   ├── watermark.py
│   ├── checkpoints.py
│   ├── leases.py
│   ├── idempotency.py
│   └── transitions.py
├── control_plane/
│   ├── schema.py
│   ├── repository.py
│   ├── migrations.py
│   └── queries.py
├── observability/
│   ├── audit.py
│   ├── metrics.py
│   ├── errors.py
│   └── status.py
├── connectors/
│   ├── base.py
│   ├── capabilities.py
│   └── registry.py
├── adapters/
│   ├── fabric/
│   │   ├── pipeline.py
│   │   ├── copy_job.py
│   │   ├── copy_activity.py
│   │   ├── dataflow_gen2.py
│   │   ├── spark_job.py
│   │   ├── notebook.py
│   │   ├── environment.py
│   │   ├── lakehouse.py
│   │   ├── warehouse.py
│   │   └── run_context.py
│   └── testing/
├── delivery/
│   ├── manifest.py
│   ├── bindings.py
│   ├── materialization.py
│   ├── deployment.py
│   └── provenance.py
├── extensions/
│   ├── contracts.py
│   ├── registry.py
│   └── entry_points.py
└── testing/
    ├── factories.py
    ├── assertions.py
    └── scenarios.py
```

The final split may vary slightly, but concern ownership must remain clear.

## 6. Ownership rules

### `contracts/`

Dependency-light stable value objects/interfaces such as execution plan, capture receipt, audit/runtime/binding contracts. No Fabric SDK/client dependencies.

### `metadata/`

Turns deployed/source-controlled metadata into immutable effective semantics. Owns validation, hashing, compatibility and engine/profile capability resolution.

`metadata/capabilities.py` currently owns conservative `(engine, capability_profile)` validation. Product/connector limitations belong here/adapters, not inside SCD1/SCD2 algorithms.

### `capture/`

Owns bounded source state/change acquisition semantics and source-boundary evidence. It does not decide target history/current-state behavior.

### `apply/`

Owns portable target semantics independent from the movement mechanism.

Current real examples:

```text
apply/replace.py
apply/scd1.py
apply/snapshot_diff.py
```

Future P0:

```text
apply/upsert.py
apply/append.py
```

### `data_plane/`

Owns normalized Bronze/staging/publication candidates/row accounting shared by strategies.

### `quality/`

Owns row/batch/schema quality, quarantine and reconciliation gates. Quality may block state/publication but must not secretly mutate checkpoints.

### `orchestration/`

Owns dataset selection, dependency readiness, concurrency and aggregate policy. It does not implement capture/apply algorithms.

### `execution/`

Owns lifecycle coordination and physical execution-unit/backend invocation for a compiled `ExecutionPlan`.

The next evolution must explicitly separate capture executor from apply executor/native-apply delegation.

### `recovery/`

Owns RETRY/BACKFILL/REPLAY/FULL_REBUILD and unknown-outcome behavior. This package is a P0 gap.

### `state/`

Owns checkpoint/watermark/lease/idempotency transition algorithms independently from persistence.

### `control_plane/`

Owns durable semantic snapshot/runtime evidence schema/repository/migrations/operator queries.

Current schema v2 is still implemented in compatibility top-level `control_plane.py`; physical package splitting can happen without changing the logical design.

### `connectors/` and `metadata/capabilities.py`

Own source/target physical capability facts such as bounded read, CDC/order, snapshot evidence, query pushdown, bulk movement and transactional publication. A connector does not define a new semantic capture/apply strategy.

### `adapters/fabric/`

Owns Microsoft Fabric-specific API/item/runtime translation only.

Important separate adapters are expected for:

```text
Pipeline
Copy Job
Copy Activity
Dataflow Gen2
Spark Job Definition / Notebook
Environment
Lakehouse / Warehouse
native run context
```

For example, `dataflow_gen2.py` will execute/correlate native capture and emit `CaptureReceipt`; it will not implement framework SCD1.

### `extensions/`

Owns bounded plugin interfaces/registry/entry-point discovery. Production metadata references logical names rather than arbitrary module/call strings.

### `delivery/`

Owns release manifest, environment bindings, metadata materialization, schema migration sequencing, deployment provenance/history and CLI orchestration.

### `testing/` / `adapters/testing/`

Deterministic reference utilities only; never evidence that a real production Fabric adapter exists.

## 7. Tests and certification target

Current suite remains intentionally simple/flat while ownership refactoring is active. Latest fully green implementation suite before final docs audit: **91 tests**.

Long-term organization:

```text
tests/
├── unit/
├── contract/
├── integration/
├── certification/
└── fixtures/
```

Certification should eventually be organized by guarantee rather than file chronology, including:

```text
FULL -> REPLACE no accidental wipe
WATERMARK same-timestamp/no-loss
Dataflow/native capture -> framework SCD1
SCD1 stale/equal-position/idempotency
SNAPSHOT delete guard
CDC offset/event identity
retry/backfill/replay/unknown outcome
multi-dataset failure isolation
Fabric adapter run correlation
```

`docs/GUARANTEE_COVERAGE.md` is the current human-readable guarantee catalog.

## 8. Compatibility policy

`v0.3.0` is published, so restructuring should not casually break effective public imports.

During the unreleased 0.4.0 cycle:

- preserve intentional exports from `fabric_data_framework.__init__`;
- use lightweight compatibility modules where justified;
- do not promise every internal path as public API;
- remove compatibility only through an explicit release/migration decision.

The goal is readable ownership without gratuitous downstream breakage.

## 9. Fabric item ownership

Reusable/reference Fabric items, when implemented, should live outside the Python source package, for example:

```text
fabric-items/
├── pipelines/
├── spark-job-definitions/
├── notebooks/
└── environments/
```

Domain-specific orchestration such as Customer batch pipelines belongs in the domain repository. This repository contains only reusable/reference Fabric items and adapter schemas.

## 10. What not to copy blindly from ingest-to-insight-batch

The transferable lesson from `ingest-to-insight-batch` is discoverable ownership, coherent project/package boundaries and executable scenarios.

Do not copy directory names merely to increase directory count. This repository has a narrower responsibility:

- reusable framework semantics here;
- business domain solution in `fabric-customer`;
- infrastructure estate management in `fabric-infra`.

## 11. Definition of done for structural hardening

The structural hardening is complete when:

- capture/apply/state/recovery/Fabric/delivery ownership is obvious from the tree;
- new capabilities land in correct final ownership rather than extending the old flat package;
- provider-neutral code does not depend on Fabric adapter details;
- native capability/profile facts do not leak into semantic algorithms;
- public compatibility is intentional;
- CI builds/tests on supported Python versions;
- guarantee coverage maps code to executable evidence;
- docs describe the actual tree/status rather than a future-only picture.
