# fabric-data-framework — Project Blueprint

Status: Canonical
Last updated: 2026-08-29

## 1. Goal

Build a production-grade reusable Microsoft Fabric Data Engineering runtime consumed by domain repositories through explicit immutable framework versions.

The framework standardizes mature cross-domain correctness and operational behavior. Domain repositories declare business semantics, mappings/rules and bounded extensions. The target is a Senior/Principal Data Engineering / Data Platform reference, not a notebook collection and not a BI demo.

Primary product test:

> After an enterprise installs a released framework wheel, ordinary datasets should be onboarded through metadata, environment bindings, capability profiles and bounded domain extensions rather than edits to `fabric-data-framework`.

## 2. Canonical reading order

For continuation/resume, read current evidence first:

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

GitHub docs are durable project memory. If docs disagree with code/tests, inspect implementation and repair docs before architecture work continues.

## 3. Repository ownership

```text
fabric-infra
  Fabric estate / capacity / workspace / RBAC / network / environment bindings

fabric-data-framework
  reusable semantic runtime + provider adapters + control-plane contracts

fabric-customer
  deployable domain solution exact-pinning a released framework wheel
```

Dependency direction:

```text
fabric-infra -> environment contract
fabric-data-framework -> immutable package -> fabric-customer
```

Framework never depends on Customer. Share code, not runtime state.

## 4. Core design principles

1. Capture semantics and apply semantics are independent.
2. Capture/movement engine and apply engine are independent.
3. Mature DE semantics have framework-owned portable implementations.
4. Native Fabric/provider features are capability-certified stage delegates.
5. One physical capture has one authoritative source-progress owner.
6. Native/external capture crosses into framework semantics through typed evidence.
7. Provider CDC formats normalize before semantic apply.
8. Provider/native source progress and framework downstream application progress are distinct.
9. Semantic definitions, deployed metadata, runtime overrides and runtime state are separate.
10. Dataset is the default failure/retry boundary.
11. Quarantine, reconciliation, schema compatibility and recovery are first-class semantics.
12. Unknown target commit is reconciled before retry.
13. Retry/replay must preserve source boundaries rather than silently reread a changed source window.
14. DEV/UAT/PROD promote immutable definitions/artifacts, never runtime rows.
15. Provider-neutral decisions remain testable outside Fabric.
16. Releases represent coherent product milestones, not commit cadence.

## 5. Semantic axes

Capture strategy:

```text
FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM
```

Apply strategy:

```text
APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF
```

Capture/movement engine:

```text
FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 |
SPARK | FABRIC_MIRRORING | EXTERNAL_CDC | SQL | CUSTOM
```

Apply engine is selected independently.

Source-family guardrails such as file manifests or API pagination are additional acquisition evidence; they do not become new apply semantics.

## 6. Current unreleased baseline

Public baseline: `v0.3.0`.

Current source: unreleased `0.4.0` on PR #13.

Latest validated code evidence:

```text
c326f062ad4e6be5185f17b9e6830946967361ab
Actions 33224558393
252 tests passed
```

The current branch proves at reference/contract level:

- strict typed metadata/effective config/overrides;
- capture/apply engine separation and capability resolution;
- composite WATERMARK + overlap;
- Bronze lineage and DQ/quarantine/accounting;
- all six canonical apply strategies including append-once APPEND;
- guarded FULL -> REPLACE and SNAPSHOT -> SNAPSHOT_DIFF;
- canonical CDC + CDC -> UPSERT/SCD1/SCD2;
- durable CDC downstream checkpoints;
- snapshot/bootstrap -> CDC fenced handoff;
- Debezium/Kafka normalization + retention-aware resume planning;
- Fabric capture adapter contracts;
- retry/attempt/unknown-outcome recovery;
- quarantine REPLAY and guarded FULL_REBUILD coordination;
- typed schema contract/evolution policy/evidence;
- replay-stable file-manifest and API frozen-window/pagination guardrails;
- control-plane v3 with real additive v2->v3 migration;
- immutable delivery/release contracts.

No current hardening test is equivalent to an approved real Fabric run.

## 7. Apply architecture

Framework-owned portable semantics now cover:

```text
APPEND
  source-controlled append_identity
  exact replay -> no-op
  same identity + changed business payload -> fail closed

REPLACE
  isolated candidate + completeness/empty/drop guards

UPSERT / SCD1
  shared ordered current-state primitive

SCD2
  deterministic history with one-current-row invariant

SNAPSHOT_DIFF
  complete snapshot + guarded insert/update/delete inference
```

`CDC != SCD2` and `FULL != REPLACE` remain explicit invariants.

## 8. Schema architecture

Typed source-controlled schema contracts are versioned and fingerprinted. Compatibility policy is explicit:

```text
EXACT
ADDITIVE_ONLY
SAFE_EVOLUTION
```

SAFE_EVOLUTION is conservative and recognizes only certified widening/relaxation. Physical Spark/Delta auto-merge cannot silently redefine framework compatibility.

Runtime observations are environment-local `schema_change` evidence; they do not mutate the deployed contract.

## 9. Source-boundary/replay architecture

Framework-owned acquisition must freeze what is being read before relying on retry/replay idempotency.

Current provider-neutral guards include:

```text
WATERMARK      bounded composite position/overlap
CDC            frozen upper checkpoint + completeness
FULL/SNAPSHOT  explicit completeness/snapshot identity
files          frozen manifest of URI/version/readiness evidence
API            frozen logical window + deterministic cursor chain
```

A retry resolving to a changed manifest/API window fails rather than silently processing a different source set.

## 10. CDC architecture

Provider-specific coordinates normalize into canonical source positions/events/checkpoints before target semantics. Current built-in reference provider is Debezium/Kafka using topic/partition/offset order.

For SCD2:

```text
source position -> event order
event_time      -> valid interval
```

Retroactive valid-time history correction remains intentionally unsupported and fails closed.

## 11. Recovery architecture

```text
RETRYABLE       -> bounded retry
NON_RETRYABLE   -> stop
UNKNOWN_OUTCOME -> reconcile first
```

Quarantine REPLAY and FULL_REBUILD are explicit audited flows. Remaining recovery gaps are primarily physical/provider specific rather than missing run-mode contracts.

## 12. Control plane

Current reference schema version: `3`.

Promotable definitions:

```text
dataset
dataset_contract
load_policy
ordering_policy
execution_policy
apply_execution_policy
orchestration_policy
data_quality_policy
reconciliation_policy
```

Environment-local state/evidence remains separate and is never promoted.

## 13. Many-table topology

Avoid both one handcrafted pipeline per table and one giant opaque source pipeline. Use metadata-selected execution groups based on operational boundaries such as source/gateway, engine/profile, schedule/SLA, volume, dependencies, criticality, capacity and blast radius.

Ordinary table onboarding changes domain metadata/contracts, not framework algorithms.

## 14. Current roadmap

1. shared cross-strategy temporal/late-event taxonomy;
2. remaining native/provider progress recovery + durable physical-target idempotency;
3. persistent control-plane repository/query/operator surface;
4. real Fabric/Kafka transports + Fabric Pipeline backend;
5. approved DEV hybrid execution retaining provider/native correlation;
6. additional provider adapters only as supported scope requires;
7. exact-candidate audit/docs/CI;
8. next immutable release decision.

## 15. Release model

- same immutable framework artifact is promoted;
- environment bindings differ;
- runtime state never moves between environments;
- domains exact-pin released framework versions;
- `v0.4.0` remains blocked until release claims match real integration evidence.

## 16. Documentation obligation

Every substantive slice updates `CURRENT_STATUS.md`; requirements/evidence changes update `PRODUCTION_REQUIREMENTS.md`, `GUARANTEE_COVERAGE.md`, `PRODUCTION_READINESS_AUDIT.md` and relevant design docs in the same coherent branch.
