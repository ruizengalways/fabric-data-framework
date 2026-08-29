# Current Status — fabric-data-framework

Last updated: 2026-08-29

## Current phase and release gate

`v0.3.0` remains the latest immutable public framework release. Source version `0.4.0` is an unreleased development line. **Do not publish v0.4.0 yet.**

The current `main` now includes three release-significant hardening slices:

```text
PR #13 -> 9b2278822ff4c566051c69180c8ca63b021866e4
production-hardening architecture/runtime slice
main Actions 33225627461
SUCCESS

PR #14 -> 4b20300c822e16a398342e0cc97da90ee51b035a
mainstream capture/onboarding + Delta CDF reference slice
main Actions 33238779139
310 tests passed
Python 3.11 + 3.13 + wheel/static checks SUCCESS

PR #17 -> 83a27d9350a6018abc272e9afebdef5d660de519
durable target-operation idempotency / operation journal
PR Actions 33240559434
315 tests passed
Python 3.11 + 3.13 + wheel/static checks SUCCESS
```

The portable/reference target-operation journal gap is now closed. `v0.4.0` remains unreleased because real Fabric/provider commit-outcome reconciliation, remaining downstream-failure recovery, production control-plane selection and real Fabric/Kafka transports are not yet proven.

The product target remains: after an enterprise installs the released wheel, routine datasets onboard through source-controlled metadata, source-fidelity classification, environment bindings, capability profiles and bounded logical-name extensions rather than edits to the framework.

## Latest validated implementation evidence

Current merged main baseline:

```text
83a27d9350a6018abc272e9afebdef5d660de519
PR #17 validation: GitHub Actions 33240559434
315 tests passed
Python 3.11 + 3.13 + wheel/static checks green
```

This baseline includes all prior capture/onboarding hardening plus:

- stable semantic `TargetOperationIntent` identities independent of physical retry IDs;
- deterministic SHA-256 operation keys over dataset + apply meaning + target + effective config + frozen input fingerprint;
- control-plane schema v4;
- `target_operation` current compare-and-swap state;
- append-only `target_operation_event` lifecycle evidence;
- fail-closed retry semantics for re-entered `IN_PROGRESS` and `UNKNOWN` operations;
- retry reopening only after durable `NOT_COMMITTED` evidence;
- terminal `SUCCEEDED` / skip semantics;
- integration with the existing `UnknownOutcomeResolution` recovery contract;
- deterministic migration proof preserving the v2 -> v3 `append_identity` migration while adding v4 journal tables.

Canonical operation-journal runbook: `docs/TARGET_OPERATION_IDEMPOTENCY.md`.

All current hardening evidence remains `REFERENCE`, `CI PROVEN` or `ADAPTER CONTRACT`. No current hardening capability is yet `FABRIC PROVEN` through a retained approved real workspace/provider execution.

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

Executable `CapturePattern` values cover fourteen common mainstream Data Engineering families:

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

`DatasetCaptureSelection` records reviewable source truth separately from runtime `DatasetConfig`:

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

The onboarding selection remains a source-controlled companion contract rather than a control-plane table. Control-plane v4 was introduced specifically for runtime target-operation durability, not for capture-selection materialization.

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

`DELTA_CDF` is a built-in provider/reference path rather than CUSTOM-only guidance:

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

## Durable target-operation model

The framework now distinguishes a logical target mutation from a physical `dataset_run_id` attempt.

A semantic operation key is derived from:

```text
dataset_id
operation_kind
target_reference
effective_config_hash
input_fingerprint
semantic_version
```

Runtime attempt IDs and timestamps are intentionally excluded so a retry of the same logical mutation converges on the same operation key.

The durable state machine is:

```text
new -> IN_PROGRESS
IN_PROGRESS -> SUCCEEDED | UNKNOWN | NOT_COMMITTED
UNKNOWN -> SUCCEEDED | UNKNOWN | NOT_COMMITTED
NOT_COMMITTED -> IN_PROGRESS
SUCCEEDED -> terminal
```

Claim behavior is fail-closed:

```text
no record       -> EXECUTE
SUCCEEDED       -> SKIP_SUCCEEDED
IN_PROGRESS     -> RECONCILE_REQUIRED
UNKNOWN         -> RECONCILE_REQUIRED
NOT_COMMITTED   -> EXECUTE after CAS transition back to IN_PROGRESS
```

This prevents the classic ambiguous-commit failure where the physical target write succeeds but the framework times out before recording success. A re-entered `IN_PROGRESS` is treated as uncertain rather than automatically stolen/retried.

The journal complements, rather than replaces, the existing `StateCommitGate`: watermark/checkpoint advancement still requires target commit + required reconciliation/data-quality proof.

## Implemented development runtime

Current `main` provides:

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
- durable semantic target-operation idempotency + CAS operation journal;
- schema contracts/evolution/evidence;
- shared source-order/event-time taxonomy;
- control-plane v4 + typed read-only operator API/CLI;
- immutable release/delivery contracts.

## Evidence boundary

Do not describe deterministic operation-journal behavior as real provider commit proof. Missing real proof still includes Fabric/Kafka transports, authentication/network bindings, Fabric Pipeline orchestration, live Kafka seek/commit, live Delta CDF bounded reads/retention-gap behavior, native/provider run IDs, real target commit probes and a retained approved DEV hybrid execution.

If a provider/target adapter cannot distinguish committed from not committed after an ambiguous response, it must return/retain `UNRESOLVED`; the framework remains blocked rather than blindly retrying.

## Exact next implementation sequence

1. remaining native/provider downstream-failure recovery, including real Kafka cursor coordination, Delta CDF retention-gap recovery semantics/evidence and target-native ambiguous-commit reconciliation hooks;
2. select/certify a production control-plane repository while preserving current operator and CAS contracts;
3. implement actual Fabric/Kafka transports and Fabric Pipeline backend;
4. prove approved DEV hybrid executions retaining provider/native correlation;
5. add further provider adapters only when supported product scope requires them;
6. exact-candidate audit/docs/CI and next immutable release decision.

## Repository boundary

- `fabric-data-framework`: reusable data-engineering semantics/runtime/package; this is where PR #17 landed.
- `fabric-customer`: business-domain metadata/config and bounded extensions; it should not be forced to consume unreleased `0.4.0` APIs yet.
- `fabric-infra`: optional infrastructure/capacity/workspace lifecycle automation; it remains independent and is not required to continue framework development in an existing enterprise Fabric environment.

## Durable project memory

New conversations should read in this order:

```text
docs/CURRENT_STATUS.md
docs/PRODUCTION_READINESS_AUDIT.md
docs/GUARANTEE_COVERAGE.md
docs/PROJECT_BLUEPRINT.md
docs/PRODUCTION_REQUIREMENTS.md
docs/CAPTURE_PATTERN_CATALOG.md
docs/TARGET_OPERATION_IDEMPOTENCY.md
docs/EXECUTION_ENGINE_STRATEGY.md
docs/FABRIC_EXECUTION_MODEL.md
docs/CDC_DESIGN.md
docs/CONTROL_PLANE_DESIGN.md
docs/REPOSITORY_STRUCTURE.md
docs/CICD_DESIGN.md
docs/ECOSYSTEM_BLUEPRINT.md
```

If docs disagree with code/tests, inspect implementation and repair docs before continuing.
