# Repository Structure — fabric-data-framework

Status: Canonical target structure
Last updated: 2026-08-28

## 1. Why the current flat package is no longer enough

The existing package proved the first contracts quickly, but a flat module list now mixes fundamentally different concerns:

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

This is acceptable for an early library but weak for a production platform because a new engineer cannot infer ownership from the tree. Capture, apply, control, recovery, Fabric integration and delivery concerns will multiply as FULL/SNAPSHOT/CDC/schema/delete/recovery are added.

The target structure must make architectural ownership visible before opening a file.

## 2. Design rules

1. Organize by **stable production concern**, not by implementation chronology.
2. Keep capture and apply as separate axes.
3. Keep provider-neutral semantics separate from Fabric adapters.
4. Keep control-plane schema/state separate from business data-plane algorithms.
5. Keep delivery/release tooling separate from runtime execution.
6. Keep test/reference adapters separate from production adapters.
7. Avoid a directory for every class; directories represent meaningful ownership boundaries.
8. Domain code and physical company bindings do not enter this repository.
9. Public imports should remain intentional and small; internal module movement must not create accidental API promises.
10. Refactoring structure must preserve or explicitly migrate tests and downstream integration contracts.

## 3. Target top-level repository shape

```text
fabric-data-framework/
├── .github/
│   └── workflows/
├── docs/
│   ├── adr/
│   ├── runbooks/
│   ├── PRODUCTION_REQUIREMENTS.md
│   ├── FABRIC_EXECUTION_MODEL.md
│   ├── REPOSITORY_STRUCTURE.md
│   ├── CONTROL_PLANE_DESIGN.md
│   ├── CICD_DESIGN.md
│   ├── PROJECT_BLUEPRINT.md
│   ├── ECOSYSTEM_BLUEPRINT.md
│   └── CURRENT_STATUS.md
├── src/
│   └── fabric_data_framework/
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── certification/
│   └── fixtures/
├── examples/
│   └── metadata/
├── pyproject.toml
└── README.md
```

`examples/` is documentation/reference only; executable production guarantees belong to package code plus tests, not example scripts.

## 4. Target Python package shape

```text
src/fabric_data_framework/
├── __init__.py
│
├── contracts/
│   ├── config.py
│   ├── runtime.py
│   ├── audit.py
│   ├── infrastructure.py
│   ├── execution_plan.py
│   └── errors.py
│
├── metadata/
│   ├── loader.py
│   ├── validation.py
│   ├── effective_config.py
│   ├── compatibility.py
│   └── hashing.py
│
├── capture/
│   ├── base.py
│   ├── full.py
│   ├── watermark.py
│   ├── snapshot.py
│   ├── append_only.py
│   ├── cdc.py
│   ├── bootstrap_cdc.py
│   ├── mirror.py
│   └── stream.py
│
├── apply/
│   ├── base.py
│   ├── append.py
│   ├── replace.py
│   ├── upsert.py
│   ├── scd1.py
│   ├── scd2.py
│   └── snapshot_diff.py
│
├── data_plane/
│   ├── bronze.py
│   ├── staging.py
│   ├── publication.py
│   └── row_accounting.py
│
├── quality/
│   ├── rules.py
│   ├── quarantine.py
│   ├── reconciliation.py
│   └── schema_contracts.py
│
├── orchestration/
│   ├── planner.py
│   ├── dispatcher.py
│   ├── dependencies.py
│   ├── concurrency.py
│   └── aggregation.py
│
├── execution/
│   ├── dataset_runner.py
│   ├── executor_registry.py
│   ├── step_runner.py
│   └── backends/
│       ├── in_process.py
│       └── base.py
│
├── recovery/
│   ├── retry.py
│   ├── backfill.py
│   ├── replay.py
│   ├── rebuild.py
│   ├── unknown_outcome.py
│   └── requests.py
│
├── state/
│   ├── watermark.py
│   ├── checkpoints.py
│   ├── leases.py
│   ├── idempotency.py
│   └── transitions.py
│
├── control_plane/
│   ├── schema.py
│   ├── models.py
│   ├── repository.py
│   ├── migrations.py
│   └── queries.py
│
├── observability/
│   ├── audit.py
│   ├── events.py
│   ├── metrics.py
│   ├── errors.py
│   └── status.py
│
├── connectors/
│   ├── base.py
│   ├── capabilities.py
│   └── registry.py
│
├── adapters/
│   ├── fabric/
│   │   ├── pipeline.py
│   │   ├── spark_job.py
│   │   ├── notebook.py
│   │   ├── copy.py
│   │   ├── environment.py
│   │   ├── variable_library.py
│   │   ├── lakehouse.py
│   │   ├── warehouse.py
│   │   └── run_context.py
│   └── testing/
│       ├── control_plane.py
│       ├── target.py
│       └── source.py
│
├── delivery/
│   ├── manifest.py
│   ├── bindings.py
│   ├── materialization.py
│   ├── deployment.py
│   ├── provenance.py
│   └── cli.py
│
└── testing/
    ├── factories.py
    ├── assertions.py
    └── scenarios.py
```

This is a target ownership map, not permission to create empty files. Directories should appear as real implementations migrate into them.

## 5. Ownership by package

### `contracts/`

Stable typed contracts shared across runtime layers. This should be one of the smallest, most dependency-light areas.

Owns types such as:

- `DatasetConfig` / policy contracts;
- run/status enums;
- effective configuration identity;
- `ExecutionPlan` and `ExecutionStep` contracts;
- audit/result value objects;
- infrastructure/binding interfaces;
- shared framework exception taxonomy.

It should not import Fabric SDKs or concrete database clients.

### `metadata/`

Owns how source-controlled/deployed/runtime configuration becomes one immutable effective configuration.

Responsibilities:

- loading;
- validation;
- deterministic hashing;
- runtime override application;
- schema/version compatibility;
- strategy compatibility validation.

### `capture/`

Owns how a bounded source change/state set is acquired.

Capture code returns normalized records/batches plus source-boundary evidence. It does not decide SCD2/UPSERT/REPLACE semantics.

### `apply/`

Owns how normalized changes/candidates are materialized into target semantics.

Apply code does not own how source changes were captured.

### `data_plane/`

Owns common data movement inside a run after capture but outside target-specific business semantics:

- Bronze normalized envelope;
- stage/candidate locations;
- publication candidates;
- row accounting.

### `quality/`

Owns row/batch/schema quality, quarantine contracts and reconciliation gates.

Quality may block state progression but must not directly mutate checkpoints behind the state layer.

### `orchestration/`

Owns planning and dependency decisions, not capture/apply algorithms.

The key architectural evolution is to separate:

```text
planner/decision semantics
from
execution backend
```

The current dispatcher mixes these because `ThreadPoolExecutor` is embedded in the reference implementation. That is acceptable evidence for Phase 4 but not the final Fabric architecture.

### `execution/`

Owns execution of a selected `ExecutionPlan` and registration of physical executors/backends.

This is where dataset-run and step-run lifecycle is coordinated.

### `recovery/`

Owns operational re-execution semantics. Recovery is not a set of CLI flags sprinkled across normal runtime code.

### `state/`

Owns checkpoint/watermark/lease/idempotency transitions and state correctness.

This package is deliberately separate from control-plane persistence so algorithms can be tested without a specific database.

### `control_plane/`

Owns durable schema/repository/migration/query mechanisms for runtime metadata and evidence.

It must not become a second business data warehouse.

### `observability/`

Owns structured audit/error/metric/status representation and queries. It should make operators independent of notebook print statements.

### `connectors/`

Owns physical source/target capability contracts and registries.

Connector capability should be modeled around requirements such as:

- consistent/bounded read;
- snapshot support;
- ordered cursor/CDC;
- pushdown query;
- bulk copy;
- transaction/swap support;
- delete/tombstone support.

Do not create a new semantic strategy for each connector product.

### `adapters/fabric/`

Owns Microsoft Fabric-specific integration only.

It converts provider-neutral execution/deployment contracts into Fabric Pipeline, Spark Job Definition, Notebook, Copy, Environment, Variable Library, Lakehouse/Warehouse and run-context actions.

No Customer-specific IDs/names belong here.

### `delivery/`

Owns immutable release/deployment semantics and CLI tooling:

- release manifest;
- bindings;
- metadata materialization;
- control-plane migration sequencing;
- deployment plan/provenance/history.

### `testing/` and `adapters/testing/`

Own reusable deterministic fixtures/in-memory adapters needed to certify framework invariants. They are not production implementations.

## 6. Tests target shape

Current tests are a useful start but are too flat as the capability matrix grows.

Target:

```text
tests/
├── unit/
│   ├── capture/
│   ├── apply/
│   ├── quality/
│   ├── orchestration/
│   ├── recovery/
│   └── state/
├── contract/
│   ├── metadata/
│   ├── control_plane/
│   ├── connectors/
│   └── fabric_adapters/
├── integration/
│   ├── full_replace/
│   ├── watermark/
│   ├── snapshot_diff/
│   ├── cdc/
│   └── recovery/
├── certification/
│   ├── guarantee_full_replace.py
│   ├── guarantee_watermark_state.py
│   ├── guarantee_snapshot_delete_guard.py
│   ├── guarantee_cdc_offsets.py
│   └── guarantee_orchestration_isolation.py
└── fixtures/
```

Certification tests answer a stronger question than ordinary unit tests: which reusable production guarantee does this scenario prove?

## 7. Guarantee ownership

The repository should eventually maintain a machine-readable guarantee catalog similar in spirit to:

```yaml
guarantees:
  - id: full_replace_no_accidental_empty_wipe
    owner: apply/replace.py
    evidence:
      - tests/certification/...
  - id: watermark_same_timestamp_no_loss
    owner: capture/watermark.py
    evidence:
      - tests/certification/...
```

This prevents documentation claims from drifting away from implementation/tests.

A guarantee may be classified as:

- `production_invariant` — reusable framework behavior a domain may depend on;
- `fabric_adapter_invariant` — provider-specific integration behavior;
- `reference_technique` — useful demonstrated technique not yet promoted into generic production runtime ownership.

## 8. Migration from current flat package

Do not rewrite everything in one blind move. Use compatibility-preserving slices.

Recommended sequence:

### Slice A — contracts/control/orchestration

Move current:

```text
config.py
runtime.py
operations.py
infrastructure.py
control_plane.py
repository.py
dispatcher.py
```

into the target ownership packages while keeping intentional compatibility exports.

Split dispatcher decision logic from in-process scheduling.

### Slice B — current WATERMARK/SCD2 vertical slice

Move:

```text
watermark.py
bronze.py
quality.py
reconciliation.py
scd2.py
execution.py
```

into capture/data_plane/quality/apply/execution/state boundaries.

Keep behavior equivalent before adding new FULL/SNAPSHOT features.

### Slice C — delivery

Move:

```text
delivery.py
deployment.py
cli.py
```

under `delivery/`, preserving command-line entrypoints and public behavior.

### Slice D — new production capabilities

Add new code directly into the final ownership structure:

- FULL/REPLACE;
- SNAPSHOT_DIFF;
- recovery;
- schema/delete policies;
- connector capabilities;
- Fabric adapters.

## 9. Compatibility policy during restructure

Because `v0.3.0` is already published, avoid casually breaking imports that were part of the effective public surface.

During the next unreleased development cycle:

- preserve top-level package exports from `fabric_data_framework.__init__`;
- where reasonable, preserve old module import paths through lightweight compatibility modules;
- mark internal-only modules as such in documentation;
- remove compatibility paths only in an explicitly planned major-version break or after downstream migration evidence.

The goal is a readable tree without turning reorganization into gratuitous consumer breakage.

## 10. Fabric items are not stored under the reusable Python package

Framework-owned Fabric reference definitions, when added, should be separated from Python code, for example:

```text
fabric-items/
├── pipelines/
│   ├── pl_framework_dataset_execute/
│   └── pl_framework_reprocess/
├── spark-job-definitions/
│   └── sjd_framework_dataset_job/
├── notebooks/
│   ├── nb_framework_smoke/
│   └── nb_framework_diagnostics/
└── environments/
    └── reference-runtime/
```

However, domain orchestration items such as `pl_customer_batch` normally belong in the domain repository. The framework repository should contain only truly reusable/reference Fabric items and adapter schemas, not Customer-specific deployables.

Exact local Fabric Git representation must follow the currently supported Fabric item definition format when implementation begins.

## 11. Naming principles

Prefer semantic names:

```text
capture/full.py
apply/replace.py
recovery/replay.py
orchestration/planner.py
```

over generic utility buckets such as:

```text
utils.py
helpers.py
common.py
misc.py
```

A utility that cannot be given a clear ownership name may indicate the abstraction boundary is wrong.

## 12. What not to copy blindly from ingest-to-insight-batch

The other repository demonstrates strong ownership separation among projects/templates/packages/platform/scenarios/labs/tests. That principle should be retained.

Do not copy its exact directory names because this repository has a different boundary:

- it is a reusable Fabric framework package, not a combined local source simulator + project + platform reference;
- domain projects live in separate repositories;
- infrastructure lives in `fabric-infra`;
- Fabric-specific execution belongs under adapters, not the provider-neutral core.

The transferable lesson is **discoverable ownership and executable guarantees**, not directory count.

## 13. Definition of done for the structural refactor

The package restructure is complete when:

- a new engineer can locate capture/apply/state/recovery/Fabric/delivery code from the tree alone;
- no circular provider/core dependency is introduced;
- all existing 44 tests still pass or are intentionally migrated into stronger test classes;
- downstream Customer compatibility is preserved or explicitly migrated;
- CI builds the wheel on Python 3.11 and 3.13;
- docs and public imports describe the same architecture;
- new FULL/SNAPSHOT/recovery work lands directly in the final structure rather than extending the old flat package.