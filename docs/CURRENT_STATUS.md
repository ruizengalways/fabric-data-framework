# Current Status — fabric-data-framework

Last updated: 2026-08-29

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine: **COMPLETE AND RELEASED AS `v0.3.0`**.
- Phase 4 — metadata dispatcher/failure isolation: **MERGED TO `main` AS UNRELEASED 0.4.0 DEVELOPMENT SOURCE**.
- Current milestone — **PRODUCTION FRAMEWORK HARDENING; RELEASE PAUSED UNTIL REAL FABRIC/PROVIDER EVIDENCE AND REMAINING OPERATIONAL GAPS ARE CLOSED OR EXPLICITLY BOUNDED**.

## Release gate

Do **not** publish `v0.4.0` yet.

Latest immutable public framework release remains `v0.3.0`. Source version `0.4.0` is an unreleased development line.

Active work:

```text
PR #13
architecture/production-framework-blueprint
```

The product target is a wheel an enterprise domain installs and normally uses through source-controlled metadata, environment bindings, capability profiles and bounded logical-name extensions. Routine onboarding must not require framework edits.

## Latest coherent implementation evidence

Latest validated code baseline:

```text
1ee22d5828a5f53a3f9050722bdb5b7f7b28de43
GitHub Actions 33225064570
261 tests passed
shared source-order/event-time taxonomy wired through batch current-state, CDC current-state and CDC-SCD2
```

Recent hardening sequence:

```text
c326f062ad4e6be5185f17b9e6830946967361ab
Actions 33224558393
252 tests passed
replay-stable file manifest + API frozen-window/pagination guardrails

6eb4ff275ed1aad9092f60f098d2a9272fd06779
Actions 33223276476
231 tests passed
typed schema contract/evolution policy + schema-change evidence

2466d6f254b37a1d79a716e8dd95c5dd16d21cf4
Actions 33222949040
215 tests passed
APPEND identity/replay semantics + control-plane v3 migration proof

f3521aa79b2cc66865d46a30e119a7dc4784d698
Actions 33220690474
197 tests passed
guarded FULL_REBUILD target/state cutover

6b4a3cd2ddecd818d22fabe22988c043cdcff260
Actions 33220487307
190 tests passed
fail-closed quarantine REPLAY coordination

ecdca38099a4f21c6f40701dc14889b464c20608
Actions 33219783325
183 tests passed
Debezium/Kafka capability profile + provider registry
```

All new hardening evidence remains `REFERENCE`, `CI PROVEN` or `ADAPTER CONTRACT`. No hardening capability is yet `FABRIC PROVEN` through retained real workspace execution.

## Implemented development runtime

The branch now provides:

- strict immutable typed dataset metadata and allow-listed runtime overrides;
- independent capture semantics, apply semantics, capture engine, apply engine and progress ownership;
- immutable provider-neutral `ExecutionPlan`;
- named capability profiles and fail-closed unsupported-combination validation;
- composite WATERMARK + overlap;
- normalized Bronze lineage;
- DQ/quarantine/no-silent-loss accounting;
- complete guarded apply catalog: APPEND, REPLACE, UPSERT, SCD1, SCD2 and SNAPSHOT_DIFF;
- APPEND source-controlled identity with exact-replay no-op and conflicting-identity failure;
- FULL -> REPLACE and SNAPSHOT -> SNAPSHOT_DIFF publication/delete protection;
- canonical CDC I/U/D ordering/dedupe/bounded-window semantics;
- CDC -> UPSERT/SCD1/SCD2;
- durable optimistic downstream CDC checkpoints;
- snapshot/bootstrap -> CDC no-gap/no-double-apply handoff;
- Debezium/Kafka topic/partition/offset normalization and retention-aware safe resume planning;
- Fabric Copy Job/Copy Activity/Dataflow Gen2/Spark capture adapter contracts;
- typed `CaptureReceipt` native/external handoff;
- conservative retry, attempt lineage and unknown-target-commit recovery;
- executable quarantine REPLAY coordination;
- guarded FULL_REBUILD with stable destructive identity and optimistic capture-aware state cutover;
- typed schema contracts and deterministic compatibility policy;
- schema fingerprint/version materialization plus append-only runtime schema-change evidence;
- immutable file-manifest readiness/completeness/version evidence;
- API frozen-window, cursor-chain, completeness, page/record-limit and replay-drift guards;
- shared temporal taxonomy separating source order from event/valid time;
- shared source-order comparison wired into batch UPSERT/SCD1 and CDC current-state;
- shared event-time comparison wired into CDC-SCD2 while preserving fail-closed retroactive-history behavior;
- metadata-driven dispatcher/dependency/failure isolation;
- bounded logical-name domain extensions;
- immutable release/delivery contracts and CLI foundations.

## Apply strategy status

```text
APPEND          IMPLEMENTED reference
REPLACE         IMPLEMENTED reference
UPSERT          IMPLEMENTED reference
SCD1            IMPLEMENTED reference
SCD2            IMPLEMENTED reference
SNAPSHOT_DIFF   IMPLEMENTED reference
```

APPEND uses `load.append_identity`, not `merge_key`. Exact business-event replay is a no-op even when run lineage changes; the same identity with changed business payload fails closed.

## Temporal correctness

The framework now has one provider-neutral taxonomy for the two independent clocks:

```text
source order: STALE | EQUAL | NEWER
event time:   EARLIER | EQUAL | LATER | UNKNOWN
```

Shared conditions include `STALE_SOURCE_POSITION`, `EQUAL_SOURCE_POSITION`, `LATE_EVENT_TIME`, `SAME_EVENT_TIME` and `IN_ORDER`.

A newer source position with earlier valid/event time is explicitly classified as requiring history rewrite. Current CDC-SCD2 still refuses that rewrite with `CDCSCD2LateArrivingError`; the shared taxonomy does not pretend retroactive-history reconstruction is implemented. Equal event time with a newer source position remains legal.

## Schema evolution

Source-controlled `SchemaContract` supports `EXACT`, `ADDITIVE_ONLY` and conservative `SAFE_EVOLUTION`. Certified widening/relaxation includes INT32 -> INT64, FLOAT32 -> FLOAT64, compatible STRING widening, DECIMAL precision widening at stable scale and required -> nullable. Removal, narrowing, nullable -> required, scale change and uncertified cross-family conversions fail closed.

Deployment materializes versioned rows in `dataset_contract`; runtime observations append to environment-local `schema_change` evidence.

## File/API capture guardrails

File capture freezes source listing/snapshot reference plus object URI/version/readiness metadata into a deterministic manifest fingerprint. Retry/replay must resolve to the same manifest.

API capture freezes logical bounds + predicate identity before page 1 and validates contiguous cursor chain, completion, terminal cursor, page/record limits, row accounting, cycles and retry/replay window drift.

These are provider-neutral guardrails; actual storage/API clients remain integration work.

## Recovery status

Reference recovery includes bounded retry, attempt lineage, unknown-outcome reconciliation, quarantine REPLAY and guarded FULL_REBUILD. Remaining recovery work is primarily physical/provider-specific: native Fabric downstream-failure resume, real Kafka source-cursor commit coordination, durable physical-target idempotency and operator integration.

## Control-plane ownership

Current schema:

```text
CONTROL_PLANE_SCHEMA_VERSION = 3
v1 phase1_initial_control_plane_schema
v2 execution_policy_ordering_capture_receipt_recovery_and_cdc
v3 append_identity_semantics
```

v3 contains a real additive migration for existing v2 `load_policy` tables.

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

Environment-local runtime/evidence includes migrations, overrides, watermarks, CDC checkpoints, leases/state, pipeline/dataset/step runs, attempt lineage, capture receipts, reconciliation/quarantine/schema-change/reprocess/deployment evidence. None is promoted DEV -> UAT -> PROD.

## Fabric/provider boundary

Current Fabric adapters are adapter contracts with injected transports and fake-transport certification. Debezium/Kafka is provider-adapter/reference recovery evidence. Missing real proof includes actual REST/SDK/CLI/Kafka clients, authentication/environment binding, live polling/seek/commit, retained provider run IDs and a real Fabric Pipeline backend.

Do not describe current adapter-contract evidence as real Fabric/Kafka integration.

## Exact next implementation sequence

1. Add a supported control-plane read/query/operator surface so on-call workflows do not require hand-written table joins.
2. Complete remaining native/provider progress recovery and durable physical-target idempotency proofs.
3. Implement actual Fabric/Kafka transports and Fabric Pipeline backend.
4. Prove at least one approved DEV hybrid execution retaining Fabric/provider correlation.
5. Add additional provider CDC adapters only when supported product scope requires them.
6. Re-run production readiness/guarantee/docs audit against the exact release-candidate head.
7. Decide the next immutable release scope/version only after those gates are explicit.

## Durable project memory

New conversations should read in this order:

```text
docs/CURRENT_STATUS.md
docs/PRODUCTION_READINESS_AUDIT.md
docs/GUARANTEE_COVERAGE.md
docs/PROJECT_BLUEPRINT.md
docs/PRODUCTION_REQUIREMENTS.md
docs/EXECUTION_ENGINE_STRATEGY.md
docs/FABRIC_EXECUTION_MODEL.md
docs/CDC_DESIGN.md
docs/CONTROL_PLANE_DESIGN.md
docs/REPOSITORY_STRUCTURE.md
docs/CICD_DESIGN.md
docs/ECOSYSTEM_BLUEPRINT.md
```

If docs disagree with code/tests, inspect implementation and repair docs before continuing.
