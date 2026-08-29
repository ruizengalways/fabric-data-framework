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
7. `docs/EXECUTION_ENGINE_STRATEGY.md`
8. `docs/FABRIC_EXECUTION_MODEL.md`
9. `docs/CDC_DESIGN.md`
10. `docs/CONTROL_PLANE_DESIGN.md`
11. `docs/REPOSITORY_STRUCTURE.md`
12. `docs/CICD_DESIGN.md`
13. `docs/ECOSYSTEM_BLUEPRINT.md`

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
4. Source fidelity is an upper bound on truthful history fidelity; framework code must not invent missing changes.
5. Delete visibility is explicit and independent from “incremental” naming.
6. Bronze storage mode is selected from source fidelity/recovery requirements, not ideology.
7. Mature DE semantics have framework-owned portable implementations.
8. Native Fabric/provider features are capability-certified delegates.
9. One physical capture has one authoritative source-progress owner.
10. Native/external capture enters framework semantics through typed evidence.
11. Provider CDC normalizes before semantic apply.
12. Provider source progress and framework downstream apply progress are distinct.
13. Semantic definitions, onboarding truth claims, deployed metadata, overrides and runtime state are separate concerns.
14. Dataset is the default failure/retry boundary.
15. Quarantine, reconciliation, schema compatibility, temporal classification and recovery are first-class semantics.
16. Unknown target commit is reconciled before retry.
17. Retry/replay must preserve the frozen source boundary/set.
18. DEV/UAT/PROD promote immutable definitions/artifacts, never runtime rows.
19. Provider-neutral decisions remain testable outside Fabric.
20. Releases represent coherent product milestones, not commit cadence.

## Semantic axes

Coarse capture semantics:

```text
FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM
```

Source/onboarding patterns refine what those coarse strategies actually mean:

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

Apply engine is selected independently.

## Capture truth model

For every new source, determine before implementation:

```text
change fidelity
  CURRENT_STATE | NET_CHANGE | FULL_CHANGE | FULL_EVENT | SOURCE_DEFINED

delete visibility
  NONE | SNAPSHOT_INFERRED | TOMBSTONE | EXPLICIT_EVENT | SOURCE_DEFINED

Bronze mode
  OVERWRITE | MERGE | APPEND

SCD2/history fidelity
  NONE | OBSERVED_CHANGES | BATCH_GRAIN | FULL_EVENT | SNAPSHOT_GRAIN | SOURCE_DEFINED
```

This resolves several common false equivalences:

```text
incremental != delete-aware
CDC != full event history
SCD2 target != proof of full source history
file source != append semantics
API cursor != durable history by itself
```

`DatasetCaptureSelection` makes source truth reviewable in domain Git and `capture-onboarding-validate` can enforce it in CI.

## Current unreleased baseline

Public baseline: `v0.3.0`.

Production hardening PR #13 and capture/onboarding PR #14 are merged to `main`:

```text
9b2278822ff4c566051c69180c8ca63b021866e4
main Actions 33225627461
SUCCESS

4b20300c822e16a398342e0cc97da90ee51b035a
main Actions 33238779139
310 tests passed
```

The next portable hardening slice is durable target-operation idempotency / operation-journal semantics. `v0.4.0` remains unreleased.

The current reference/contract product slice includes:

- typed metadata/effective config/overrides;
- source-fidelity capture catalog and onboarding CI claims;
- capture/apply engine separation and capability resolution;
- composite WATERMARK + overlap;
- Bronze/DQ/quarantine/accounting;
- all six apply strategies including append-once APPEND;
- canonical CDC + CDC -> UPSERT/SCD1/SCD2;
- downstream CDC checkpointing + snapshot->CDC handoff;
- Debezium/Kafka and Delta CDF provider normalization;
- Fabric capture adapter contracts;
- retry/backoff/attempt/unknown-outcome recovery, quarantine REPLAY and FULL_REBUILD;
- typed schema contracts/evolution/evidence;
- replay-stable file/API source guards;
- shared source-order/event-time taxonomy;
- control-plane v3 and typed read-only operator snapshots/CLI;
- immutable delivery/release contracts.

No current hardening test is equivalent to an approved real Fabric/provider run.

## Apply architecture

Framework-owned reference behavior covers every canonical apply strategy. APPEND uses source-controlled append identity; REPLACE/SNAPSHOT_DIFF require isolated candidates and completeness guards; UPSERT/SCD1 share ordered current-state primitives; SCD2 preserves deterministic one-current-row history.

`CDC != SCD2` and `FULL != REPLACE` remain explicit invariants.

## Temporal architecture

Source order and event/valid time are independent clocks:

```text
source: STALE / EQUAL / NEWER
time:   EARLIER / EQUAL / LATER / UNKNOWN
```

The shared taxonomy is consumed by batch current-state and CDC paths. A newer source event with earlier valid time requires history rewrite and currently fails closed for SCD2 rather than silently changing historical intervals.

## Schema architecture

Typed source-controlled schema contracts are versioned/fingerprinted with explicit `EXACT`, `ADDITIVE_ONLY` and conservative `SAFE_EVOLUTION` compatibility. Physical engine auto-merge cannot redefine framework semantics.

## Source-boundary/replay architecture

Framework-owned acquisition freezes what is being read before relying on retry/replay:

```text
WATERMARK      bounded composite position/overlap
CDC            frozen upper checkpoint + completeness
FULL/SNAPSHOT  snapshot identity + completeness
files          frozen URI/version/readiness manifest
API            frozen logical window + cursor chain
Delta CDF      bounded commit-version checkpoint
```

## Provider architecture

Built-in/reference provider profiles now include:

```text
EXTERNAL_CDC / debezium_kafka_v1
SPARK        / delta_cdf_v1
```

Provider adapters normalize to canonical CDC rather than owning UPSERT/SCD1/SCD2 semantics.

## Recovery architecture

Implemented reference behavior includes bounded retry, attempt lineage, explicit reprocess intent and unknown-outcome tri-state reconciliation. Quarantine REPLAY and FULL_REBUILD are audited flows. Durable target-operation idempotency is the next portable recovery hardening item.

## Control-plane/operator architecture

Promotable definitions remain separate from environment-local runtime evidence. Schema version is v3. `DatasetCaptureSelection` is currently a Git/CI onboarding companion and does not create a control-plane v4 merely for classification.

The operator layer returns typed read-only snapshots rather than raw SQL rows and aggregates run/lineage, capture correlation, progress, reconciliation, quarantine, schema and active reprocess evidence.

## Many-table topology

Avoid both one handcrafted pipeline per table and one giant opaque source pipeline. Use metadata-selected execution groups based on source/gateway, engine/profile, schedule/SLA, volume, dependency, criticality, capacity and blast radius. Ordinary onboarding changes domain metadata/contracts, not framework algorithms.

## Current roadmap

1. durable target-operation idempotency/operation journal;
2. remaining native/provider downstream-failure recovery and live cursor/retention coordination;
3. selected/certified production control-plane store while preserving operator API;
4. real Fabric/Kafka transports + Fabric Pipeline backend;
5. approved DEV hybrid execution retaining provider/native correlation;
6. additional provider adapters only as supported scope requires;
7. exact-candidate audit/docs/CI and next immutable release decision.

## Release model

The same immutable framework artifact is promoted; environment bindings differ; runtime state never moves; domains exact-pin released versions. `v0.4.0` remains blocked until release claims match real integration evidence.

## Documentation obligation

Every substantive slice updates `CURRENT_STATUS.md`; source-pattern changes update `CAPTURE_PATTERN_CATALOG.md`; evidence/requirements changes update `PRODUCTION_REQUIREMENTS.md`, `GUARANTEE_COVERAGE.md`, `PRODUCTION_READINESS_AUDIT.md` and relevant design docs in the same coherent branch.
