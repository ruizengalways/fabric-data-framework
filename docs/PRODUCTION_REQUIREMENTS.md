# Production Requirements — fabric-data-framework

Status: Canonical requirements baseline
Last updated: 2026-08-29

## Product contract and evidence levels

`fabric-data-framework` is a reusable enterprise wheel. Routine datasets should onboard through source-controlled dataset metadata, source/capture truth classification, environment bindings, certified capability profiles and bounded domain extensions rather than framework forks.

Evidence levels remain distinct: portable semantics, deterministic CI certification, real Fabric/provider execution, and external enterprise controls. Reference tests must never be described as real service evidence.

## Architecture invariants

1. Source fidelity is classified before selecting Silver history semantics or a physical tool.
2. Capture strategy and apply strategy are independent.
3. Capture/movement engine and apply engine are independent.
4. One physical capture has one source-progress authority: FRAMEWORK, FABRIC_NATIVE or EXTERNAL.
5. Native/provider capture hands off through immutable typed evidence.
6. Provider CDC coordinates normalize before canonical CDC logic.
7. Provider source progress and framework downstream semantic progress are distinct.
8. Capture fidelity is an upper bound on truthful history fidelity; missing source changes must never be invented.
9. Delete visibility is explicit and cannot be inferred merely from the word “incremental”.
10. Bronze write mode follows source fidelity/recovery requirements rather than a universal APPEND/MERGE rule.
11. Dataset is the default failure/retry boundary.
12. Runtime state/evidence is environment-local and never promoted.
13. State advances only after required target/reconciliation evidence.
14. Unknown target writes are reconciled before retry.
15. Retry/replay must not silently change the source window/set.
16. Source order and event/valid time are independent clocks.
17. Real Fabric/provider/security/capacity evidence must not be fabricated by reference tests.

## Source onboarding and capture-pattern requirements

Every production dataset must be classifiable by what the source actually exposes, not by the product/tool selected to read it.

The framework executable catalog covers these mainstream patterns:

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

For each pattern the framework must expose/review:

```text
compatible coarse CaptureStrategy
change fidelity
delete visibility
allowed/default Bronze write mode
Bronze content semantics
retry/replay identity
SCD2/history fidelity
recommended apply strategies
known caveats
```

Canonical history fidelity vocabulary:

```text
NONE
OBSERVED_CHANGES
BATCH_GRAIN
FULL_EVENT
SNAPSHOT_GRAIN
SOURCE_DEFINED
```

Examples of mandatory truthfulness:

- ordinary watermark cannot claim hard-delete visibility without a tombstone/delete feed or authoritative reconciliation;
- watermark SCD2 is `OBSERVED_CHANGES`;
- native net CDC SCD2 is `BATCH_GRAIN`;
- recurring snapshot diff is `SNAPSHOT_GRAIN`;
- full ordered CDC/Debezium/Delta CDF can claim `FULL_EVENT` for captured changes when provider ordering/retention contracts are satisfied;
- API/file history remains `SOURCE_DEFINED` until source semantics prove more.

`DatasetCaptureSelection` is the source-controlled onboarding declaration for capture pattern, Bronze mode, history/delete claim, rationale and known limitations. `validate_capture_selection()` must reject contradictory/overstated claims.

Domain CI should use:

```bash
fabric-framework capture-onboarding-validate \
  --config-dir <dataset-config-dir> \
  --selections <capture-selections.json> \
  --require-all
```

The companion onboarding declaration is not currently a runtime control-plane table; no schema v4 is introduced solely for classification.

## Capture requirements

Canonical coarse strategies:

```text
FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM
```

Implemented reference guarantees include FULL/SNAPSHOT completeness evidence, composite WATERMARK + overlap, typed CaptureReceipt, canonical CDC order/dedupe/frozen windows, downstream CDC checkpoints, snapshot->CDC handoff, Debezium/Kafka normalization/resume planning, Delta CDF normalization/profile, Fabric capture adapter contracts, immutable file manifests and frozen API windows/cursor chains.

Still required: real Fabric transports/polling, live Kafka consumer/seek/commit, real Delta CDF bounded-read/retention recovery evidence, real auth/network/gateway/capacity evidence and additional provider adapters only where supported scope requires them.

## Bronze requirements

Bronze is source-faithful, but source-faithful does not imply one universal write mode.

Required rules:

```text
complete current snapshot
  -> OVERWRITE may be valid when snapshot identity/completeness is proven

watermark/current-state rows
  -> MERGE may be valid when ordered idempotent source evidence is retained

full CDC/CDF/business events
  -> APPEND is required if full event history is claimed

net CDC
  -> MERGE for current Bronze OR APPEND for batch observations
  -> neither may claim intermediate changes that native capture collapsed
```

Where audit/regulatory requirements require immutable raw landing, that archive is additive to the normalized Bronze contract rather than a reason to misclassify every source as an event stream.

Applicable source/snapshot/window/file/event/order/schema/run evidence must remain traceable through Bronze or governed landing evidence.

## Apply requirements

```text
APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF
```

All six have framework-owned reference implementations. APPEND requires explicit `append_identity`, exact replay is a no-op, and conflicting identity/payload fails closed. REPLACE and SNAPSHOT_DIFF require isolated candidates/completeness guards. UPSERT/SCD1 share ordered current-state correctness. SCD2 preserves deterministic history.

`CDC != SCD2` and `FULL != REPLACE` remain invariants. An SCD2 target does not upgrade weak capture fidelity into full history.

## Delete requirements

Delete handling must be tied to source evidence:

```text
NONE               -> hard delete cannot be discovered
SNAPSHOT_INFERRED  -> complete authoritative snapshot required
TOMBSTONE          -> ordered delete marker must survive parsing/DQ
EXPLICIT_EVENT     -> preserve operation + source position
SOURCE_DEFINED     -> source contract must define the semantics
```

Missing rows in an incomplete extract must never be interpreted as deletes.

## Temporal requirements

Shared taxonomy is implemented reference:

```text
source order: STALE | EQUAL | NEWER
event time:   EARLIER | EQUAL | LATER | UNKNOWN
```

Batch UPSERT/SCD1 and CDC current-state consume shared source-order comparison. CDC-SCD2 consumes the same source-order path plus shared event-time comparison.

A newer source event with an earlier valid/event time is classified as requiring history rewrite. Retroactive SCD2 history rewrite itself remains intentionally unsupported and must fail closed unless a future explicit policy certifies it.

## Schema requirements

Schema is a source-controlled semantic contract, not an engine auto-merge side effect.

Current compatibility policy:

```text
EXACT | ADDITIVE_ONLY | SAFE_EVOLUTION
```

SAFE_EVOLUTION accepts only explicitly certified widening/relaxation. Removal, narrowing, required additions, nullable->required, scale changes and uncertified cross-family conversions fail closed.

Deployment versions/materializes `dataset_contract`; runtime observations append environment-local `schema_change` evidence.

## File/API source requirements

File capture freezes provider listing/snapshot reference plus URI, stable version token, size, timezone-aware modification evidence and readiness into a deterministic complete manifest. Retry/replay must prove the same manifest. A mutable path alone is not a replay identity.

API capture freezes lower/upper logical bounds and predicate identity before page 1, then proves contiguous cursor/page sequence, no cycle, explicit completeness, terminal cursor, bounded page/record count and row accounting. Pagination itself does not prove delete or history fidelity.

Provider SDK/HTTP/auth/retry-after details remain integration concerns.

## CDC provider requirements

Built-in/reference profiles currently include:

```text
EXTERNAL_CDC / debezium_kafka_v1 / EXTERNAL progress
SPARK        / delta_cdf_v1       / FRAMEWORK progress
```

Debezium/Kafka canonical consumed order is topic/partition/offset. A consumer-group cursor that moved ahead of downstream apply cannot overwrite the framework safe resume point.

Delta CDF normalization consumes `insert`, `delete`, `update_preimage`, `update_postimage`, pairs unambiguous pre/post images for one key+commit, and bounds progress by commit version. It must fail closed when multiple logical same-key mutations inside one commit cannot be ordered. CDF retention must cover the next unapplied version; missing required versions are a recovery gap, not permission to jump forward.

Provider adapters normalize to canonical CDC and do not own SCD1/SCD2 semantics.

## Execution/delegation requirements

Capture engines:

```text
FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 | SPARK |
FABRIC_MIRRORING | EXTERNAL_CDC | SQL | CUSTOM
```

Named profiles require explicit engines. Unsupported capture/apply/progress/order combinations fail before mutation. Capture capability does not imply apply capability. AUTO resolves before execution; silent switching is forbidden.

## Recovery/idempotency requirements

Canonical modes:

```text
NORMAL | RETRY | BACKFILL | REPLAY | FULL_REBUILD
```

Implemented reference behavior includes bounded retry, attempt lineage, reprocess lifecycle, unknown-outcome COMMITTED/NOT_COMMITTED/UNRESOLVED resolution, quarantine REPLAY and guarded FULL_REBUILD.

Still required: durable target-operation idempotency/operation journal with stable semantic operation keys; native/provider downstream-failure recovery; real Kafka cursor coordination; Delta CDF retention-gap/resume proof against real storage.

## Control-plane/operator requirements

Current schema version: `3`.

Promotable definitions remain distinct from environment-local migrations, overrides, checkpoints, runs, receipts, reconciliation/quarantine/schema/reprocess/deployment evidence.

The read-only operator surface is implemented reference and returns typed stable views rather than raw SQL rows. A production persistent store is still unselected/unproven.

## DQ/reconciliation requirements

For bounded row flows:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Required reconciliation can block publication/state advancement. Governed quarantine payload storage, privacy/retention and authenticated operator replay integration belong to production deployment.

## Orchestration requirements

Reference dispatcher/planner supports metadata selection/grouping, dependency/cycle validation, bounded concurrency, sibling isolation, dependent BLOCKED, unrelated continuation and criticality-aware aggregate status.

Real Fabric Pipeline backend and provider-specific cancellation/timeout/tuning remain required.

## CI/CD and supply chain

Implemented/proven: Python 3.11/3.13 PR CI, Ruff/compile/pip check/tests, wheel build, immutable v0.3.0 release/checksum workflow, release/environment binding separation, runtime-state exclusion from promotion and exact framework version pinning by domains.

Latest deterministic PR #14 baseline:

```text
78018b90c3dfb7f7ff2297aa173e9e8dfaee40e6
Actions 33237905150
310 passed
```

The test suite validates the checked-in capture-pattern examples as real typed metadata, not illustrative pseudo-config.

## Security/external controls

Framework metadata stores logical connection/secret refs, not credentials. External proof is required for Entra/workspace identity/RBAC, tenant settings, gateway/private networking, source CDC/CDF retention, Kafka/database access, backup/restore, monitoring/on-call, privacy/retention and capacity policy.

## Current release blockers

Do **not** publish `v0.4.0` yet.

Material blockers now are:

1. durable target-operation idempotency and remaining provider/native recovery required by release scope;
2. real Fabric/Kafka/Delta provider transports and Fabric Pipeline backend;
3. approved DEV hybrid execution retaining real native/provider correlation;
4. selected/certified production control-plane store and concurrency/migration governance, or an explicitly bounded release promise;
5. final exact-head audit/docs/CI.

The mainstream capture catalog, onboarding truth claims, APPEND, schema evolution, file/API replay stability, shared temporal taxonomy and read-only operator diagnostics are no longer open placeholders.
