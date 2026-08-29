# fabric-data-framework

Reusable, versioned Microsoft Fabric Data Engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns mature reusable data-engineering semantics and operational contracts. Domain repositories consume an immutable framework wheel and normally onboard datasets through source-controlled metadata, environment bindings, capability profiles and bounded logical-name extensions rather than framework edits.

## Release status

- Latest immutable public release: **v0.3.0**.
- Current source version: **0.4.0 development**.
- **Do not publish v0.4.0 yet.** Production hardening and real Fabric evidence remain in progress.

## Architecture in one diagram

```text
semantic metadata
      |
      v
capability resolver + immutable ExecutionPlan
      |
      +--> native/external capture movement
      |      Copy Job / Copy Activity / Dataflow / CDC / Mirroring
      |             |
      |             v
      |       validated CaptureReceipt
      |
      +--> framework capture where appropriate
                    |
                    v
              Bronze / staging
                    |
              DQ / transform
                    |
       framework apply semantics
 REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF
                    |
            reconciliation/state
                    |
        watermark / cdc_checkpoint / audit
```

Core rule: **framework-first semantics with stage-level native delegation**. Fabric-native features are first-class accelerators/adapters only when their capability profile proves the requested stage contract.

## Implemented reference capabilities

Current unreleased hardening branch includes:

- strict immutable dataset metadata + allow-listed overrides;
- composite WATERMARK + overlap semantics;
- normalized Bronze lineage;
- row DQ/quarantine/accounting;
- guarded FULL -> REPLACE;
- guarded SNAPSHOT -> SNAPSHOT_DIFF;
- ordered/idempotent UPSERT and SCD1;
- deterministic SCD2;
- metadata-driven dispatcher/failure isolation;
- independent capture and apply engine planning;
- named engine capability profiles;
- Dataflow Gen2 incremental capture -> framework SCD1/UPSERT topology;
- typed `CaptureReceipt`;
- fail-closed Copy Job / Copy Activity / Dataflow Gen2 / Spark capture adapter contracts;
- conservative retry + unknown-target-commit reconciliation;
- RETRY/BACKFILL/REPLAY/FULL_REBUILD request and attempt-lineage contracts;
- canonical provider-neutral CDC event/order/dedupe/checkpoint contracts;
- CDC -> UPSERT/SCD1;
- CDC -> SCD2 with independent source-order and valid-time clocks;
- durable optimistic CDC downstream apply checkpoints;
- snapshot/bootstrap -> CDC no-gap/no-double-apply handoff;
- logical-name extension registry;
- additive control-plane schema v2;
- immutable release/config/deployment provenance and delivery CLI.

These are portable/reference guarantees. Real Fabric adapter/runtime evidence and enterprise IAM/network/governance evidence are tracked separately and are not implied by Python tests.

## Cheatsheet semantic alignment

The external data-engineering cheatsheet is treated as the acceptance specification for mainstream source/capture/Bronze/Silver combinations. A 2026-08-29 audit found that the framework's original fourteen `CapturePattern` values were **not the same taxonomy** as the cheatsheet's fourteen semantic rows because the legacy enum mixes source semantics, read strategy, provider technology and Bronze choice.

Canonical recovery/design checkpoint:

```text
docs/CHEATSHEET_PATTERN_ALIGNMENT.md
```

Pre-alignment assessment was:

```text
10 SUPPORTED
2 PARTIAL
2 GAP
```

PR #34 (`1c7d67bedd125f5fb5e983be791085fd1eaa9b0e`) added orthogonal semantic dimensions, all fourteen cheatsheet presets, and legacy `CapturePattern` projection into semantics + provider family. PR #35 (`bf215fcb3538f9806b4002d2f154dbd46ae19412`) added source-controlled semantic onboarding validation and the `capture-semantic-onboarding-validate` CLI.

At the **semantic-contract + onboarding-validation level**, all fourteen cheatsheet rows are now first-class expressible/tested presets. This does **not** mean every row is live-provider/Fabric proven. Provider/runtime evidence remains separate.

The next reusable semantic gap is full-baseline -> watermark bootstrap with explicit no-gap boundary evidence. The separate partial integration-evidence merge work remains on `codex/integration-evidence-merge` and must not be lost.

## CDC model

Canonical detail: `docs/CDC_DESIGN.md`.

```text
provider LSN/binlog/Kafka/native coordinate
    -> adapter normalization
    -> partition + integer position tuple
    -> CDCEvent
    -> bounded normalize/dedupe/order
    -> UPSERT / SCD1 / SCD2
    -> reconcile
    -> cdc_checkpoint
```

The framework fails closed when a provider has not supplied enough sequence information to prove deterministic order.

Snapshot bootstrap uses a source fence:

```text
retain CDC from S
S <= snapshot checkpoint B
complete snapshot consistent through B
CDC <= B -> ignore as snapshot-covered overlap
CDC >  B -> apply
```

## Local development

```bash
python -m pip install -e '.[dev]'
pytest
```

Latest coherent CDC proof before the docs-audit commit:

```text
465a2c1e9ddf25b0ace2293f578c2c5bb3a653ae
GitHub Actions 33216281126
Python 3.11 / 3.13 + wheel SUCCESS
171 tests passed
```

## Delivery CLI

```text
fabric-framework validate-tag ...
fabric-framework capture-semantic-onboarding-validate ...
fabric-framework control-plane-migrate ...
fabric-framework metadata-materialize ...
fabric-framework release-manifest ...
fabric-framework deployment-plan ...
fabric-framework deployment-record ...
```

Delivery separates immutable release definitions from environment-local bindings/runtime state. Credentials and physical Fabric IDs stay outside reusable semantic config.

## Canonical project memory

Read in this order when resuming in a new conversation:

1. `docs/ECOSYSTEM_BLUEPRINT.md`
2. `docs/PROJECT_BLUEPRINT.md`
3. `docs/PRODUCTION_REQUIREMENTS.md`
4. `docs/EXECUTION_ENGINE_STRATEGY.md`
5. `docs/FABRIC_EXECUTION_MODEL.md`
6. `docs/CDC_DESIGN.md`
7. `docs/CHEATSHEET_PATTERN_ALIGNMENT.md`
8. `docs/REPOSITORY_STRUCTURE.md`
9. `docs/CONTROL_PLANE_DESIGN.md`
10. `docs/CICD_DESIGN.md`
11. `docs/PRODUCTION_READINESS_AUDIT.md`
12. `docs/GUARANTEE_COVERAGE.md`
13. `docs/CURRENT_STATUS.md`
14. `docs/adr/`
15. `docs/runbooks/`

If documentation conflicts with code/tests, inspect implementation and repair documentation before continuing.
