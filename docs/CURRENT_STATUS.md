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

The product target is a wheel that an enterprise domain installs and normally uses through source-controlled metadata, environment bindings, capability profiles and bounded logical-name extensions. Routine onboarding must not require framework edits.

## Latest coherent implementation evidence

Latest validated code baseline:

```text
c326f062ad4e6be5185f17b9e6830946967361ab
GitHub Actions 33224558393
252 tests passed
replay-stable file manifest + API frozen-window/pagination guardrails
```

Immediately preceding hardening evidence:

```text
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

1087ab9231b9cb638a87bc2f78ef0c1b1fe32beb
Actions 33219601375
179 tests passed
Debezium/Kafka envelope + retention-aware resume
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

APPEND uses `load.append_identity`, not `merge_key`. The framework writes reserved identity/payload hashes so an exact business-event replay is a no-op even when run lineage changes; the same identity with changed business payload fails closed.

## Schema evolution

Source-controlled `SchemaContract` supports:

```text
EXACT
ADDITIVE_ONLY
SAFE_EVOLUTION
```

`SAFE_EVOLUTION` currently certifies only explicit widening/relaxation rules such as INT32 -> INT64, FLOAT32 -> FLOAT64, compatible STRING widening, DECIMAL precision widening at stable scale, and required -> nullable. Removal, narrowing, nullable -> required, scale change and uncertified cross-family conversions fail closed.

Deployment materializes versioned rows in `dataset_contract`; runtime observations append to environment-local `schema_change` evidence.

## File/API capture guardrails

File capture contracts freeze:

```text
source snapshot/listing reference
file URI + stable version token
size + timezone-aware last_modified
readiness
complete-discovery evidence
manifest fingerprint
```

Retry/replay must resolve to the same frozen manifest. Duplicate paths, path/version ambiguity, incomplete discovery, non-ready files and policy-limit breaches fail closed.

API capture contracts freeze logical source bounds + predicate identity before page 1 and then validate a contiguous cursor chain. Completion, terminal cursor, page/record limits, row accounting, cursor cycles and retry/replay window drift are explicit guards.

These are provider-neutral guardrails; actual storage/API clients remain adapter/domain integration work.

## Recovery status

Reference recovery core now includes:

```text
RETRYABLE       -> bounded retry
NON_RETRYABLE   -> stop
UNKNOWN_OUTCOME -> reconcile first
  COMMITTED     -> converge SUCCESS without rewrite
  NOT_COMMITTED -> retry may proceed
  UNRESOLVED    -> stop
```

Quarantine REPLAY and FULL_REBUILD coordination are implemented reference capabilities. Remaining recovery work is mainly physical/provider specific: native Fabric downstream-failure resume, real Kafka source cursor commit coordination, durable physical-target idempotency and operator integration.

## Control-plane ownership

Current schema:

```text
CONTROL_PLANE_SCHEMA_VERSION = 3
v1 phase1_initial_control_plane_schema
v2 execution_policy_ordering_capture_receipt_recovery_and_cdc
v3 append_identity_semantics
```

v3 contains a real additive migration for existing v2 `load_policy` tables; it does not merely record a version row.

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

Environment-local runtime/evidence includes:

```text
schema_migration_history
runtime_override
watermark
cdc_checkpoint
dataset_state
dataset_lease
pipeline_run
dataset_run
dataset_attempt_lineage
capture_receipt
step_run
reconciliation_result
quarantine_batch
schema_change
reprocess_request
deployment_history
```

None of that runtime state is promoted DEV -> UAT -> PROD.

## Fabric/provider boundary

Current Fabric adapters are adapter contracts with injected transports and fake-transport certification. Debezium/Kafka is a provider adapter/reference recovery contract. Missing real proof includes actual REST/SDK/CLI/Kafka clients, authentication/environment binding, live polling/seek/commit, retained provider run IDs and a real Fabric Pipeline backend.

Do not describe current adapter-contract evidence as real Fabric/Kafka integration.

## Exact next implementation sequence

1. Add a shared cross-strategy late/out-of-order taxonomy and wire it into current-state/CDC history decisions without inventing retroactive rewrite semantics.
2. Complete remaining native/provider progress recovery and durable physical-target idempotency proofs.
3. Add a supported persistent control-plane repository/query/operator surface.
4. Implement actual Fabric/Kafka transports and Fabric Pipeline backend.
5. Prove at least one approved DEV hybrid execution retaining Fabric/provider correlation.
6. Add additional provider CDC adapters only when supported product scope requires them.
7. Re-run production readiness/guarantee/docs audit against the exact release-candidate head.
8. Decide the next immutable release scope/version only after those gates are explicit.

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
