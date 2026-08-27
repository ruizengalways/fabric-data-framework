# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

Phase 0 — Canonical architecture and repository boundaries: **COMPLETE**.

Phase 1 — Coherent framework foundation: **COMPLETE**.

Phase 2 — Customer WATERMARK -> Bronze -> SCD2 vertical slice: **READY TO START** after this Phase 1 PR is merged.

## Last completed step

Implemented the first runnable `fabric-data-framework` package foundation (`0.1.0`) following the accepted metadata-driven, failure-isolated and enterprise CI/CD architecture.

The implementation establishes strict immutable dataset metadata, audited operational override resolution, runtime/state correctness contracts, audit/quarantine/reconciliation contracts, a logical control-plane schema baseline, provider-neutral environment resolution and provider-neutral deployment/release provenance.

No actual WATERMARK extraction, SCD2/CDC mutation or Fabric deployment automation was implemented in this slice.

## Current implementation

### Package foundation

- Python package under `src/fabric_data_framework/`.
- `pyproject.toml` with Python `>=3.11`.
- Pydantic v2 typed contract dependency.
- SQLAlchemy 2.x Core dependency for logical relational control-plane schema definition.
- setuptools build backend and editable/wheel package support.

### Metadata/effective configuration

Implemented:

- `CaptureStrategy`: FULL, WATERMARK, CDC, MIRROR, STREAM, SNAPSHOT.
- `ApplyStrategy`: APPEND, REPLACE, UPSERT, SCD1, SCD2, SNAPSHOT_DIFF.
- run mode, dataset status, pipeline status and criticality enums.
- source/target/load/orchestration/DQ/reconciliation models.
- business/merge key validation.
- WATERMARK `(column, tie_breaker)` or overlap-window correctness requirement.
- immutable config hash.
- allow-listed `RuntimeOverride` fields only.
- override validity windows, audit identity, precedence and conflict detection.
- immutable `EffectiveDatasetConfig` with base/effective hash and applied override IDs.

Semantic fields such as merge key or apply strategy cannot be changed through `RuntimeOverride`.

### Infrastructure/runtime contracts

Implemented:

- logical `ResourceKind` / `LogicalResourceRef` / `ResolvedResource` models;
- provider-neutral `EnvironmentResolver` protocol;
- immutable `RuntimeContext` with pipeline/dataset/correlation IDs and release/config provenance;
- final pipeline status aggregation after terminal dataset outcomes;
- non-critical dataset failure -> `PARTIAL_SUCCESS` capability;
- critical dataset failure -> `FAILED` capability;
- `StateCommitGate` and `WatermarkTransition` preventing state advancement before target commit + required reconciliation or when quarantined.

### Audit/quarantine/reconciliation contracts

Implemented:

- pipeline/dataset/step audit models;
- exact source row accounting invariant: `rows_read = rows_accepted + rows_quarantined + rows_filtered`;
- target insert/update/delete mutation counts;
- row/batch quarantine lineage model;
- reconciliation metric/result model;
- validation preventing `PASS` reconciliation from hiding a failed metric.

### Control-plane schema foundation

Implemented a logical provider-neutral relational schema with 19 tables:

- `schema_migration_history`;
- `dataset`, `dataset_contract`, `load_policy`, `orchestration_policy`, `data_quality_policy`, `reconciliation_policy`;
- `runtime_override`;
- `watermark`, `dataset_state`, `dataset_lease`;
- `pipeline_run`, `dataset_run`, `step_run`;
- `reconciliation_result`, `quarantine_batch`, `schema_change`, `reprocess_request`, `deployment_history`.

The Phase 1 baseline has schema version `1` and an idempotent baseline initialization contract used in tests.

Definition rows and runtime-state rows are explicitly separated:

- deploy/materialize semantic definition rows per environment;
- never copy environment-local watermarks, leases, runs, runtime overrides, quarantine/reprocess state or deployment history from DEV to UAT/PROD.

### Enterprise deployment/provenance contracts

Implemented:

- environment-neutral `ReleaseBundleIdentity`;
- deterministic release hash;
- `DeploymentRequest` adding stage-specific logical binding profile without rebuilding the release;
- CI-provider and Fabric deployment-mechanism enums;
- `DeploymentProvenance` contract;
- `ControlPlaneDeploymentAdapter` protocol for later Fabric-native or external CD implementations;
- explicit control-plane record classification into release definition vs environment-local runtime state.

## Files/components implemented

- `pyproject.toml`
- `README.md`
- `src/fabric_data_framework/__init__.py`
- `src/fabric_data_framework/config.py`
- `src/fabric_data_framework/infrastructure.py`
- `src/fabric_data_framework/runtime.py`
- `src/fabric_data_framework/operations.py`
- `src/fabric_data_framework/control_plane.py`
- `src/fabric_data_framework/deployment.py`
- `tests/test_config.py`
- `tests/test_infrastructure.py`
- `tests/test_runtime.py`
- `tests/test_operations.py`
- `tests/test_control_plane.py`
- `tests/test_deployment.py`
- canonical docs under `docs/`.

## Tests/checks executed

Local isolated validation before writing the coherent Git commit:

1. `pytest -q` — **24 passed**.
2. `python -m compileall -q src tests` — PASS.
3. import/package contract check using `PYTHONPATH=src` — PASS.
4. editable installation using local build backend with `--no-build-isolation --no-deps` — PASS.
5. import from editable install — PASS (`fabric_data_framework.__version__ == 0.1.0`).
6. wheel build using `pip wheel --no-build-isolation --no-deps` — PASS.
7. wheel content inspection — PASS; package contains framework modules.
8. SQLAlchemy in-memory baseline migration — tested twice to prove idempotent schema initialization and schema version `1`.

The test suite covers:

- valid WATERMARK -> SCD2 metadata;
- missing tie-breaker/overlap correctness rejection;
- stateful apply merge-key requirement;
- semantic override rejection;
- operational override expiry/precedence/conflict;
- deterministic effective config hashes;
- critical/non-critical orchestration aggregation;
- final-state-only aggregation;
- watermark/state commit gating;
- no-silent-loss row accounting;
- reconciliation consistency;
- quarantine lineage validation;
- provider-neutral environment resolver protocol;
- control-plane table/classification invariants;
- same release identity across DEV and PROD with different binding profiles;
- deployment provenance contracts.

## Test results

**PASS — 24 unit/contract tests.**

Phase 1 foundation is runnable and package-buildable. No Fabric estate was mutated or required for these tests.

## Known limitations

- No actual source connector or WATERMARK extraction algorithm.
- No Bronze writer/normalizer implementation.
- No SCD1/SCD2/UPSERT/SNAPSHOT_DIFF/CDC mutation algorithm.
- No physical control-plane repository/store adapter yet; SQLAlchemy schema is the logical baseline contract.
- No dataset lease persistence implementation yet; only the schema and runtime correctness contract exist.
- No metadata dispatcher/Fabric Pipeline item yet.
- No published framework package/release automation yet.
- No GitHub Actions/Azure Pipelines workflow or Fabric Deployment Pipeline adapter yet.
- No Fabric runtime/integration test against an enterprise workspace yet.
- No Terraform implementation.

## Open issues/blockers

No architecture blocker for Phase 2.

The physical Fabric control-store choice remains deliberately deferred. Phase 2 can validate algorithms and control-plane contracts with small local/integration adapters before Phase 3 selects/deploys the enterprise Fabric delivery spine.

## Last known-good release / commit

Package source version: `0.1.0`.

No published immutable package release exists yet. The exact Git commit for this validated Phase 1 slice is the merge commit of the Phase 1 PR; Git history remains the authoritative commit provenance.

## Exact next implementation step

**Phase 2 — one coherent Customer WATERMARK -> Bronze -> SCD2 vertical slice across `fabric-data-framework` and `fabric-customer`.**

Complete substantially more than an algorithm stub:

### Framework work required for the slice

1. implement a small control-plane repository interface plus a local test adapter for deployed dataset metadata, watermark/state, dataset runs, reconciliation and quarantine lineage;
2. implement WATERMARK planning/filter semantics using `(modified_at, customer_id)` and explicit before/after positions;
3. implement normalized Bronze framework metadata for the captured rows;
4. implement reusable validation/quarantine execution primitives needed by the Customer fixture;
5. implement a deterministic SCD2 apply engine with business/merge keys, tracked-attribute change detection, one-current-row invariant and idempotent rerun behaviour;
6. implement reconciliation and atomic state-commit sequencing for the slice;
7. add integration tests for new, changed, unchanged, duplicate watermark timestamp, invalid/quarantined row, rerun/idempotency and failed reconciliation/no-watermark-advance.

### Customer work required for the slice

1. add the source-controlled `crm.customer` dataset definition using framework types/schema;
2. add tiny deterministic CRM fixtures and expected Silver SCD2 output;
3. add the Customer-specific mapping/DQ rule needed by the fixture without duplicating framework algorithms;
4. add cross-package integration tests pinned to the framework version/source under test;
5. update Customer Blueprint/CURRENT_STATUS.

Do **not** build the complete capture/apply strategy catalog, full Fabric CI/CD automation or Terraform in Phase 2. Prove one correct vertical slice first.
