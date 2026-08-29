# Current Status — fabric-data-framework

Last updated: 2026-08-29

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine: **COMPLETE AND RELEASED AS `v0.3.0`**.
- Phase 4 — metadata-driven dispatcher/failure isolation: **MERGED TO `main` AS UNRELEASED 0.4.0 DEVELOPMENT SOURCE**.
- Current milestone — **PRODUCTION FRAMEWORK HARDENING; RELEASE PAUSED UNTIL THE PRODUCT SLICE IS MATERIALLY BROADER AND REAL FABRIC EVIDENCE EXISTS**.

## Release gate

Do **not** publish `v0.4.0` now.

Latest immutable public framework release remains `v0.3.0`. Source version `0.4.0` is an unreleased development line.

Active work:

```text
PR #13
architecture/production-framework-blueprint
```

The target product is a wheel an enterprise domain installs and normally uses through source-controlled metadata, environment bindings, capability profiles and bounded logical-name extensions. Routine onboarding must not require framework edits.

## Latest coherent implementation evidence

Current hardening sequence is green:

```text
ccf0fc8950efb1f4d338cadcaf83aac5fd49a7b9
Actions 33215409341
153 tests passed
canonical CDC + CDC -> UPSERT/SCD1

ed6c13d4fcabe165ef86be2e547d794e15e5375c
Actions 33215708004
159 tests passed
CDC -> SCD2

c41fbd00bb3d3c6bc71e20f958c4ec14106ac33c
Actions 33216133811
165 tests passed
CDC checkpoint persistence + optimistic concurrency

465a2c1e9ddf25b0ace2293f578c2c5bb3a653ae
Actions 33216281126
171 tests passed
snapshot/bootstrap -> CDC no-gap/no-double-apply handoff

1087ab9231b9cb638a87bc2f78ef0c1b1fe32beb
Actions 33219601375
179 tests passed
Debezium/Kafka envelope adapter + retention-aware resume planning

ecdca38099a4f21c6f40701dc14889b464c20608
Actions 33219783325
183 tests passed
Debezium/Kafka capability profile + explicit provider-adapter registry

6b4a3cd2ddecd818d22fabe22988c043cdcff260
Actions 33220487307
190 tests passed
fail-closed quarantine REPLAY coordination

f3521aa79b2cc66865d46a30e119a7dc4784d698
Actions 33220690474
197 tests passed
guarded FULL_REBUILD target/state cutover
```

Earlier hardening evidence remains relevant:

```text
b831d465c2f03117c323a0cbd90e22bbf081417c
Actions 33178765403
123 tests passed
Fabric capture adapter contract

a5da06294dfba0c5ae756dcc1d8814931feebec7
Actions 33179754372
139 tests passed
retry/unknown-commit recovery + relational recovery evidence
```

All of the above are portable/reference or adapter-contract CI evidence. No new hardening capability is yet `FABRIC PROVEN` through a retained real workspace execution.

## Implemented development runtime

The hardening branch now provides:

- strict typed semantic config and allow-listed runtime overrides;
- infrastructure/environment binding abstraction;
- composite WATERMARK selection with tie-breakers/overlap;
- normalized Bronze lineage envelope;
- row DQ/quarantine and no-silent-loss accounting primitives;
- deterministic SCD2 foundation;
- shared ordered current-state primitive for SCD1 and UPSERT;
- ordered/idempotent SCD1 and UPSERT;
- guarded FULL -> REPLACE;
- guarded SNAPSHOT -> SNAPSHOT_DIFF;
- metadata-driven dispatcher with dependency validation/failure isolation;
- provider-neutral immutable `ExecutionPlan` / execution units;
- independent capture/movement and apply executor selection;
- named engine capability profiles;
- Dataflow Gen2 incremental capture profile feeding framework SCD1/UPSERT;
- typed `CaptureReceipt` native/external handoff;
- fail-closed Fabric capture adapter boundary for Copy Job, Copy Activity, Dataflow Gen2 and Spark;
- controlled logical-name domain extension registry;
- conservative retry, attempt lineage and unknown-target-commit recovery;
- RETRY/BACKFILL/REPLAY/FULL_REBUILD request contracts;
- executable quarantine REPLAY with external governed payload-provider boundary, batch identity/row-count validation and post-gate replay marking;
- guarded FULL_REBUILD with stable destructive operation identity, optimistic state cutover and capture-aware replacement state;
- canonical CDC event/order/dedupe/bounded-window contracts;
- CDC -> UPSERT/SCD1 current-state apply;
- CDC -> SCD2 history apply with source-order/valid-time separation;
- durable environment-local CDC apply checkpoints with optimistic concurrency;
- snapshot/bootstrap -> CDC no-gap/no-double-apply handoff contract;
- built-in Debezium/Kafka envelope adapter using topic/partition/offset as canonical order;
- Debezium snapshot-read and tombstone handling policies;
- retention-aware Kafka resume planning from the framework committed apply checkpoint;
- source-controlled `EXTERNAL_CDC/debezium_kafka_v1` capability profile;
- explicit provider CDC adapter registry keyed by engine/profile;
- additive control-plane schema v2 including capture/apply execution policy, ordering policy, capture receipt, recovery lineage and CDC checkpoint;
- immutable release/delivery contracts and CLI.

## CDC semantic core

Canonical design: `docs/CDC_DESIGN.md`.

Provider-specific positions must be normalized before entering the semantic core:

```text
provider LSN / binlog / Kafka offset / native coordinate
       -> partition + integer position tuple
       -> CDCEvent
```

Current normalization certifies INSERT/UPDATE/DELETE, event identity, canonical key, source position, before/after, event time/transaction metadata, frozen upper checkpoint, completeness evidence, duplicate handling, conflict detection, committed-overlap ignore and deterministic ordering.

The framework intentionally fails closed if an adapter has not supplied enough sequence information to prove a unique event position.

## Debezium/Kafka provider adapter

Current built-in provider profile:

```text
execution engine: EXTERNAL_CDC
capability profile: debezium_kafka_v1
progress owner: EXTERNAL
apply engine: independently selected; framework/Spark by default
```

The adapter maps Debezium records consumed from Kafka into canonical `CDCEvent`/`CDCCheckpoint` using:

```text
topic + partition + offset -> canonical source position
```

Database LSN/binlog values remain metadata only; they are not guessed into a total row order.

Certified adapter behavior includes:

- Debezium `c/u/d` -> canonical INSERT/UPDATE/DELETE;
- Kafka tombstone -> provider cleanup, not a second business delete;
- Debezium snapshot `op=r` rejected by default to avoid bootstrap double-apply;
- explicit policy may map `r` to INSERT when intentionally required;
- explicit Kafka record key required; business key is not inferred from arbitrary payload;
- mixed topic / missing partition / record beyond frozen upper offset fail closed;
- provider adapter resolution is explicit through `(EXTERNAL_CDC, debezium_kafka_v1)`.

Resume planning deliberately ignores an external consumer-group cursor when deciding safe downstream recovery. It derives the next required offset from the framework committed CDC apply checkpoint and fails with a retention-gap error if Kafka no longer retains that offset.

This is reference/provider-adapter evidence only. No real Kafka broker, Debezium connector or consumer group has been exercised by this branch.

## CDC apply semantics

### CDC -> UPSERT / SCD1

Current-state targets retain framework CDC source-position metadata after first CDC mutation.

Certified behavior includes insert/update/delete/reinsert, stale event suppression, equal-position conflict detection, exact rerun, delete policy and bootstrap rows entering CDC only after a committed lower checkpoint proves the event is newer.

### CDC -> SCD2

Two clocks remain separate:

```text
source position -> event order
event_time      -> valid interval
```

Same `event_time` with distinct source positions is legal. A newer source event whose valid-time predates the current history version is currently rejected with `CDCSCD2LateArrivingError`; retroactive history rewrite is not silently invented.

## Durable CDC checkpoint

Environment-local control plane includes:

```text
cdc_checkpoint
  dataset_id
  positions
  committed_dataset_run_id
  version
```

`positions` are CDC semantic apply progress. `version` is only an optimistic-concurrency token.

Checkpoint advancement requires target commit + required reconciliation and refuses regression, partition drop and stale writer overwrite.

For FABRIC_NATIVE/EXTERNAL capture, native source progress remains provider-owned and is retained in `CaptureReceipt`; the framework checkpoint records downstream semantic application progress rather than pretending to own the native cursor.

## Snapshot/bootstrap -> CDC

Current reference contract proves:

```text
start/retain CDC at S
   S <= B
complete snapshot consistent through B
publish snapshot
consume buffered CDC
   <= B -> ignore
   >  B -> apply
```

Bootstrap fails closed for incomplete snapshot evidence, stream start after the snapshot fence, partition-set changes, or a first CDC upper checkpoint below the snapshot boundary.

## Recovery core

Implemented reference behavior:

```text
RETRYABLE       -> bounded retry
NON_RETRYABLE   -> stop
UNKNOWN_OUTCOME -> reconcile first
  COMMITTED     -> converge SUCCESS without rewrite
  NOT_COMMITTED -> retry may proceed
  UNRESOLVED    -> stop
```

### Quarantine REPLAY

REPLAY no longer means only an audited intent. The framework now resolves immutable quarantine evidence from the control plane, loads payload through a governed external payload-provider protocol, verifies dataset/reference/row-count identity and calls replay logic with a typed plan. `replayed_by_dataset_run_id` advances only after target/reconciliation state gate success. Exact rerun by the same replay run is idempotent; a different run cannot silently claim an already replayed batch.

### FULL_REBUILD

FULL_REBUILD uses `reprocess_request_id` as the stable destructive-operation identity across attempts. Target reconstruction must explicitly prove authoritative completion and pass the required state gate before runtime progress is cut over. Replacement progress is capture-aware (`NONE`, `WATERMARK`, `CDC`, `EXTERNAL`) and state persistence uses optimistic versioning so a concurrent state change is never overwritten. Re-running an already completed rebuild request converges without repeating destructive work.

Remaining recovery gaps are physical/native integration specific: Copy/Dataflow/Mirroring downstream-failure resume proofs, real Kafka cursor commit coordination, remaining capture-family frozen-window certification, persistent target idempotency and supported operator API/CLI.

## Fabric adapter status

Implemented adapter-contract surfaces:

```text
Copy Job
Copy Activity
Dataflow Gen2
Spark Job
```

Adapters validate already-compiled capture units, native evidence and source boundaries and emit `CaptureReceipt` only for proven success.

Still missing:

- actual Fabric REST/SDK/CLI transport implementation;
- real workspace item execution/polling;
- approved authentication/environment binding proof;
- retained real native run IDs from DEV;
- Fabric Pipeline backend.

Do not describe the current adapter contract as real Fabric integration.

## Control-plane ownership

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

## Current external boundary

This hardening work has not modified an enterprise Fabric workspace, capacity, tenant setting, RBAC assignment, network route, connection, credential, production dataset or production runtime state.

SQLAlchemy/SQLite control-plane evidence is a schema/transaction reference proof, not an approved production store.

## Exact next implementation sequence

1. Implement APPEND identity/collision/replay semantics with source-controlled append identity and control-plane materialization.
2. Implement general schema-evolution classification and compatibility policy.
3. Add shared late/out-of-order taxonomy beyond the current fail-closed SCD2 retroactive case.
4. Add file-manifest and API-pagination/window capture guardrails.
5. Complete remaining physical/native progress recovery and durable target-idempotency proofs.
6. Add supported persistent control-plane repository/operator query surface.
7. Implement actual Fabric/Kafka transports/backend and prove at least one approved DEV hybrid execution.
8. Add additional provider CDC adapters only where supported product scope requires them; keep canonical CDC unchanged.
9. Re-run production readiness/guarantee/docs audit against the exact candidate head.
10. Only then decide the next immutable framework release scope/version.

## Durable project memory

New conversations must read:

```text
docs/ECOSYSTEM_BLUEPRINT.md
docs/PROJECT_BLUEPRINT.md
docs/PRODUCTION_REQUIREMENTS.md
docs/EXECUTION_ENGINE_STRATEGY.md
docs/FABRIC_EXECUTION_MODEL.md
docs/CDC_DESIGN.md
docs/REPOSITORY_STRUCTURE.md
docs/CONTROL_PLANE_DESIGN.md
docs/CICD_DESIGN.md
docs/PRODUCTION_READINESS_AUDIT.md
docs/GUARANTEE_COVERAGE.md
docs/CURRENT_STATUS.md
```

If another document conflicts with current code/tests, inspect implementation and repair the document before continuing.
