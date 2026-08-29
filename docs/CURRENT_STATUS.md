# Current Status — fabric-data-framework

Last updated: 2026-08-29

## Current phase and release gate

`v0.3.0` remains the latest immutable public framework release. Source version `0.4.0` is an unreleased development line. **Do not publish v0.4.0 yet.**

Current release-significant merged baselines:

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

PR #19 -> fd6d5039a5852e32d823b178970816ff292472a2
provider-native downstream recovery contracts
PR Actions 33240884208
322 tests passed
Python 3.11 + 3.13 + wheel/static checks SUCCESS
```

The portable/reference operation-journal and provider-recovery contract gaps are now closed. `v0.4.0` remains unreleased because production control-plane certification, actual Fabric/Kafka transports, Fabric Pipeline execution and retained real DEV provider evidence are still missing.

The product target remains: after an enterprise installs the released wheel, routine datasets onboard through source-controlled metadata, source-fidelity classification, environment bindings, capability profiles and bounded logical-name extensions rather than edits to the framework.

## Latest validated implementation evidence

Current merged main baseline:

```text
fd6d5039a5852e32d823b178970816ff292472a2
PR #19 validation: GitHub Actions 33240884208
322 tests passed
Python 3.11 + 3.13 + wheel/static checks green
```

This baseline includes all prior capture/onboarding and target-operation durability work plus:

- Kafka/Debezium consumer-group cursor coordination around framework downstream checkpoints;
- explicit `MISSING`, `BEHIND`, `ALIGNED`, `AHEAD` external-cursor classification;
- deterministic seek/rewind plans derived from framework semantic progress, never from external group position;
- Kafka next-to-consume offsets calculated for provider commit only after downstream/framework checkpoint success;
- fail-closed Kafka retention-gap detection;
- Delta CDF bounded resume planning using provider earliest/latest available versions;
- fail-closed Delta CDF retention-gap detection when the next unapplied version is no longer available;
- provider-neutral `TargetCommitProbe` evidence contract;
- durable persistence of `COMMITTED`, `NOT_COMMITTED`, and `UNRESOLVED` target-probe results through the operation journal;
- provider probe exceptions converted to durable `UNRESOLVED/UNKNOWN`, never permission to retry blindly.

Canonical runbooks:

```text
docs/CAPTURE_PATTERN_CATALOG.md
docs/TARGET_OPERATION_IDEMPOTENCY.md
docs/PROVIDER_NATIVE_RECOVERY.md
```

All current hardening evidence remains `REFERENCE`, `CI PROVEN` or `ADAPTER CONTRACT`. No current hardening capability is yet `FABRIC PROVEN` through a retained approved real workspace/provider execution.

## Mainstream source/capture model

A new source is classified before choosing target apply semantics or a physical Fabric tool:

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

Executable `CapturePattern` values cover fourteen common Data Engineering families:

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

`DatasetCaptureSelection` records reviewable source truth separately from runtime `DatasetConfig`. Domain CI can enforce complete classification with:

```bash
fabric-framework capture-onboarding-validate \
  --config-dir <dataset-config-dir> \
  --selections <capture-selections.json> \
  --require-all
```

Checked-in executable examples live under `docs/examples/capture-patterns/` and are loaded by tests so documentation cannot silently drift from the typed contracts.

## Durable target-operation model

The framework separates a logical target mutation from a physical `dataset_run_id` attempt.

Semantic operation identity:

```text
dataset_id
operation_kind
target_reference
effective_config_hash
input_fingerprint
semantic_version
```

Runtime attempt IDs and timestamps are excluded.

Control-plane v4 persists:

```text
target_operation        current expected-version CAS state
target_operation_event  append-only lifecycle evidence
```

State/claim behavior:

```text
new               -> IN_PROGRESS / EXECUTE
IN_PROGRESS retry -> RECONCILE_REQUIRED
UNKNOWN retry     -> RECONCILE_REQUIRED
NOT_COMMITTED     -> CAS to IN_PROGRESS / EXECUTE
SUCCEEDED         -> terminal / SKIP_SUCCEEDED
```

This prevents blind re-execution after an ambiguous physical commit. The journal complements the existing `StateCommitGate`; watermark/checkpoint advancement still requires target commit and required reconciliation/data-quality proof.

## Provider-native downstream recovery model

### Kafka / Debezium

Framework `CDCCheckpoint` is the semantic source of truth. Kafka consumer-group committed offsets are transport cursors only.

If framework progress says offset `100` is applied, next required is `101` regardless of the group cursor:

```text
group next offset 110 -> AHEAD  -> seek back to 101
group next offset 95  -> BEHIND -> seek forward to 101
group next offset 101 -> ALIGNED -> no seek
missing group offset   -> MISSING -> initialize/seek to 101
```

Correct ordering:

```text
framework checkpoint
  -> provider earliest/latest + group cursor
  -> deterministic seek/read plan
  -> bounded consume
  -> target operation + reconciliation
  -> framework CDC checkpoint commit
  -> optional Kafka group cursor commit
```

A group-cursor commit failure cannot cause semantic loss because the next run realigns from framework state again.

If Kafka earliest available offset is beyond the next unapplied record, `DebeziumKafkaResumeGapError` fails closed and requires a governed rebuild/bootstrap recovery.

### Delta CDF

If framework commit version `100` is fully applied, next required is `101`. Provider earliest/latest availability evidence is checked before the bounded read.

```text
lower committed 100
earliest available 101 -> safe bounded resume

earliest available 102 -> retention gap -> fail closed
```

Empty row-change results alone do not prove a retention gap; provider version availability evidence determines whether the boundary is still readable.

### Target-native commit probe

`TargetCommitProbe` standardizes read-only provider evidence for an ambiguous target operation:

```text
COMMITTED     -> durable SUCCEEDED; never execute again
NOT_COMMITTED -> durable NOT_COMMITTED; next CAS claim may execute
UNRESOLVED    -> durable UNKNOWN; execution remains blocked
probe error   -> durable UNKNOWN; execution remains blocked
```

A resolved probe must retain a native operation ID or evidence reference. Real provider implementations still need to prove that their native statement/transaction/Delta marker can distinguish these outcomes.

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
- Debezium/Kafka and Delta CDF provider adapters/reference semantics;
- Fabric capture adapter contracts;
- replay-stable file manifests and API frozen windows;
- retry/attempt/unknown-outcome recovery, quarantine REPLAY and FULL_REBUILD;
- durable semantic target-operation idempotency + CAS operation journal;
- Kafka cursor coordination, Delta CDF retention-gap resume planning and target commit-probe contracts;
- schema contracts/evolution/evidence;
- shared source-order/event-time taxonomy;
- control-plane v4 + typed read-only operator API/CLI;
- immutable release/delivery contracts.

## Evidence boundary

Do not describe reference recovery contracts as live provider integration.

Still unproven in a real approved environment:

- live Kafka seek/commit and rebalance behavior;
- live Fabric Lakehouse CDF bounded reads and retention-gap drill;
- real Fabric Warehouse/Delta/Spark target commit probes;
- authentication/network/environment bindings;
- real native/provider run IDs and correlation;
- Fabric Pipeline orchestration backend;
- production control-plane persistence/concurrency behavior;
- retained approved DEV hybrid execution.

If provider evidence cannot distinguish committed from not committed, the result remains `UNRESOLVED`; the framework blocks rather than guesses.

## Exact next implementation sequence

1. define and certify the production control-plane repository contract while preserving current CAS, migration and operator semantics;
2. implement actual Fabric/Kafka transports and Fabric Pipeline backend behind existing adapter/execution contracts;
3. add provider-specific target commit probes and source-position discovery to the real transports;
4. prove approved DEV hybrid executions retaining framework/provider/native correlation and failure drills;
5. add further provider adapters only when supported product scope requires them;
6. exact-candidate audit/docs/CI and next immutable release decision.

## Repository boundary

- `fabric-data-framework`: reusable data-engineering semantics/runtime/package; current hardening work lives here.
- `fabric-customer`: business-domain metadata/config and bounded extensions; do not force it to consume unreleased `0.4.0` APIs.
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
docs/PROVIDER_NATIVE_RECOVERY.md
docs/EXECUTION_ENGINE_STRATEGY.md
docs/FABRIC_EXECUTION_MODEL.md
docs/CDC_DESIGN.md
docs/CONTROL_PLANE_DESIGN.md
docs/REPOSITORY_STRUCTURE.md
docs/CICD_DESIGN.md
docs/ECOSYSTEM_BLUEPRINT.md
```

If docs disagree with code/tests, inspect implementation and repair docs before continuing.
