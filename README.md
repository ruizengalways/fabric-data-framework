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

Current unreleased hardening line includes:

- strict immutable dataset metadata + allow-listed overrides;
- orthogonal cheatsheet-aligned source/change/read/delete/Bronze semantics;
- exact fourteen-row cheatsheet semantic acceptance presets and semantic onboarding CI gate;
- composite WATERMARK + overlap semantics;
- full-baseline -> WATERMARK no-gap bootstrap evidence contract;
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
- CDC -> UPSERT/SCD1/SCD2;
- durable optimistic CDC downstream apply checkpoints;
- snapshot/bootstrap -> CDC no-gap/no-double-apply handoff;
- logical-name extension registry;
- immutable release/config/deployment provenance and delivery CLI.

These are portable/reference guarantees. Real Fabric adapter/runtime evidence and enterprise IAM/network/governance evidence are tracked separately and are not implied by Python tests.

## Cheatsheet semantic alignment

The external data-engineering cheatsheet is treated as the acceptance specification for mainstream source/capture/Bronze/Silver combinations. A 2026-08-29 audit found that the original fourteen `CapturePattern` values were not the same taxonomy as the cheatsheet's fourteen semantic rows because the legacy enum mixed source semantics, read strategy, provider technology and Bronze choice.

Canonical recovery/design checkpoint:

```text
docs/CHEATSHEET_PATTERN_ALIGNMENT.md
```

Pre-alignment assessment was `10 supported / 2 partial / 2 gap`.

Merged alignment sequence:

```text
PR #34 -> 1c7d67bedd125f5fb5e983be791085fd1eaa9b0e
14 orthogonal cheatsheet semantic presets

PR #35 -> bf215fcb3538f9806b4002d2f154dbd46ae19412
semantic onboarding validation + CLI

PR #37 -> d69b2ff49f984331b6753bcd9274ea9a298ce798
full-baseline -> WATERMARK bootstrap contract
Actions 33253581049 / 441 tests / Python 3.11 + 3.13 + static + wheel SUCCESS
```

At the **semantic-contract + onboarding-validation level**, all fourteen cheatsheet rows are now first-class expressible/tested presets. This does not mean every row is live-provider/Fabric proven. Provider/runtime evidence remains separate.

The next active work is staged approved-environment evidence accumulation. The earlier partial implementation is preserved on `codex/integration-evidence-merge` at `d50769f3926e07d291c950199c1fa2e74b82c59c` and should be ported onto current `main`, tested, given a CLI, documented, and merged.

## CDC and bootstrap model

Canonical CDC detail: `docs/CDC_DESIGN.md`.

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

Snapshot -> CDC bootstrap uses a source fence:

```text
retain CDC from S
S <= snapshot checkpoint B
complete snapshot consistent through B
CDC <= B -> ignore as snapshot-covered overlap
CDC > B  -> apply
```

Full baseline -> WATERMARK bootstrap now similarly requires explicit evidence that the baseline is complete and consistent through exact boundary W, ordering is deterministic, and post-W changes remain visible. A generic `updated_at` column is not automatically sufficient proof.

## Local development

```bash
python -m pip install -e '.[dev]'
pytest
```

## Delivery CLI

```text
fabric-framework validate-tag ...
fabric-framework capture-semantic-onboarding-validate ...
fabric-framework integration-evidence-validate ...
fabric-framework integration-run-preflight ...
fabric-framework integration-item-smoke-run ...
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
