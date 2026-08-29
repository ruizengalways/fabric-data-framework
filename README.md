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

## Cheatsheet semantic alignment in progress

The external data-engineering cheatsheet is now treated as an acceptance specification for mainstream source/capture/Bronze/Silver combinations. A 2026-08-29 audit found that the framework's existing fourteen `CapturePattern` values are **not the same taxonomy** as the cheatsheet's fourteen semantic rows: the current enum mixes source semantics, read strategy, provider technology and Bronze choice.

Canonical recovery/design checkpoint:

```text
docs/CHEATSHEET_PATTERN_ALIGNMENT.md
```

Pre-alignment assessment of the cheatsheet fourteen rows:

```text
10 SUPPORTED
2 PARTIAL
2 GAP
```

Release-significant missing/partial combinations are recurring Full Snapshot -> Snapshot Bronze, Watermark + Lookback -> Raw Append Bronze, Watermark + Lookback + Soft Delete -> Raw Append Bronze, and Full Changes -> intentionally-lossy Current Bronze.

The active design direction is backward-compatible: introduce orthogonal source/change/read/delete/Bronze/history dimensions and project legacy `CapturePattern` values into that model rather than adding a combinatorial enum for every new combination. Do not claim the current “14-pattern catalog” exactly equals the cheatsheet acceptance table until the alignment work and executable fourteen-row tests are complete.

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
