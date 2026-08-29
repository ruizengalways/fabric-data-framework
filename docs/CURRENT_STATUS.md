# Current Status — fabric-data-framework

Last updated: 2026-08-29

## Current phase and release gate

`v0.3.0` remains the latest immutable public framework release. Source version `0.4.0` is an unreleased development line. **Do not publish v0.4.0 yet.**

The large production-hardening PR #13 was squash-merged to `main`:

```text
9b2278822ff4c566051c69180c8ca63b021866e4
main Actions 33225627461
SUCCESS
```

Active work is now:

```text
PR #14
feature/capture-pattern-catalog
```

The product target remains: after an enterprise installs the released wheel, routine datasets onboard through source-controlled metadata, source-fidelity classification, environment bindings, capability profiles and bounded logical-name extensions rather than edits to the framework.

## Latest validated implementation evidence

Current PR #14 baseline:

```text
78018b90c3dfb7f7ff2297aa173e9e8dfaee40e6
GitHub Actions 33237905150
310 tests passed
Python 3.11 + 3.13 + wheel/static checks green
```

This baseline includes:

- executable 14-pattern mainstream capture catalog;
- source-controlled `DatasetCaptureSelection` truth claims;
- `capture-onboarding-validate` CLI/CI gate;
- five complete executable onboarding examples;
- Delta Change Data Feed canonical CDC adapter;
- `SPARK/delta_cdf_v1` capability profile and provider registry integration.

Earlier merged hardening evidence includes:

```text
ae1eb99ab5fa9d7add5a62dda2d7448b6200d240
Actions 33225341709
268 tests passed
operator status API/CLI

1ee22d5828a5f53a3f9050722bdb5b7f7b28de43
Actions 33225064570
261 tests passed
shared source-order/event-time taxonomy

c326f062ad4e6be5185f17b9e6830946967361ab
Actions 33224558393
252 tests passed
replay-stable file/API capture guardrails
```

All new hardening evidence remains `REFERENCE`, `CI PROVEN` or `ADAPTER CONTRACT`. No current hardening capability is yet `FABRIC PROVEN` through a retained real workspace/provider execution.

## Mainstream capture/onboarding model

Canonical guide: `docs/CAPTURE_PATTERN_CATALOG.md`.

A new source is classified along independent axes before choosing a target apply strategy or physical Fabric tool:

```text
source/capture pattern
    -> what facts are actually available

change fidelity
    -> CURRENT_STATE / NET_CHANGE / FULL_CHANGE / FULL_EVENT / SOURCE_DEFINED

delete visibility
    -> NONE / SNAPSHOT_INFERRED / TOMBSTONE / EXPLICIT_EVENT / SOURCE_DEFINED

Bronze storage
    -> OVERWRITE / MERGE / APPEND

Silver apply
    -> APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF
```

Executable `CapturePattern` values now cover the fourteen common families requested for mainstream Data Engineering:

```text
FULL_SNAPSHOT
WATERMARK_INCREMENTAL
WATERMARK_LOOKBACK
WATERMARK_TOMBSTONE
CDC_NET_CURRENT
CDC_NET_OBSERVATION
CDC_FULL
TRANSACTION_LOG_CDC
DEBEZIUM_KAFKA
DELTA_CDF
EVENT_SOURCE
SNAPSHOT_DIFF
API_CURSOR_INCREMENTAL
FILE_INCREMENTAL
```

Key invariant:

> **Capture fidelity is an upper bound on history fidelity.**

Examples:

- watermark SCD2 is `OBSERVED_CHANGES`, not guaranteed full source history;
- net CDC SCD2 is `BATCH_GRAIN` because intermediate source changes were already collapsed;
- snapshot diff is `SNAPSHOT_GRAIN`;
- full ordered CDC/Debezium/Delta CDF can support `FULL_EVENT` captured history;
- API/file history is `SOURCE_DEFINED` until the source contract proves more.

## Source-controlled onboarding claim

`DatasetCaptureSelection` records reviewable source truth separately from the runtime DatasetConfig:

```text
dataset_id
capture_pattern
Bronze write mode
history claim
delete claim
rationale
known limitations
```

`validate_capture_selection()` refuses claims that contradict the canonical pattern. For example a `WATERMARK_LOOKBACK` source cannot claim `FULL_EVENT` history or `EXPLICIT_EVENT` delete visibility.

Domain CI can run:

```bash
fabric-framework capture-onboarding-validate \
  --config-dir <dataset-config-dir> \
  --selections <capture-selections.json> \
  --require-all
```

`--require-all` makes missing source classification a CI failure.

The onboarding selection is currently a source-controlled companion contract, not a new control-plane table. Control-plane schema therefore remains v3 in this slice.

## Executable examples

Canonical examples live under:

```text
docs/examples/capture-patterns/
```

Included complete examples:

```text
crm.customer             WATERMARK_LOOKBACK + SCD1
commerce.order_cdc       DEBEZIUM_KAFKA + SCD2
lakehouse.customer_cdf   DELTA_CDF + SCD2
partner.customer_api     API_CURSOR_INCREMENTAL + SCD1
vendor.account_files     FILE_INCREMENTAL + SNAPSHOT_DIFF
```

The test suite loads these exact files through `DatasetConfig`, `DatasetCaptureSelection` and `CapabilityRegistry`, so examples cannot silently drift from the code contract.

## Delta Change Data Feed status

`DELTA_CDF` is now a built-in provider/reference path rather than CUSTOM-only guidance:

```text
capture strategy: CDC
capture engine: SPARK
capability profile: delta_cdf_v1
progress owner: FRAMEWORK
apply engine: independently selected; SPARK/framework by default
```

`DeltaCDFRecord` maps Delta CDF `insert`, `delete`, `update_preimage`, `update_postimage` into canonical `CDCEvent` values. Update pre/post images for one key/commit are paired into one UPDATE. Source progress is bounded by Delta commit version and only advances after downstream target/reconciliation success.

Because Delta CDF does not expose a universal row sequence for arbitrary multiple logical changes of the same key inside one commit, the adapter fails closed when that order cannot be proven. Different keys in one commit receive a deterministic key-sorted row sequence for framework processing; metadata explicitly states that this is deterministic processing order, not invented business temporal order.

This is deterministic adapter/profile evidence only. Real Fabric Lakehouse CDF execution, authentication/environment binding and retention-gap drill are still integration work.

## Implemented development runtime

Merged/mainline hardening plus PR #14 now provides:

- strict immutable metadata/effective config and allow-listed runtime overrides;
- independent capture semantics, apply semantics, capture engine, apply engine and progress owner;
- immutable provider-neutral `ExecutionPlan` and named capability profiles;
- 14-pattern source-fidelity onboarding catalog + CI truth claims;
- composite WATERMARK + overlap;
- Bronze lineage, DQ/quarantine and no-silent-loss accounting;
- APPEND, REPLACE, UPSERT, SCD1, SCD2 and SNAPSHOT_DIFF;
- canonical CDC I/U/D ordering/dedupe/checkpoints;
- CDC -> UPSERT/SCD1/SCD2 and snapshot/bootstrap -> CDC handoff;
- Debezium/Kafka and Delta CDF provider adapters;
- Fabric capture adapter contracts;
- replay-stable file manifests and API frozen windows;
- retry/attempt/unknown-outcome recovery, quarantine REPLAY and FULL_REBUILD;
- schema contracts/evolution/evidence;
- shared source-order/event-time taxonomy;
- control-plane v3 + typed read-only operator API/CLI;
- immutable release/delivery contracts.

## Evidence boundary

Do not describe any of these as real provider integration merely because deterministic tests are green. Missing real proof still includes Fabric/Kafka transports, authentication/network bindings, Fabric Pipeline orchestration, live Kafka seek/commit, live Delta CDF bounded reads, native/provider run IDs and a retained approved DEV hybrid execution.

## Exact next implementation sequence

1. durable target-operation idempotency/operation journal with stable semantic operation key and persistent lifecycle/CAS evidence;
2. remaining native/provider downstream-failure recovery, including real Kafka cursor coordination and Delta CDF retention-gap recovery proof;
3. select/certify a production control-plane repository while preserving current operator contracts;
4. implement actual Fabric/Kafka transports and Fabric Pipeline backend;
5. prove approved DEV hybrid executions retaining provider/native correlation;
6. add further provider adapters only when supported product scope requires them;
7. exact-candidate audit/docs/CI and next immutable release decision.

## Durable project memory

New conversations should read in this order:

```text
docs/CURRENT_STATUS.md
docs/PRODUCTION_READINESS_AUDIT.md
docs/GUARANTEE_COVERAGE.md
docs/PROJECT_BLUEPRINT.md
docs/PRODUCTION_REQUIREMENTS.md
docs/CAPTURE_PATTERN_CATALOG.md
docs/EXECUTION_ENGINE_STRATEGY.md
docs/FABRIC_EXECUTION_MODEL.md
docs/CDC_DESIGN.md
docs/CONTROL_PLANE_DESIGN.md
docs/REPOSITORY_STRUCTURE.md
docs/CICD_DESIGN.md
docs/ECOSYSTEM_BLUEPRINT.md
```

If docs disagree with code/tests, inspect implementation and repair docs before continuing.
