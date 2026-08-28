# fabric-data-framework

Reusable, versioned Microsoft Fabric Data Engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns mature reusable DE semantics and operational contracts. Domain repositories consume an immutable framework wheel and normally onboard datasets through source-controlled metadata, environment bindings and bounded logical-name extensions rather than framework edits.

## Release status

- Latest immutable public release: **v0.3.0**.
- Current source version: **0.4.0 development**.
- **Do not publish v0.4.0 yet**; the production-hardening milestone is still in progress.

Latest fully green hardening evidence before documentation synchronization:

```text
commit a5da06294dfba0c5ae756dcc1d8814931feebec7
GitHub Actions 33179754372
Python 3.11 / 3.13 + wheel: SUCCESS
139 tests passed
```

## Architecture in one diagram

```text
semantic metadata
      |
      v
capability resolver + immutable ExecutionPlan
      |
      +--> capture/movement executor
      |      Copy Job / Copy Activity / Dataflow / Spark / ...
      |            |
      |     native/provider evidence
      |            v
      |       CaptureReceipt
      |
      v
Bronze / normalize / DQ
      |
      v
independently selected apply executor
REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF
      |
      v
reconciliation / state / audit
      |
      +--> recovery core
           retry / attempt lineage / reprocess / unknown outcome
```

Core rule: **framework-first semantics with stage-level native delegation**. Native Fabric features are first-class stage executors, but they are not assumed to provide every semantic guarantee.

## Implemented reference capabilities

Current unreleased hardening branch includes:

- strict immutable dataset metadata and allow-listed runtime overrides;
- composite WATERMARK + overlap semantics;
- normalized Bronze lineage;
- row DQ/quarantine/accounting;
- deterministic SCD2;
- ordered/idempotent SCD1;
- ordered/idempotent UPSERT using a shared current-state primitive;
- guarded FULL -> REPLACE;
- guarded SNAPSHOT -> SNAPSHOT_DIFF + delete guards;
- metadata-driven multi-dataset dispatcher/failure isolation;
- independent capture/apply engine selection in immutable ExecutionPlan;
- named engine capability profiles;
- Dataflow Gen2 incremental capture profile feeding framework SCD1/UPSERT;
- typed CaptureReceipt;
- Fabric capture adapter contract layer for Copy Job, Copy Activity, Dataflow Gen2 and Spark;
- fail-closed provider run evidence validation;
- generic recovery failure classification/retry/backoff;
- immutable dataset attempt lineage;
- audited RETRY/BACKFILL/REPLAY/FULL_REBUILD request contracts;
- unknown target-commit reconciliation before retry;
- relational reprocess/attempt evidence in environment-local control-plane state;
- additive control-plane v2 development schema;
- immutable release/config/deployment provenance and delivery CLI.

These are portable/reference or adapter-contract guarantees. They do **not** imply that a real Fabric API/workspace/connection/capacity was exercised.

## Current next milestone

The next P0 correctness slice is CDC:

```text
canonical I/U/D event envelope
 -> event identity/order/dedup/conflict
 -> checkpoint commit gate
 -> CDC -> UPSERT/SCD1/SCD2
 -> snapshot/bootstrap -> CDC handoff
```

After CDC, complete strategy-specific replay/rebuild/native-progress recovery, schema evolution, APPEND/persistent operator surfaces and at least one real Fabric DEV hybrid execution before release decision.

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

Read in this order when resuming:

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

If documentation conflicts with code/tests, inspect implementation and repair the docs before continuing.
