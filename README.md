# fabric-data-framework

Reusable, versioned Microsoft Fabric Data Engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns mature reusable DE semantics and operational contracts. Domain repositories consume an immutable framework wheel and normally onboard datasets through source-controlled metadata, environment bindings and bounded logical-name extensions rather than framework edits.

## Release status

- Latest immutable public release: **v0.3.0**.
- Current source version: **0.4.0 development**.
- **Do not publish v0.4.0 yet**; the production-hardening milestone is still in progress.

Latest fully green implementation evidence before final documentation-audit commits:

```text
commit 82bf3d97e6e08e9620bacdd1de25a14a2f7d489c
GitHub Actions 33172961692
Python 3.11 / 3.13 + wheel: SUCCESS
91 tests passed
```

## Architecture in one diagram

```text
semantic metadata
      |
      v
capability resolver + immutable ExecutionPlan
      |
      +--> native capture/movement (Copy Job / Copy Activity / Dataflow / Mirroring)
      |        -> CaptureReceipt
      |
      +--> framework-controlled capture (Spark / SQL / custom adapter)
               |
               v
         Bronze / staging
               |
         DQ / transform
               |
     framework apply semantics
     REPLACE | SCD1 | SCD2 | SNAPSHOT_DIFF
     UPSERT/APPEND in progress
               |
       reconciliation/state/audit
```

Core rule: **framework-first semantics with stage-level native delegation**. Fabric-native features are first-class execution accelerators/adapters, but they are not assumed to provide every semantic guarantee.

For example, Dataflow Gen2 incremental bucket refresh may own capture progress while the framework owns final SCD1:

```text
Dataflow Gen2 incremental
  -> landing/staging
  -> CaptureReceipt
  -> framework SCD1
  -> reconciliation/audit
```

## Implemented reference capabilities

Current unreleased hardening branch includes:

- strict immutable dataset metadata and allow-listed runtime overrides;
- composite WATERMARK `(column, tie_breaker...)` + overlap semantics;
- normalized Bronze lineage envelope;
- row DQ/quarantine/accounting;
- deterministic SCD2;
- ordered/idempotent SCD1 with stale/equal-position/conflict handling;
- guarded FULL -> REPLACE;
- guarded SNAPSHOT -> SNAPSHOT_DIFF + delete guards;
- metadata-driven multi-dataset dispatcher/failure isolation;
- provider-neutral execution plans;
- capture/movement engine + progress-owner metadata;
- named engine capability profiles;
- Dataflow Gen2 incremental bucket capture profile feeding framework SCD1;
- typed `CaptureReceipt` for native/external handoff;
- logical-name extension registry;
- additive control-plane schema v2 (`execution_policy`, `ordering_policy`, `capture_receipt`);
- immutable release/config/deployment provenance and delivery CLI.

These are portable/reference guarantees. Real Fabric adapter/runtime evidence and enterprise IAM/network/governance evidence are tracked separately and are not implied by the test suite.

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

The delivery model separates immutable release definitions from environment-local bindings/runtime state. Credentials and physical Fabric IDs stay outside reusable semantic config.

## Canonical project memory

Read in this order when resuming in a new conversation:

1. `docs/ECOSYSTEM_BLUEPRINT.md`
2. `docs/PROJECT_BLUEPRINT.md`
3. `docs/PRODUCTION_REQUIREMENTS.md`
4. `docs/EXECUTION_ENGINE_STRATEGY.md`
5. `docs/FABRIC_EXECUTION_MODEL.md`
6. `docs/REPOSITORY_STRUCTURE.md`
7. `docs/CONTROL_PLANE_DESIGN.md`
8. `docs/CICD_DESIGN.md`
9. `docs/PRODUCTION_READINESS_AUDIT.md`
10. `docs/GUARANTEE_COVERAGE.md`
11. `docs/CURRENT_STATUS.md`
12. `docs/adr/`
13. `docs/runbooks/`

If documentation conflicts with code/tests, inspect the implementation and repair the docs before continuing.
