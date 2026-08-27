# fabric-data-framework

Reusable, versioned Microsoft Fabric data-engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns reusable metadata-driven behaviour: typed dataset configuration, operational overrides, WATERMARK capture semantics, normalized Bronze envelopes, validation/quarantine primitives, SCD2, reconciliation/state gates, control-plane contracts, failure isolation, recovery semantics, environment resolution and deployment provenance. Domain repositories consume the framework and keep business-specific mappings/rules explicit.

## Current implementation

Source package version: **0.3.0**.

Implemented capabilities include:

- strict immutable dataset/source/target/load/orchestration/DQ/reconciliation metadata;
- composite WATERMARK planning with `(column, tie_breaker)` and optional overlap-window semantics;
- normalized `_framework_*` Bronze envelope;
- reusable row-validation and quarantine primitives;
- deterministic SCD2 insert/change/unchanged handling with one-current-row invariant and idempotent rerun;
- reconciliation and state/watermark commit gates;
- in-memory reference control-plane/target adapters and end-to-end tests;
- provider-neutral relational control-plane schema;
- immutable release/config-bundle identity and environment-local deployment bindings;
- idempotent semantic metadata materialization that preserves runtime state;
- deployment-history persistence;
- GitHub Actions CI and tag-triggered wheel release workflow.

The reference package still does **not** claim a real enterprise Fabric deployment until an authorized tenant identity and workspace bindings are exercised. Terraform and the remaining capture/apply strategy catalog are also intentionally later work.

## Local development

```bash
python -m pip install -e '.[dev]'
pytest
```

## Delivery CLI

```text
fabric-framework validate-tag ...
fabric-framework control-plane-migrate ...
fabric-framework metadata-materialize ...
fabric-framework release-manifest ...
fabric-framework deployment-plan ...
fabric-framework deployment-record ...
```

The CLI separates immutable release definitions from environment-local bindings and runtime state. GitHub Actions, Azure Pipelines or Fabric-native deployment automation can call the same contracts; credentials and physical Fabric IDs remain outside the package.

## Canonical project memory

- `docs/ECOSYSTEM_BLUEPRINT.md`
- `docs/PROJECT_BLUEPRINT.md`
- `docs/CONTROL_PLANE_DESIGN.md`
- `docs/CICD_DESIGN.md`
- `docs/CURRENT_STATUS.md`
- `docs/adr/`
- `docs/runbooks/`
