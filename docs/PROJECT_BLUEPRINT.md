# fabric-data-framework — Project Blueprint

Status: Canonical
Last updated: 2026-08-29

## Goal

Build a production-grade reusable Microsoft Fabric Data Engineering runtime consumed by domain repositories through explicit immutable framework versions. The framework owns cross-domain correctness and operations; domains declare source truth, business semantics, mappings/rules and bounded extensions.

Primary product test:

> After an enterprise installs a released framework wheel, ordinary datasets onboard through source-controlled metadata, source/capture classification, environment bindings, capability profiles and bounded domain extensions rather than edits to `fabric-data-framework`.

## Canonical reading order

1. `docs/CURRENT_STATUS.md`
2. `docs/PRODUCTION_READINESS_AUDIT.md`
3. `docs/GUARANTEE_COVERAGE.md`
4. `docs/PROJECT_BLUEPRINT.md`
5. `docs/PRODUCTION_REQUIREMENTS.md`
6. `docs/CAPTURE_PATTERN_CATALOG.md`
7. `docs/TARGET_OPERATION_IDEMPOTENCY.md`
8. `docs/EXECUTION_ENGINE_STRATEGY.md`
9. `docs/FABRIC_EXECUTION_MODEL.md`
10. `docs/CDC_DESIGN.md`
11. `docs/CONTROL_PLANE_DESIGN.md`
12. `docs/REPOSITORY_STRUCTURE.md`
13. `docs/CICD_DESIGN.md`
14. `docs/ECOSYSTEM_BLUEPRINT.md`

GitHub docs are durable project memory. If docs disagree with code/tests, repair docs before further architecture work.

## Repository ownership

```text
fabric-infra          estate/capacity/workspace/RBAC/network/bindings
fabric-data-framework reusable semantic runtime/adapters/control-plane contracts
fabric-customer       deployable domain solution exact-pinning a released wheel
```

Dependency direction is `fabric-infra -> environment contract` and `fabric-data-framework -> immutable package -> fabric-customer`. Framework never depends on Customer. Share code, not runtime state.

## Design principles

1. Source/capture fidelity is classified before target apply or physical-tool selection.
2. Capture and apply semantics are independent.
3. Capture/movement and apply engines are independent.
4. Source fidelity is an upper bound on truthful history fidelity; missing source changes are never invented.
5. Delete visibility is explicit and independent from “incremental” naming.
6. Bronze storage follows source fidelity/recovery needs, not a universal write ideology.
7. Mature DE semantics have framework-owned portable implementations.
8. Native Fabric/provider features are capability-certified delegates.
9. One physical capture has one authoritative source-progress owner.
10. Native/external capture enters framework semantics through typed evidence.
11. Provider source progress, framework downstream progress and target-operation outcome are distinct state domains.
12. Dataset attempt identity is distinct from stable target-operation identity.
13. A retry of one frozen semantic mutation reuses one operation key across attempts/restarts.
14. Only a target operation proven `NOT_COMMITTED` may be blindly re-executed; uncertain outcome is reconciled first.
15. Semantic definitions, onboarding claims, deployed metadata, overrides and runtime state remain separated.
16. Dataset is the default failure/retry boundary.
17. Quarantine, reconciliation, schema compatibility, temporal classification and recovery are first-class semantics.
18. Retry/replay preserves the frozen source boundary/set.
19. DEV/UAT/PROD promote immutable definitions/artifacts, never runtime rows.
20. Provider-neutral decisions remain testable outside Fabric.
21. Releases represent coherent product milestones, not commit cadence.

## Semantic axes

Capture:

```text
FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM
```

Source/capture patterns:

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

Apply:

```text
APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF
```

Physical capture/movement engine:

```text
FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 |
SPARK | FABRIC_MIRRORING | EXTERNAL_CDC | SQL | CUSTOM
```

Apply engine is independently selected.

## Capture truth model

For every source determine:

```text
change fidelity
delete visibility
Bronze mode
replay identity
truthful SCD2/history fidelity
```

`DatasetCaptureSelection` makes these claims reviewable in domain Git and `capture-onboarding-validate` can enforce them in CI.

## Stable target-mutation model

For every physical target mutation determine a frozen mutation scope **before** writing the target.

```text
TargetOperationSpec
  dataset_id
  run_mode
  apply_strategy
  target_reference
  effective_config_hash
  mutation_scope_hash
        |
        v
stable operation_key
```

The key excludes attempt IDs. A retry creates a new `dataset_run_id` but keeps the same operation key if it is replaying the same frozen target mutation.

`mutation_scope_hash` is executor-owned and must hash the actual frozen semantic input: watermark window, CDC checkpoints + normalized batch, snapshot/candidate identity, append batch identities, frozen file/API evidence, replay scope, backfill range or rebuild candidate/state-reset evidence.

Lifecycle:

```text
PREPARED -> IN_PROGRESS
IN_PROGRESS -> COMMITTED | COMMIT_UNKNOWN | NOT_COMMITTED | FAILED
COMMIT_UNKNOWN -> COMMITTED | NOT_COMMITTED
NOT_COMMITTED -> IN_PROGRESS | FAILED
COMMITTED / FAILED terminal
```

`COMMITTED` converges without re-write. Persisted `IN_PROGRESS` is treated as uncertain after restart. Only `NOT_COMMITTED` is safe automatic retry.

Canonical guide: `docs/TARGET_OPERATION_IDEMPOTENCY.md`.

## Current unreleased baseline

Public baseline remains `v0.3.0`.

Merged mainline hardening:

```text
PR #13 -> 9b2278822ff4c566051c69180c8ca63b021866e4
PR #14 -> 4b20300c822e16a398342e0cc97da90ee51b035a
main Actions 33238779139 / 310 tests
PR #15 -> 07923edfa30fe0e5957d98a68a224579816c6b50
```

Active PR #16 implements target-operation idempotency. Coherent pre-docs evidence:

```text
dd148a0c8e329c19809986fa9a32ed7edbe5dbfb
Actions 33239441546
323 tests passed
```

`v0.4.0` remains unreleased.

## Current reference product slice

- typed metadata/effective config/overrides;
- source-fidelity capture catalog and onboarding CI claims;
- capture/apply engine separation and capability resolution;
- composite WATERMARK + overlap;
- Bronze/DQ/quarantine/accounting;
- all six apply strategies;
- canonical CDC + CDC -> UPSERT/SCD1/SCD2;
- downstream CDC checkpoint + snapshot/bootstrap handoff;
- Debezium/Kafka and Delta CDF normalization;
- Fabric capture adapter contracts;
- retry/attempt/unknown-outcome recovery, REPLAY and FULL_REBUILD;
- durable target-operation key/journal/CAS and retry convergence;
- typed schema contracts/evolution/evidence;
- replay-stable file/API source guards;
- shared source-order/event-time taxonomy;
- control-plane v4 and typed read-only operator snapshot/CLI;
- immutable delivery/release contracts.

No current deterministic test is equivalent to an approved real Fabric/provider target execution.

## State-domain separation

Keep these separate:

```text
provider/native source cursor
  -> physical source acquisition authority

watermark / cdc_checkpoint
  -> framework committed semantic source progress

target_operation
  -> physical semantic target-mutation outcome/idempotency

dataset_run / attempt lineage
  -> execution-attempt history
```

A target operation saying COMMITTED does not by itself authorize source state advancement; normal reconciliation/state gates remain required.

## Control-plane/operator architecture

Current development schema is v4. v4 adds environment-local `target_operation`. It is not promotable between environments.

The operator snapshot includes the latest target operation alongside run/lineage, capture correlation, source progress, reconciliation, quarantine, schema and reprocess evidence.

The relational implementation remains reference-level until a production repository is selected and concurrency/isolation behavior is re-certified.

## Current roadmap

1. merge/audit the target-operation journal slice;
2. complete native/provider downstream-failure recovery and live cursor/retention coordination;
3. select/certify production control-plane storage and re-prove CAS/transaction behavior;
4. implement real Fabric/Kafka/Delta transports + Fabric Pipeline backend;
5. integrate real target-side outcome evidence/reconciliation;
6. prove approved DEV hybrid execution retaining source/native/target correlation;
7. add additional provider adapters only as required;
8. exact-candidate audit/docs/CI and next immutable release decision.

## Release model

The same immutable artifact is promoted; environment bindings differ; runtime state never moves; domains exact-pin released versions. `v0.4.0` stays blocked until release claims match real integration evidence.

## Documentation obligation

Every substantive slice updates `CURRENT_STATUS.md`. Source-pattern changes update `CAPTURE_PATTERN_CATALOG.md`; target mutation/recovery changes update `TARGET_OPERATION_IDEMPOTENCY.md`; evidence/requirements changes update `PRODUCTION_REQUIREMENTS.md`, `GUARANTEE_COVERAGE.md`, `PRODUCTION_READINESS_AUDIT.md` and owning design docs in the same coherent branch.
