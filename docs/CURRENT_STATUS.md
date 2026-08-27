# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

Phase 0 — Canonical architecture and repository boundaries: **COMPLETE**.

## Last completed step

Established recoverable GitHub-based project memory for the ecosystem and this repository, including ownership boundaries, infrastructure abstraction, runtime/release principles and initial ADRs.

## Current implementation

Documentation-only foundation. No framework runtime package or Fabric execution code has been implemented yet. This is intentional: Phase 0 stops before SCD2, CDC, watermark execution or Terraform implementation.

## Important decisions made

- Three repositories have distinct Infrastructure Platform, Reusable Data Runtime and Customer Domain ownership.
- Domains consume a versioned framework package; they do not invoke one shared cross-workspace runtime.
- Capture strategy and apply strategy are independent configuration axes.
- Control-plane schema/migrations are a framework concern; physical hosting is an infrastructure concern.
- Framework/domain code resolves Fabric resources through an infrastructure contract and does not hard-code enterprise workspace/resource identities.
- Initial infrastructure implementation is deferred while using a pre-provisioned enterprise Fabric estate.
- Delivery is trunk-based and promotes the same immutable Git SHA through environments.

## Files/components implemented

- `README.md`
- `docs/ECOSYSTEM_BLUEPRINT.md`
- `docs/PROJECT_BLUEPRINT.md`
- `docs/CURRENT_STATUS.md`
- `docs/adr/0001-three-repository-ownership.md`
- `docs/adr/0002-capture-vs-apply-strategy.md`
- `docs/adr/0003-control-plane-ownership.md`
- `docs/runbooks/README.md`

## Tests executed

Phase 0 documentation validation only:

- inspected all three repositories before changes;
- confirmed each contained only its initial README/commit and no conflicting canonical architecture;
- reviewed repository boundaries and dependency direction for circular ownership;
- reviewed documented next-step sequencing to ensure no Phase 1+ implementation is claimed.

## Test results

PASS — Phase 0 documentation is internally consistent and intentionally contains no runtime implementation.

## Known limitations

- No Python package skeleton yet.
- No typed configuration model or infrastructure resolver interface yet.
- No control-plane migration implementation yet.
- No CI, package release, Fabric deployment or environment promotion automation yet.
- No Fabric runtime has been exercised.

## Open issues/blockers

No architecture blocker identified for starting Phase 1. Access details for a specific enterprise Fabric estate are intentionally not embedded in the framework.

## Last known-good release / commit

No framework package release exists yet. Phase 0 is documentation-only.

## Exact next implementation step

**Phase 1 / Step 1 — framework package and configuration foundation.**

Create the minimal Python package skeleton (`pyproject.toml`, `src/fabric_data_framework/`, `tests/`) and implement only:

1. typed `CaptureStrategy` and `ApplyStrategy` enums;
2. a validated `DatasetConfig` model covering dataset identity, business keys, capture/apply selection and optional watermark `(column, tie_breaker)` configuration;
3. a small typed infrastructure/environment contract interface that resolves logical Fabric resources without embedding workspace/Lakehouse/Warehouse IDs in framework code;
4. unit tests for valid/invalid configuration and the capture/apply separation.

Do **not** implement watermark execution, SCD2, CDC, Fabric deployment or Terraform in that step.
