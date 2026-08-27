# fabric-data-framework

Reusable, versioned Microsoft Fabric data-engineering runtime contracts for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns reusable metadata-driven behaviour: typed dataset configuration, audited operational overrides, runtime/control-plane contracts, failure isolation, audit, quarantine, reconciliation, recovery semantics, environment resolution and deployment provenance. Domain repositories consume a pinned framework version and keep business-specific transformations explicit.

## Current implementation

Phase 1 foundation is implemented as package version `0.1.0` and currently includes:

- strict immutable metadata models for source/target/load/orchestration/DQ/reconciliation policy;
- separate capture/apply strategy enums and watermark correctness validation;
- allow-listed, audited operational overrides and immutable `EffectiveDatasetConfig` hashing;
- provider-neutral logical Fabric resource resolution contracts;
- immutable runtime context, dataset/pipeline status aggregation and state/watermark commit gates;
- pipeline/dataset/step audit, quarantine and reconciliation contracts;
- a provider-neutral relational control-plane schema baseline with versioned idempotent initialization;
- explicit classification of deployable semantic-definition rows vs environment-local runtime state;
- provider-neutral release bundle and deployment provenance contracts for Fabric-native or external CI/CD.

Actual WATERMARK extraction, SCD2/CDC mutation logic, Fabric item deployment automation and Terraform are intentionally not implemented yet.

## Local development

```bash
python -m pip install -e '.[dev]'
pytest
```

## Canonical project memory

- `docs/ECOSYSTEM_BLUEPRINT.md` — cross-repository architecture and ownership model.
- `docs/PROJECT_BLUEPRINT.md` — framework architecture, implementation boundaries and roadmap.
- `docs/CONTROL_PLANE_DESIGN.md` — metadata-driven runtime/control-plane design.
- `docs/CICD_DESIGN.md` — enterprise Git/Fabric CI/CD and environment promotion design.
- `docs/CURRENT_STATUS.md` — exact implementation state and next coherent step.
- `docs/adr/` — accepted architecture decisions.
- `docs/runbooks/` — operational/recovery procedures as capabilities are implemented.
