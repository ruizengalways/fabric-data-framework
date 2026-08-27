# fabric-data-framework

Reusable, versioned Microsoft Fabric data-engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns reusable metadata-driven behaviour: typed dataset configuration, operational overrides, WATERMARK capture semantics, normalized Bronze envelopes, validation/quarantine primitives, SCD2, reconciliation/state gates, control-plane contracts, failure isolation, recovery semantics, environment resolution and deployment provenance. Domain repositories consume the framework and keep business-specific mappings/rules explicit.

## Current implementation

Source package version: **0.2.0**.

Implemented through the first end-to-end reference slice:

- strict immutable dataset/source/target/load/orchestration/DQ/reconciliation metadata;
- composite WATERMARK planning with `(column, tie_breaker)` and optional overlap-window semantics;
- normalized `_framework_*` Bronze envelope;
- reusable row-validation and quarantine primitives;
- deterministic SCD2 insert/change/unchanged handling with one-current-row invariant and idempotent rerun;
- explicit rejection of late/out-of-order SCD2 events until a later policy is implemented;
- reconciliation and state/watermark commit gates;
- in-memory control-plane and SCD2 target adapters for deterministic integration tests;
- pipeline/dataset/step audit contracts and row accounting;
- provider-neutral logical control-plane schema and deployment/provenance contracts.

The reference package still does **not** implement CDC/snapshot-diff/full strategy breadth, physical Fabric control-store adapters, Fabric item deployment automation, enterprise CI workflows or Terraform.

## Local development

```bash
python -m pip install -e '.[dev]'
pytest
```

## Canonical project memory

- `docs/ECOSYSTEM_BLUEPRINT.md`
- `docs/PROJECT_BLUEPRINT.md`
- `docs/CONTROL_PLANE_DESIGN.md`
- `docs/CICD_DESIGN.md`
- `docs/CURRENT_STATUS.md`
- `docs/adr/`
- `docs/runbooks/`
