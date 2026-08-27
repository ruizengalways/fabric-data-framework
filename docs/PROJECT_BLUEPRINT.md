# fabric-data-framework — Project Blueprint

Status: Canonical
Last updated: 2026-08-28

## 1. Goal

Build a production-grade, reusable Microsoft Fabric data-engineering runtime package that domain repositories can consume through explicit, immutable versions.

The framework standardizes stable cross-domain behaviour while leaving domain-specific transformations explicit in domain repositories.

## 2. Non-goals

- Customer-specific business logic or canonical Customer transformations.
- Power BI dashboards, DAX, semantic models or visualization UX.
- Owning Fabric capacity, workspace RBAC, network architecture or tenant settings.
- A giant metadata product that hides genuinely different business logic.
- A central cross-workspace runtime notebook called by every domain.

## 3. Design principles

1. Share versioned code, not a shared runtime.
2. Configuration-driven where behaviour is stable; explicit code where logic differs.
3. Capture strategy and apply strategy are separate concepts.
4. Git configuration is distinct from runtime state.
5. Resource identities/names are resolved through an infrastructure contract.
6. Stateful behaviour is defined through invariants and idempotent semantics.
7. Recovery is designed before operational scale.

## 4. Repository structure

Phase 0 contains only canonical documentation. Phase 1 will add code incrementally; planned structure is intentionally small:

```text
fabric-data-framework/
  pyproject.toml                  # Phase 1
  src/fabric_data_framework/      # Phase 1
  tests/                          # Phase 1
  docs/
    ECOSYSTEM_BLUEPRINT.md
    PROJECT_BLUEPRINT.md
    CURRENT_STATUS.md
    adr/
    runbooks/
```

No placeholder strategy modules are created before they are needed.

## 5. Planned package boundaries

The initial package foundation will introduce only the boundaries needed for the first vertical slice:

- configuration models and enums;
- infrastructure/environment resolution contracts;
- runtime interfaces/context;
- structured logging conventions;
- control-plane model/schema definitions;
- testing helpers required by the first behaviours.

Strategy implementations (WATERMARK, SCD2, CDC, snapshot diff, etc.) are added in later coherent steps rather than generated upfront.

## 6. Configuration model

Stable metadata is expected to describe a dataset in terms such as:

```yaml
dataset: crm.customer
capture_strategy: WATERMARK
apply_strategy: SCD2
business_key:
  - customer_id
watermark:
  column: modified_at
  tie_breaker:
    - customer_id
tracked_columns:
  - name
  - address
  - segment
```

The configuration selects behaviour; the framework implements the behaviour. Complex source mappings and domain transformations remain explicit domain code.

## 7. Runtime architecture

Conceptual execution flow:

```text
Domain configuration
  -> resolve environment/infrastructure contract
  -> build immutable run context
  -> capture source changes
  -> normalize Bronze metadata contract
  -> apply selected target strategy
  -> reconcile / record runtime state
  -> advance state only after successful commit
```

Each domain executes its own runtime using a pinned framework package version.

## 8. Metadata and Bronze contract

Framework metadata will use a stable `_framework_*` namespace. Initial design targets ingestion timestamp, run identity, source system/object, normalized operation, source commit timestamp/sequence, snapshot ID and schema version. Source-provider details must not leak into downstream algorithms.

## 9. Control-plane model

The framework owns schema definitions/migrations for runtime state. Planned entities:

- `dataset`
- `dataset_contract`
- `load_policy`
- `watermark`
- `dataset_state`
- `pipeline_run`
- `dataset_run`
- `reconciliation_result`
- `schema_change`
- `reprocess_request`
- `deployment_history`

Physical hosting is supplied through the infrastructure contract and is not provisioned by this package.

## 10. Stateful correctness

Watermark design must support duplicate timestamps via a tie-breaker or an overlap-window/idempotent alternative. State advances only after success.

SCD2 must eventually define/test business keys, tracked-attribute hashing, effective ranges, current-row invariant, insert/update/delete, duplicates, late/out-of-order events, rerun and backfill.

Recovery modes are explicit: `NORMAL`, `RETRY`, `BACKFILL`, `REPLAY`, `FULL_REBUILD`.

## 11. Testing model

- Unit tests: pure reusable logic and configuration validation.
- Contract tests: framework metadata, environment contract, schema compatibility.
- Integration tests: representative small datasets and state transitions.
- Reconciliation tests: expected counts/hashes/state.
- Smoke tests: later, against a deployed Fabric environment.

Tests prioritize correctness over volume or benchmark performance.

## 12. Release and versioning model

The package follows semantic versioning. Domain repositories pin exact released versions; `@main` or direct mutable branch dependencies are not production dependencies.

Framework release and domain release lifecycles are independent. A framework release never silently changes a deployed domain; the domain must accept an explicit dependency-upgrade PR.

## 13. Implementation roadmap

### Phase 0 — COMPLETE
Canonical architecture, ownership model, ADRs and recoverable status documentation.

### Phase 1 — Framework foundation
1. Create `pyproject.toml`, `src/` and `tests/`.
2. Implement typed capture/apply enums and dataset configuration validation.
3. Implement an infrastructure/environment resolution interface without Fabric resource IDs hard-coded in framework code.
4. Define immutable runtime context and structured logging conventions.
5. Establish control-plane schema/model design and migrations approach.

### Phase 2 onward
Follow the ecosystem roadmap beginning with one Customer WATERMARK -> Bronze -> SCD2 -> Silver vertical slice, then delivery spine, remaining strategies, hardening, streaming and finally infrastructure automation.

## 14. Documentation obligations

Every meaningful implementation PR must update `docs/CURRENT_STATUS.md`; architecture changes must update this blueprint and/or add an ADR. The ecosystem blueprint is updated when cross-repository boundaries or shared architecture change.
