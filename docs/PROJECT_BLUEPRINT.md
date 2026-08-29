# fabric-data-framework — Project Blueprint

Status: Canonical
Last updated: 2026-08-29

## Goal

Build a production-grade reusable Microsoft Fabric Data Engineering runtime consumed by domain repositories through explicit immutable framework versions. The framework owns cross-domain correctness and operations; domains declare business semantics, mappings/rules and bounded extensions.

Primary product test:

> After an enterprise installs a released framework wheel, ordinary datasets onboard through metadata, environment bindings, capability profiles and bounded domain extensions rather than edits to `fabric-data-framework`.

## Canonical reading order

1. `docs/CURRENT_STATUS.md`
2. `docs/PRODUCTION_READINESS_AUDIT.md`
3. `docs/GUARANTEE_COVERAGE.md`
4. `docs/PROJECT_BLUEPRINT.md`
5. `docs/PRODUCTION_REQUIREMENTS.md`
6. `docs/EXECUTION_ENGINE_STRATEGY.md`
7. `docs/FABRIC_EXECUTION_MODEL.md`
8. `docs/CDC_DESIGN.md`
9. `docs/CONTROL_PLANE_DESIGN.md`
10. `docs/REPOSITORY_STRUCTURE.md`
11. `docs/CICD_DESIGN.md`
12. `docs/ECOSYSTEM_BLUEPRINT.md`

GitHub docs are durable project memory. If docs disagree with code/tests, repair docs before further architecture work.

## Repository ownership

```text
fabric-infra          estate/capacity/workspace/RBAC/network/bindings
fabric-data-framework reusable semantic runtime/adapters/control-plane contracts
fabric-customer       deployable domain solution exact-pinning a released wheel
```

Dependency direction is `fabric-infra -> environment contract` and `fabric-data-framework -> immutable package -> fabric-customer`. Framework never depends on Customer. Share code, not runtime state.

## Design principles

1. Capture and apply semantics are independent.
2. Capture/movement and apply engines are independent.
3. Mature DE semantics have framework-owned portable implementations.
4. Native Fabric/provider features are capability-certified delegates.
5. One physical capture has one authoritative source-progress owner.
6. Native/external capture enters framework semantics through typed evidence.
7. Provider CDC normalizes before semantic apply.
8. Provider source progress and framework downstream apply progress are distinct.
9. Semantic definitions, deployed metadata, overrides and runtime state are separate.
10. Dataset is the default failure/retry boundary.
11. Quarantine, reconciliation, schema compatibility, temporal classification and recovery are first-class semantics.
12. Unknown target commit is reconciled before retry.
13. Retry/replay preserves frozen source boundary/set.
14. DEV/UAT/PROD promote immutable definitions/artifacts, never runtime rows.
15. Provider-neutral decisions remain testable outside Fabric.
16. Releases represent coherent product milestones, not commit cadence.

## Semantic axes

Capture:

```text
FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM
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

Apply engine is selected independently. File manifests/API pagination are source-family guardrail evidence, not new apply semantics.

## Current unreleased baseline

Public baseline: `v0.3.0`.

Current source: unreleased `0.4.0` on PR #13.

Latest validated code evidence:

```text
ae1eb99ab5fa9d7add5a62dda2d7448b6200d240
Actions 33225341709
268 tests passed
```

Current reference/contract product slice includes:

- typed metadata/effective config/overrides;
- capture/apply engine separation and capability resolution;
- composite WATERMARK + overlap;
- Bronze/DQ/quarantine/accounting;
- all six apply strategies including append-once APPEND;
- canonical CDC + CDC -> UPSERT/SCD1/SCD2;
- downstream CDC checkpointing + snapshot->CDC handoff;
- Debezium/Kafka normalization/resume planning;
- Fabric capture adapter contracts;
- retry/attempt/unknown-outcome recovery, quarantine REPLAY and FULL_REBUILD;
- typed schema contracts/evolution/evidence;
- replay-stable file/API source guards;
- shared source-order/event-time taxonomy wired into apply paths;
- control-plane v3 with real additive v2->v3 migration;
- typed read-only operator snapshots and `control-plane-status` CLI;
- immutable delivery/release contracts.

No current hardening test is equivalent to an approved real Fabric run.

## Apply architecture

Framework-owned reference behavior now covers every canonical apply strategy. APPEND uses source-controlled append identity; REPLACE/SNAPSHOT_DIFF require isolated candidates and completeness guards; UPSERT/SCD1 share ordered current-state primitives; SCD2 preserves deterministic one-current-row history.

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
```

## Recovery architecture

Implemented reference behavior includes bounded retry, attempt lineage, explicit reprocess intent and unknown-outcome tri-state reconciliation. Quarantine REPLAY and FULL_REBUILD are audited flows. Durable target-operation idempotency is the next portable recovery hardening item.

## Control-plane/operator architecture

Promotable definitions remain separate from environment-local runtime evidence. Schema version is currently v3.

The operator layer returns typed read-only snapshots rather than raw SQL rows. It aggregates latest run/lineage, capture/provider correlation, WATERMARK/CDC progress, reconciliation, quarantine backlog, schema observation and active reprocess requests. The same surface is exposed as JSON through `fabric-framework control-plane-status`.

This preserves an API boundary that can move above a future approved production repository implementation.

## Many-table topology

Avoid both one handcrafted pipeline per table and one giant opaque source pipeline. Use metadata-selected execution groups based on source/gateway, engine/profile, schedule/SLA, volume, dependency, criticality, capacity and blast radius. Ordinary onboarding changes domain metadata/contracts, not framework algorithms.

## Current roadmap

1. durable target-operation idempotency/operation journal;
2. remaining native/provider downstream-failure recovery and real Kafka cursor coordination;
3. selected/certified production control-plane store while preserving the operator API;
4. real Fabric/Kafka transports + Fabric Pipeline backend;
5. approved DEV hybrid execution retaining provider/native correlation;
6. additional provider adapters only as supported scope requires;
7. exact-candidate audit/docs/CI and next immutable release decision.

## Release model

The same immutable framework artifact is promoted; environment bindings differ; runtime state never moves; domains exact-pin released versions. `v0.4.0` remains blocked until release claims match real integration evidence.

## Documentation obligation

Every substantive slice updates `CURRENT_STATUS.md`; evidence/requirements changes update `PRODUCTION_REQUIREMENTS.md`, `GUARANTEE_COVERAGE.md`, `PRODUCTION_READINESS_AUDIT.md` and relevant design docs in the same coherent branch.
