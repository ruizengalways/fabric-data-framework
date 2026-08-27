# fabric-data-framework — Project Blueprint

Status: Canonical
Last updated: 2026-08-28

## 1. Goal

Build a production-grade, reusable Microsoft Fabric data-engineering runtime package that domain repositories consume through explicit immutable versions.

The framework standardizes stable cross-domain behaviour while domain-specific transformations remain explicit in domain repositories.

## 2. Non-goals

- Customer-specific business logic or canonical Customer transformations.
- Power BI dashboards, DAX, semantic models or visualization UX.
- Owning Fabric capacity, workspace RBAC, network architecture or tenant settings.
- A metadata product that attempts to encode genuinely different business logic as arbitrary configuration.
- A central cross-workspace runtime notebook called by every domain.
- One bespoke Fabric pipeline per source table.

## 3. Design principles

1. Share versioned code, not a shared runtime.
2. Configuration-driven where behaviour is stable; explicit code where logic differs.
3. Metadata-driven execution is a first-class framework capability.
4. Capture strategy and apply strategy are separate concepts.
5. Git semantic configuration is distinct from runtime state and operational overrides.
6. Resource identities are resolved through an infrastructure contract.
7. Stateful behaviour is defined through invariants, idempotency and explicit commit gates.
8. A dataset is the default execution/failure boundary; unrelated datasets continue where safe.
9. Quarantine, reconciliation and audit are part of execution semantics.
10. DEV/UAT/PROD promote the same immutable release identity while runtime state remains environment-local.
11. Recovery and deployment provenance are designed before operational scale.

## 4. Implemented Phase 1 package shape

The first coherent foundation slice intentionally uses a small flat module set rather than empty placeholder subpackages:

```text
fabric-data-framework/
  pyproject.toml
  src/fabric_data_framework/
    __init__.py
    config.py
    infrastructure.py
    runtime.py
    operations.py
    control_plane.py
    deployment.py
  tests/
    test_config.py
    test_infrastructure.py
    test_runtime.py
    test_operations.py
    test_control_plane.py
    test_deployment.py
  docs/
    ECOSYSTEM_BLUEPRINT.md
    PROJECT_BLUEPRINT.md
    CONTROL_PLANE_DESIGN.md
    CICD_DESIGN.md
    CURRENT_STATUS.md
    adr/
    runbooks/
```

Modules can split into subpackages when implementation volume justifies it; no empty architecture scaffolding is created merely to match a diagram.

## 5. Phase 1 foundation contracts

### Typed metadata

`DatasetConfig` composes:

- source and target logical identity;
- `CaptureStrategy` and `ApplyStrategy`;
- business and merge keys;
- WATERMARK column, tie-breaker and overlap-window semantics;
- event-time and tracked-column metadata;
- orchestration execution group, criticality, dependencies and operational defaults;
- DQ/quarantine policy reference;
- reconciliation policy and state-commit requirement.

Models are strict and immutable. Stateful apply strategies require merge keys. WATERMARK capture requires either a tie-breaker or positive overlap window so timestamp-only correctness is not silently accepted.

### Effective configuration

Runtime override fields are explicitly allow-listed. Current operational knobs include:

- enabled/disabled;
- priority;
- retry count;
- timeout;
- batch size;
- max concurrency;
- WATERMARK overlap window.

Semantic values such as merge keys, capture/apply strategy and schema contracts cannot be supplied through the runtime-override model.

`resolve_effective_config()` produces one immutable execution snapshot with:

- base semantic config hash;
- effective config hash;
- applied override IDs;
- deterministic precedence/conflict rules.

### Infrastructure resolution

`EnvironmentResolver` maps logical Fabric resource references to environment-specific resolved resources. Domain configuration does not contain physical workspace/Lakehouse/Warehouse IDs.

### Runtime correctness

`RuntimeContext` provides correlation/run identity and immutable release/config provenance.

Pipeline aggregation supports `SUCCESS`, `PARTIAL_SUCCESS` and `FAILED` after eligible dataset work reaches a terminal state. Independent non-critical failure therefore does not require immediate sibling cancellation.

`StateCommitGate` and `WatermarkTransition` encode the invariant that runtime state cannot advance before target commit and required reconciliation, and cannot advance for quarantined execution.

### Audit, quarantine and reconciliation

Contracts cover:

- pipeline, dataset and significant-step audit identity/status;
- exact row accounting (`read = accepted + quarantined + intentionally filtered`);
- target mutation counts;
- row/batch quarantine lineage;
- reconciliation metrics/results and state-blocking semantics.

### Control plane

Phase 1 defines a logical relational schema using SQLAlchemy Core. It is not yet a decision that Fabric Warehouse, Lakehouse/Delta or another store must be the final physical implementation.

The baseline contains 19 logical tables including:

```text
schema_migration_history

dataset
dataset_contract
load_policy
orchestration_policy
data_quality_policy
reconciliation_policy
runtime_override

watermark
dataset_state
dataset_lease
pipeline_run
dataset_run
step_run
reconciliation_result
quarantine_batch
schema_change
reprocess_request
deployment_history
```

The baseline schema initialization is versioned and idempotent for contract/integration testing.

Rows are explicitly classified into:

- **release definitions** — source-controlled semantic metadata materialized per environment;
- **environment-local runtime state** — watermarks, runs, overrides, quarantine/reprocess history, deployment history and similar state that must never be copied DEV -> UAT -> PROD as release data.

### Deployment contracts

`ReleaseBundleIdentity` is environment-neutral and includes the immutable domain Git SHA, framework version, config hash/schema version, control-plane schema version, Fabric item manifest version and build ID.

`DeploymentRequest` adds target environment/binding profile without changing the release identity.

`DeploymentProvenance` records CI provider and Fabric deployment mechanism. The runtime package therefore does not depend on GitHub Actions, Azure Pipelines or Fabric Deployment Pipelines specifically.

## 6. Metadata-driven execution target

A domain-level Fabric Pipeline remains an orchestration shell:

```text
lookup/select active datasets
  -> execution-group/dependency filtering
  -> bounded parallel dispatcher
  -> generic dataset executor(dataset_id, pipeline_run_id, run_mode)
  -> aggregate outcomes
```

Source/target/merge/watermark/DQ/reconciliation semantics are resolved from effective metadata rather than duplicated across table-specific pipeline activities.

## 7. Stateful execution target

The intended dataset executor flow remains:

```text
resolve effective config
  -> acquire lease
  -> create dataset_run
  -> capture
  -> Bronze normalize/write
  -> validate/DQ
  -> quarantine applicable bad data
  -> domain transform hook when required
  -> apply target strategy
  -> reconcile
  -> commit watermark/state only after required gates
  -> finalize audit
  -> release lease
```

Phase 1 implements the contracts around this flow, not the WATERMARK/SCD2/CDC data algorithms themselves.

## 8. Testing model

Phase 1 includes high-value unit/contract tests for:

- valid/invalid metadata combinations;
- semantic override rejection;
- runtime override expiry, precedence and conflict;
- deterministic base/effective config hashes;
- critical vs non-critical aggregate outcomes;
- state/watermark commit gates;
- no-silent-loss row accounting;
- quarantine/reconciliation model validity;
- provider-neutral environment resolution;
- idempotent versioned control-plane baseline creation;
- release-definition vs environment-local state classification;
- same release bundle identity across DEV/UAT/PROD.

Later phases add algorithmic, integration and deployed Fabric smoke tests.

## 9. Release and versioning model

The package follows semantic versioning. Domain repositories pin exact released versions. A framework release never silently changes a deployed domain; a domain takes an explicit dependency-upgrade PR.

The initial source package version is `0.1.0`. It is not yet a published production package release.

Pydantic v2 provides strict typed validation/immutability contracts and SQLAlchemy 2.x Core provides a provider-neutral relational schema definition for the Phase 1 baseline. Neither choice dictates the final Fabric control-store product.

## 10. Implementation cadence

Routine work inside accepted architecture proceeds as coherent testable capability slices. A slice is done when code, tests and recoverable docs are synchronized.

Stop for review only for a real architecture conflict, destructive/unsafe external action or material ambiguity—not after each small class/file.

## 11. Roadmap status

### Phase 0 — COMPLETE
Canonical architecture, repository boundaries, ADRs and recovery documentation.

### Phase 1 — COMPLETE: framework foundation
Implemented:

1. package/test structure and packaging metadata;
2. typed capture/apply/run/status/criticality contracts;
3. typed dataset/source/target/load/orchestration/DQ/reconciliation metadata;
4. allow-listed operational overrides and immutable effective-config hashing;
5. logical environment/resource resolution protocol;
6. immutable runtime context and correlation IDs;
7. audit/quarantine/reconciliation/state-commit contracts;
8. logical 19-table control-plane schema baseline and versioned idempotent initialization;
9. provider-neutral release/deployment/provenance contracts;
10. unit/contract test suite and package-build validation.

### Phase 2 — NEXT: Customer WATERMARK -> Bronze -> SCD2 vertical slice
Implement only the reusable algorithms and domain pieces required to prove one realistic end-to-end slice. The reference flow is:

```text
crm.customer metadata
  -> WATERMARK capture using modified_at + customer_id
  -> normalized Bronze metadata contract
  -> validation and row quarantine
  -> Customer mapping hook
  -> SCD2 apply
  -> reconciliation
  -> atomic state/watermark commit
```

Use tiny deterministic fixtures and exercise retry/idempotency/duplicate-watermark cases. Do not build the full strategy catalog yet.

### Phase 3 onward
Delivery spine, complete reusable strategy set, runtime hardening/multi-dataset orchestration, streaming and finally Terraform infrastructure automation follow the ecosystem roadmap.

## 12. Documentation obligations

Every meaningful implementation PR updates `docs/CURRENT_STATUS.md`. Architecture changes update this blueprint and/or add an ADR. Cross-repository architecture changes update the ecosystem blueprint.
