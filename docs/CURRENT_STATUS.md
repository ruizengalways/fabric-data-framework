# Current Status — fabric-data-framework

Last updated: 2026-08-29

## Current phase and release gate

`v0.3.0` remains the latest immutable public framework release. Source version `0.4.0` is an unreleased development line.

Active work is PR #13 on `architecture/production-framework-blueprint`. **Do not publish v0.4.0 yet.** The hardening branch is now a broad portable/reference product slice, but real Fabric/Kafka execution and external enterprise controls remain unproven.

The product target remains: after an enterprise installs the released wheel, routine datasets onboard through source-controlled metadata, environment bindings, capability profiles and bounded logical-name extensions rather than edits to the framework.

## Latest validated implementation evidence

```text
ae1eb99ab5fa9d7add5a62dda2d7448b6200d240
GitHub Actions 33225341709
268 tests passed
typed read-only control-plane operator snapshot + control-plane-status CLI

1ee22d5828a5f53a3f9050722bdb5b7f7b28de43
GitHub Actions 33225064570
261 tests passed
shared source-order/event-time taxonomy wired through current-state and CDC/SCD2

c326f062ad4e6be5185f17b9e6830946967361ab
GitHub Actions 33224558393
252 tests passed
replay-stable file manifest + API frozen-window/pagination guardrails

6eb4ff275ed1aad9092f60f098d2a9272fd06779
GitHub Actions 33223276476
231 tests passed
typed schema contract/evolution policy + schema-change evidence

2466d6f254b37a1d79a716e8dd95c5dd16d21cf4
GitHub Actions 33222949040
215 tests passed
APPEND identity/replay semantics + control-plane v3 migration proof

f3521aa79b2cc66865d46a30e119a7dc4784d698
GitHub Actions 33220690474
197 tests passed
guarded FULL_REBUILD target/state cutover
```

All of the above are `REFERENCE`, `CI PROVEN` or `ADAPTER CONTRACT` evidence. No hardening capability is yet `FABRIC PROVEN` through a retained real workspace execution.

## Implemented development runtime

The branch now provides:

- strict immutable metadata/effective config and allow-listed runtime overrides;
- independent capture semantics, apply semantics, capture engine, apply engine and progress owner;
- immutable provider-neutral `ExecutionPlan` and named capability profiles;
- composite WATERMARK + overlap;
- Bronze lineage, row DQ/quarantine and no-silent-loss accounting;
- all six canonical apply strategies: APPEND, REPLACE, UPSERT, SCD1, SCD2, SNAPSHOT_DIFF;
- guarded FULL -> REPLACE and SNAPSHOT -> SNAPSHOT_DIFF publication/delete behavior;
- canonical CDC I/U/D ordering/dedupe/bounded-window semantics;
- CDC -> UPSERT/SCD1/SCD2 and durable optimistic downstream CDC checkpoints;
- snapshot/bootstrap -> CDC no-gap/no-double-apply handoff;
- Debezium/Kafka topic/partition/offset adapter + retention-aware safe resume planning;
- Fabric Copy Job/Copy Activity/Dataflow Gen2/Spark capture adapter contracts;
- typed `CaptureReceipt` native/external handoff;
- bounded retry, attempt lineage, unknown-commit tri-state recovery, quarantine REPLAY and guarded FULL_REBUILD;
- typed schema contracts with deterministic EXACT/ADDITIVE_ONLY/SAFE_EVOLUTION policy and append-only schema-change evidence;
- replay-stable file-manifest and API frozen-window/pagination guards;
- shared temporal taxonomy separating source order from event/valid time, wired into batch current-state and CDC/SCD2 comparison paths;
- metadata-driven dispatcher/dependency/failure isolation;
- bounded logical-name domain extensions;
- control-plane schema v3 with a real v2 -> v3 additive APPEND migration;
- typed read-only operator snapshots over run/capture/progress/reconciliation/quarantine/schema/reprocess evidence;
- `fabric-framework control-plane-status` JSON CLI for one dataset or an ordered dataset overview;
- immutable release/delivery contracts and deployment provenance foundations.

## Temporal correctness

The shared taxonomy is now implemented at reference level:

```text
source order: STALE | EQUAL | NEWER
event time:   EARLIER | EQUAL | LATER | UNKNOWN
```

A newer source event with earlier event/valid time is classified as `LATE_EVENT_TIME` and `requires_history_rewrite=true`. CDC-SCD2 still rejects that case with `CDCSCD2LateArrivingError`; this taxonomy does not imply retroactive history reconstruction. Equal event time with a newer source position remains legal.

## Operator surface

`get_dataset_operational_snapshot()` returns a typed read-only view of:

- latest dataset run + attempt lineage;
- latest capture/native/provider correlation;
- current WATERMARK/CDC downstream progress;
- latest reconciliation;
- unreplayed quarantine backlog counts;
- latest schema-change observation;
- active PENDING/RUNNING reprocess requests.

`list_dataset_operational_snapshots()` provides a deterministic dataset-id ordered overview. The CLI exposes the same contract through `control-plane-status` and optional JSON file output.

This is a supported reference query surface. It does **not** make SQLite the production control-plane technology and does not provide mutation/operator approval workflows yet.

## Control plane

```text
CONTROL_PLANE_SCHEMA_VERSION = 3
v1 phase1_initial_control_plane_schema
v2 execution_policy_ordering_capture_receipt_recovery_and_cdc
v3 append_identity_semantics
```

Promotable definitions remain separate from environment-local runtime/evidence. No watermarks, CDC checkpoints, runs, receipts, quarantine, schema observations or reprocess requests are promoted between environments.

## Fabric/provider boundary

Current Fabric adapters use injected transports and fake-transport certification. Debezium/Kafka is provider-adapter/reference recovery evidence. Missing real proof includes actual REST/SDK/CLI/Kafka clients, authentication/environment binding, live polling/seek/commit, retained provider run IDs and a real Fabric Pipeline backend.

Do not describe current adapter-contract evidence as real Fabric/Kafka integration.

## Exact next implementation sequence

1. Add durable target-operation idempotency/operation-journal semantics so retry and unknown-outcome handling has a persistent stable operation key rather than only executor convention.
2. Complete remaining native/provider progress recovery, especially downstream-failure resume for Fabric-native engines and real Kafka cursor coordination.
3. Select/certify a production control-plane repository technology and transaction/concurrency behavior; retain the current operator API above that repository boundary.
4. Implement actual Fabric/Kafka transports and Fabric Pipeline backend.
5. Prove at least one approved DEV hybrid execution retaining Fabric/provider correlation.
6. Add additional provider CDC adapters only when supported product scope requires them.
7. Re-run exact-candidate audit/docs/CI and decide the next immutable release scope/version.

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
