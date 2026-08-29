# Production Requirements — fabric-data-framework

Status: Canonical requirements baseline
Last updated: 2026-08-29

## Product contract and evidence levels

`fabric-data-framework` is a reusable enterprise wheel. Routine datasets onboard through source-controlled dataset metadata, source/capture truth classification, environment bindings, certified capability profiles and bounded domain extensions rather than framework forks.

Evidence levels remain distinct: portable semantics, deterministic CI certification, real Fabric/provider execution, and external enterprise controls. Reference tests must never be described as real service evidence.

## Architecture invariants

1. Source fidelity is classified before Silver history semantics or physical-tool selection.
2. Capture and apply strategies are independent.
3. Capture/movement and apply engines are independent.
4. One physical capture has one source-progress authority: FRAMEWORK, FABRIC_NATIVE or EXTERNAL.
5. Provider source progress, framework semantic source progress and target-operation outcome are distinct state domains.
6. Native/provider capture hands off through immutable typed evidence.
7. Provider CDC coordinates normalize before canonical CDC logic.
8. Capture fidelity is an upper bound on truthful history fidelity; missing source changes are never invented.
9. Delete visibility is explicit and cannot be inferred from the word “incremental”.
10. Bronze write mode follows source fidelity/recovery requirements rather than a universal APPEND/MERGE rule.
11. Dataset is the default failure/retry boundary.
12. Dataset attempt identity is not target-operation identity.
13. A retry of one frozen semantic target mutation must reuse one stable operation key.
14. A target mutation with uncertain commit outcome must be reconciled before re-execution.
15. Only a target operation proven NOT_COMMITTED may be automatically re-issued.
16. Runtime state/evidence is environment-local and never promoted.
17. Source state advances only after required target and reconciliation evidence.
18. Retry/replay must not silently change the source window/set.
19. Source order and event/valid time are independent clocks.
20. Real Fabric/provider/security/capacity evidence must not be fabricated by reference tests.

## Source onboarding and capture-pattern requirements

The executable mainstream catalog is:

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

Each pattern declares compatible coarse capture strategy, change fidelity, delete visibility, Bronze write/content semantics, replay identity, truthful history fidelity and recommended apply semantics.

Canonical history fidelity:

```text
NONE | OBSERVED_CHANGES | BATCH_GRAIN | FULL_EVENT | SNAPSHOT_GRAIN | SOURCE_DEFINED
```

Mandatory truthfulness includes:

- ordinary watermark cannot claim hard-delete visibility without another delete signal;
- watermark SCD2 is `OBSERVED_CHANGES`;
- native net CDC SCD2 is `BATCH_GRAIN`;
- recurring snapshot diff is `SNAPSHOT_GRAIN`;
- full ordered CDC/Debezium/Delta CDF may claim `FULL_EVENT` for captured changes only when ordering/completeness/retention is proven;
- API/file fidelity remains `SOURCE_DEFINED` until the source contract proves more.

`DatasetCaptureSelection` records source-controlled pattern/Bronze/history/delete claims. Domain CI should use `fabric-framework capture-onboarding-validate --require-all`.

This onboarding declaration is a Git/CI companion, not runtime control-plane state.

## Capture requirements

Canonical coarse strategies:

```text
FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM
```

Implemented reference guarantees include FULL/SNAPSHOT completeness evidence, composite WATERMARK + overlap, typed CaptureReceipt, canonical CDC order/dedupe/frozen windows, downstream CDC checkpoints, snapshot->CDC handoff, Debezium/Kafka normalization/resume, Delta CDF normalization/profile, Fabric capture adapter contracts, immutable file manifests and frozen API windows/cursor chains.

Still required: real Fabric transports/polling, live Kafka consumer/seek/commit, real Delta CDF bounded-read/retention proof and real auth/network/gateway/capacity evidence.

## Bronze requirements

Source-faithful does not imply one universal write mode:

```text
complete current snapshot -> OVERWRITE may be valid with completeness evidence
watermark/current rows     -> MERGE may be valid with ordered idempotent evidence
full CDC/CDF/events        -> APPEND required if full event history is claimed
net CDC                    -> MERGE current OR APPEND batch observations
```

Applicable source/snapshot/window/file/event/order/schema/run evidence must remain traceable through Bronze or governed landing evidence.

## Apply requirements

```text
APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF
```

All six have framework-owned reference implementations. APPEND uses explicit append identity; REPLACE/SNAPSHOT_DIFF require isolated complete candidates; UPSERT/SCD1 share ordered current-state correctness; SCD2 preserves deterministic history.

`CDC != SCD2`, `FULL != REPLACE`, and an SCD2 target does not upgrade weak capture fidelity into full history.

## Durable target-operation idempotency requirements

Canonical guide: `docs/TARGET_OPERATION_IDEMPOTENCY.md`.

Every target mutation that may be retried across attempts/restarts must have a stable semantic identity:

```text
operation_key = hash(
  schema version,
  dataset_id,
  run_mode,
  apply_strategy,
  target_reference,
  effective_config_hash,
  mutation_scope_hash
)
```

`operation_key` must not include `dataset_run_id`, attempt number or current time.

`mutation_scope_hash` must deterministically identify the exact frozen mutation input. Depending on source/apply this includes evidence such as:

- WATERMARK: frozen lower/upper/tie-breaker/overlap + candidate identity;
- CDC/Debezium/Delta CDF: lower/upper checkpoints + normalized event/candidate identity;
- FULL/REPLACE: snapshot identity/completeness + candidate hash;
- SNAPSHOT_DIFF: previous/current snapshot identities + diff hash;
- APPEND: frozen batch/event identity set;
- file/API: frozen manifest/window/cursor evidence + candidate hash;
- BACKFILL/REPLAY/FULL_REBUILD: explicit range/request/candidate/reset evidence.

Required lifecycle:

```text
PREPARED -> IN_PROGRESS
IN_PROGRESS -> COMMITTED | COMMIT_UNKNOWN | NOT_COMMITTED | FAILED
COMMIT_UNKNOWN -> COMMITTED | NOT_COMMITTED
NOT_COMMITTED -> IN_PROGRESS | FAILED
COMMITTED / FAILED terminal
```

Behavioral requirements:

- reserve operation before target mutation;
- exact reserve is idempotent;
- persisted COMMITTED converges without another target mutation;
- persisted IN_PROGRESS is treated as uncertain after attempt/process loss;
- COMMIT_UNKNOWN must be reconciled before re-execution;
- only NOT_COMMITTED may be automatically retried;
- unexpected exception after target mutation starts defaults to unknown outcome unless rollback is explicitly proven;
- lifecycle update uses optimistic compare-and-swap versioning;
- target operation COMMITTED does not bypass dataset reconciliation/state-commit gates;
- journal state is environment-local and never promoted.

Target integrations must eventually provide stable target-side outcome evidence where available, for example transaction/job/version/commit identifiers.

## Delete requirements

Delete handling is tied to evidence:

```text
NONE               -> hard delete cannot be discovered
SNAPSHOT_INFERRED  -> complete authoritative snapshot required
TOMBSTONE          -> ordered delete marker must survive parsing/DQ
EXPLICIT_EVENT     -> preserve operation + source position
SOURCE_DEFINED     -> source contract defines semantics
```

Missing rows in an incomplete extract must never be interpreted as deletes.

## Temporal requirements

Shared source-order taxonomy is `STALE | EQUAL | NEWER`; event/valid-time taxonomy is `EARLIER | EQUAL | LATER | UNKNOWN`. A newer source event with earlier valid time requires history rewrite; retroactive SCD2 rewrite remains intentionally unsupported and fails closed.

## Schema requirements

Schema is a source-controlled semantic contract. Compatibility is `EXACT | ADDITIVE_ONLY | SAFE_EVOLUTION`; only explicitly certified widening/relaxation is accepted. Removal/narrowing/unproven conversion fails closed.

## File/API requirements

File capture freezes a stable manifest including URI/version/readiness evidence; a mutable path alone is not replay identity. API capture freezes logical bounds/predicate/start cursor before page 1 and proves cursor continuity/completeness/limits/accounting. Retry/replay must use the same frozen scope.

## CDC provider requirements

Built-in/reference profiles:

```text
EXTERNAL_CDC / debezium_kafka_v1 / EXTERNAL progress
SPARK        / delta_cdf_v1       / FRAMEWORK progress
```

Provider adapters normalize to canonical CDC and do not own SCD1/SCD2 semantics. Kafka safe resume derives from downstream applied checkpoint rather than blindly trusting an ahead consumer cursor. Delta CDF fails closed when same-key within-commit order cannot be proven.

## Execution/delegation requirements

Capture engines:

```text
FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 | SPARK |
FABRIC_MIRRORING | EXTERNAL_CDC | SQL | CUSTOM
```

Named profiles require explicit engines. Unsupported capture/apply/progress/order combinations fail before mutation. AUTO resolves before execution; silent switching is forbidden.

## Recovery requirements

Canonical modes:

```text
NORMAL | RETRY | BACKFILL | REPLAY | FULL_REBUILD
```

Implemented reference behavior includes bounded retry, attempt lineage, reprocess lifecycle, target-operation journal/convergence, unknown-outcome reconciliation, quarantine REPLAY and guarded FULL_REBUILD.

Remaining recovery work is mainly provider/native integration: live Kafka cursor coordination, real Delta CDF retention-gap/resume proof, native Fabric downstream-failure handling and real target transaction/outcome reconciliation.

## Control-plane/operator requirements

Current development schema version: `4`.

Promotable definitions remain distinct from environment-local runtime/evidence. v4 adds environment-local `target_operation` with stable semantic key, lifecycle, attempt correlation, outcome evidence and optimistic version.

The typed operator snapshot/CLI must expose latest target-operation state alongside run/capture/progress/reconciliation/quarantine/schema/reprocess evidence.

A production persistent store is still unselected/unproven. Its concurrency/isolation/failover behavior must re-certify operation-journal CAS semantics.

## DQ/reconciliation requirements

For bounded row flows:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Required reconciliation can block source-state advancement even after target mutation is COMMITTED.

## Orchestration requirements

Reference dispatcher/planner supports metadata selection/grouping, dependency/cycle validation, bounded concurrency, sibling isolation and dependent BLOCKED behavior. Real Fabric Pipeline backend remains required.

## CI/CD and supply chain

Implemented/proven: Python 3.11/3.13 PR CI, Ruff/compile/pip check/tests, wheel build, immutable v0.3.0 release/checksum workflow, release/environment binding separation, runtime-state exclusion from promotion and exact framework version pinning.

Latest coherent target-operation baseline before docs audit:

```text
dd148a0c8e329c19809986fa9a32ed7edbe5dbfb
Actions 33239441546
323 passed
```

## Security/external controls

Framework metadata stores logical connection/secret refs, not credentials. External proof is required for Entra/workspace identity/RBAC, gateway/private networking, source CDC/CDF retention, Kafka/database access, backup/restore, monitoring/on-call, privacy/retention and capacity policy.

## Current release blockers

Do **not** publish `v0.4.0` yet.

Material blockers are now:

1. remaining real provider/native recovery and real target outcome integration required by release scope;
2. real Fabric/Kafka/Delta transports and Fabric Pipeline backend;
3. approved DEV hybrid execution retaining source/native/target correlation;
4. selected/certified production control-plane store with operation-journal concurrency/migration governance, or an explicitly bounded release promise;
5. final exact-head audit/docs/CI.

The portable stable target-operation key/journal is no longer an open placeholder once PR #16 merges.
