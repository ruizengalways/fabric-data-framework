# Current Status — fabric-data-framework

Status: Canonical recovery checkpoint  
Last updated: 2026-08-29

## 1. Release gate

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
latest main baseline  = 014cd334105de6f867b6320509b94147a444a2fa
latest full CI        = Actions 33253817758
full test baseline    = 455
```

**Do not publish `0.4.0` yet.** Portable semantics and deterministic CI are broad; the remaining release gate is retained approved real-environment evidence for the exact candidate release plus production backend/external controls.

## 2. Release-significant merged sequence

```text
PR #17 -> 83a27d9350a6018abc272e9afebdef5d660de519
  durable target-operation journal / control-plane v4

PR #19 -> fd6d5039a5852e32d823b178970816ff292472a2
  provider-native downstream recovery contracts

PR #21 -> 6377eafd4875c3cfe1d7bf21a982f6c11d47aea1
  production control-plane backend certification contract

PR #22 -> 650b7d30b2e31e21d01c56465e8871b91aae4779
  Fabric REST Job Scheduler + Data Pipeline backend

PR #24 -> 2fa8e2c4bc6875b529a4968694722d4108a635ff
  SQLAlchemy relational runtime repository

PR #26 -> 8f23942acd5b03d817e42b97d9f490acc6bee89f
  concrete Copy Job + Spark Job Definition REST transports

PR #28 -> 67562e4312dc9c37e8b7fb8d79535bb621bd573f
  Fabric Warehouse same-transaction target commit proof

PR #30 -> 732920e214ccdead20c632f7e70c0eb8f1267f0d
  approved DEV integration evidence harness

PR #32 -> e42dee86db3d4102c7264bc0d1f01f83fb8aade2
  approved-run preflight + read-only item smoke runner
  Actions 33251177339 / 407 tests

PR #34 -> 1c7d67bedd125f5fb5e983be791085fd1eaa9b0e
  orthogonal cheatsheet capture semantics + exact 14 acceptance presets
  Actions 33253215030 / 419 tests

PR #35 -> bf215fcb3538f9806b4002d2f154dbd46ae19412
  semantic onboarding validation + CLI
  Actions 33253394201 / 430 tests

PR #37 -> d69b2ff49f984331b6753bcd9274ea9a298ce798
  full-baseline -> WATERMARK bootstrap evidence contract
  Actions 33253581049 / 441 tests

PR #39 -> 014cd334105de6f867b6320509b94147a444a2fa
  strict staged integration evidence merge + CLI/runbook
  Actions 33253817758 / 455 tests
```

Docs checkpoints #33/#36/#38 keep recovery context synchronized between code slices.

## 3. Governing architecture

```text
source semantic truth
  -> immutable DatasetConfig + semantic onboarding selection
  -> capability profile / immutable ExecutionPlan
  -> environment-local physical binding
  -> provider/native capture
  -> CaptureReceipt + native evidence
  -> normalize/order/dedup/DQ
  -> target-operation CAS claim
  -> target mutation + provider-native commit proof when available
  -> reconciliation
  -> downstream checkpoint/state commit
  -> retained exact-release integration evidence
```

Invariants:

```text
capture fidelity <= truthful history fidelity
provider/native cursor != framework downstream semantic checkpoint
provider Completed != framework semantic success
unknown target commit outcome never permits blind re-execution
credentials/runtime DB URLs never belong in retained source-controlled evidence config
```

## 4. Cheatsheet pattern alignment

Canonical detail: `CHEATSHEET_PATTERN_ALIGNMENT.md`.

The external data-engineering cheatsheet is now an acceptance specification. The old framework `CapturePattern` enum mixed source semantics, read strategy, provider technology and Bronze choice. PR #34 added orthogonal dimensions and exact presets for all fourteen cheatsheet semantic rows while preserving the legacy enum through compatibility projection.

Current truth:

```text
all 14 cheatsheet semantic combinations        IMPLEMENTED + CI PROVEN REFERENCE
semantic onboarding / overclaim guardrails      IMPLEMENTED + CI PROVEN REFERENCE
legacy CapturePattern compatibility              retained
```

First-class combinations now include the formerly missing/partial cases:

```text
Full Snapshot -> Snapshot Bronze
Watermark + Lookback -> Raw Append Bronze
Watermark + Lookback + Soft Delete -> Raw Append Bronze
Full Changes -> Current Bronze (explicitly intentionally lossy)
```

Semantic support does not mean every physical provider path is live proven.

## 5. Bootstrap and incremental safety

### Snapshot -> CDC

Existing `capture/bootstrap_cdc.py` requires a complete source-consistent snapshot fenced by retained CDC positions, then ignores snapshot-covered events and applies only positions strictly after the snapshot boundary.

### Full baseline -> WATERMARK

PR #37 adds `capture/bootstrap_watermark.py`:

```text
WatermarkBootstrapEvidence
WatermarkBootstrapPlan
plan_watermark_bootstrap()
plan_first_watermark_batch()
assert_same_watermark_bootstrap()
```

Required evidence:

```text
complete authoritative baseline
baseline consistent through exact boundary W
verified deterministic watermark ordering
post-W changes guaranteed to remain visible after W is committed
```

Strict mode requires deterministic tie-breaker semantics. Lookback mode intentionally rereads overlap and marks idempotent downstream processing as required. A generic timestamp/`updated_at` is not automatically sufficient proof.

## 6. Capture/apply surface

Portable apply/reference coverage:

```text
APPEND
REPLACE
UPSERT
SCD1
SCD2
SNAPSHOT_DIFF
```

Capture/source families include:

```text
FULL / SNAPSHOT
WATERMARK / LOOKBACK / SOFT DELETE
NET CDC
FULL CDC
transaction-log CDC
Debezium/Kafka normalization
Delta CDF normalization
business events
API cursor guardrails
replay-stable file manifests
```

Retroactive/back-dated SCD2 history reconstruction that would rewrite already committed history remains intentionally unsupported/fail-closed unless a future explicit rewrite policy is introduced.

## 7. Fabric/provider execution contracts

Implemented reference/transport/backend scope:

```text
Fabric REST Job Scheduler client
Fabric Data Pipeline backend
Copy Job REST capture transport
Spark Job Definition REST capture transport
Fabric capture observation -> verified CaptureReceipt
Fabric Warehouse target mutation + same-transaction marker proof
provider-neutral target commit tri-state
Debezium/Kafka normalization + retention-aware resume planning
Delta CDF normalization + bounded checkpoint/recovery contracts
```

Important evidence boundary:

```text
Copy/Spark/Pipeline/Warehouse code + fake/provider-contract CI != real Fabric proof
Kafka/Delta adapter tests != live broker/Lakehouse proof
```

## 8. Target-operation and unknown-outcome recovery

Control-plane v4 persists attempt-independent target operation state plus append-only lifecycle evidence.

```text
new               -> EXECUTE
SUCCEEDED         -> SKIP_SUCCEEDED
IN_PROGRESS retry -> RECONCILE_REQUIRED
UNKNOWN retry     -> RECONCILE_REQUIRED
NOT_COMMITTED     -> CAS reopen -> EXECUTE
```

Provider probes resolve only:

```text
COMMITTED
NOT_COMMITTED
UNRESOLVED
```

Fabric Warehouse preferred target transaction:

```text
BEGIN TRAN
  target mutation
  target-side framework operation marker
COMMIT TRAN
```

Marker absence alone is not proof of non-commit. Query history remains secondary diagnostics.

## 9. Relational control plane

`SqlAlchemyControlPlaneRepository` is the production-oriented repository surface. Released artifacts remain the complete immutable `DatasetConfig` truth; SQL stores deployed metadata/config hash plus runtime/evidence state.

Production-candidate profiles:

```text
fabric_sql_database_v1
azure_sql_database_v1
```

Runtime does not silently migrate/provision production schema. Real selected-backend auth/network/concurrency/rollback/CAS certification is still required.

## 10. Approved-environment evidence system

Canonical runbooks:

```text
DEV_INTEGRATION_EVIDENCE.md
INTEGRATION_EVIDENCE_MERGE.md
```

### Evidence spec/manifest

`IntegrationEvidenceSpec` binds checks to exact:

```text
schema version
environment
domain
framework version
release_hash
required/optional check list
```

Required status semantics:

```text
PASS              satisfies required check
FAIL              blocks
NOT_RUN           blocks required check
EXTERNAL_REQUIRED blocks required check
```

Retained fields reject obvious credential material.

### Approved runner / safe first call

`ApprovedIntegrationRunnerConfig` stores only release identity, check IDs, workspace/item UUIDs, profile names and runtime **environment-variable names**. Secret values are runtime-only.

```bash
fabric-framework integration-run-preflight ...
fabric-framework integration-item-smoke-run ...
```

The first live-capable provider path is read-only item identity/authorization smoke. CI proves the runner contract only; no approved live item smoke has yet been retained.

### Staged evidence merge

PR #39 adds:

```bash
fabric-framework integration-evidence-merge \
  --spec evidence-spec.json \
  --input evidence/item-read.json \
  --input evidence/control-plane.json \
  --output evidence/merged.json
```

Rules:

```text
NOT_RUN = absence and may be filled by another stage
one substantive result = retain unchanged
identical duplicate substantive result = allowed
different substantive result for same check = conflict
no latest/PASS-wins/FAIL-wins arbitration
```

`--require-certified` validates before writing. Merge conflict or failed certification does not overwrite an existing output file. Source partial manifests must still be retained.

Correct label:

```text
IMPLEMENTED + CI PROVEN EVIDENCE MERGE CONTRACT
```

## 11. Still unproven in retained approved infrastructure

```text
real enterprise Entra token acquisition
real workspace/item authorization smoke
live Data Pipeline run
live Copy Job capture + post-run observation
live Spark Job Definition capture + post-run observation
real Fabric Warehouse target + marker transaction
ambiguous Warehouse COMMIT/network failure drill
production-approved marker-absence certifier
real Fabric SQL Database / Azure SQL Database certification
live Kafka consumer seek/commit/rebalance if in release scope
live Delta CDF bounded read/retention drill if in release scope
capacity/throttling/gateway behavior
backup/restore, HA/DR, monitoring, retention/governance evidence
complete exact-release approved DEV evidence bundle
```

Never promote deterministic CI/reference evidence to `FABRIC PROVEN`, `FABRIC WAREHOUSE PROVEN`, `PRODUCTION DB PROVEN`, `KAFKA PROVEN` or equivalent.

## 12. Exact next implementation/execution sequence

1. add an environment-variable-driven approved-run **control-plane certification runner**:
   - selected check must come from exact runner config/spec;
   - database URL read only from configured runtime env var;
   - explicit conformance/mutation authorization;
   - reuse `certify_control_plane_backend`;
   - retain safe certification report;
   - project result into a partial integration manifest;
2. replace placeholder DEV release hash/item UUIDs with the exact candidate values;
3. run staged read-only preflight and real `integration-item-smoke-run` under approved identity;
4. run real control-plane certification against the selected Fabric SQL Database/Azure SQL Database candidate;
5. merge retained partial manifests with `integration-evidence-merge`;
6. only after read-only + DB prerequisites pass, explicitly authorize representative Pipeline/Copy/Spark checks;
7. execute real Warehouse target+marker transaction and ambiguous COMMIT failure drill;
8. assemble exact-release evidence and pass `integration-evidence-validate --require-certified`;
9. prove Kafka/Delta live only if included in the `0.4.0` public product promise;
10. run exact-candidate code/docs/evidence audit and only then decide whether to release `0.4.0`.

## 13. Repository boundaries

```text
fabric-data-framework
  reusable semantics/runtime/transports/evidence/package

fabric-customer
  domain/business config + bounded extensions

fabric-infra
  optional capacity/workspace/infrastructure lifecycle
```

Do not force `fabric-customer` to consume unreleased `0.4.0` as a stable dependency yet.

## 14. Canonical recovery order

For a new conversation, read:

```text
README.md
CURRENT_STATUS.md
CHEATSHEET_PATTERN_ALIGNMENT.md
PRODUCTION_READINESS_AUDIT.md
DEV_INTEGRATION_EVIDENCE.md
INTEGRATION_EVIDENCE_MERGE.md
GUARANTEE_COVERAGE.md
PROJECT_BLUEPRINT.md
PRODUCTION_REQUIREMENTS.md
CAPTURE_PATTERN_CATALOG.md
TARGET_OPERATION_IDEMPOTENCY.md
PROVIDER_NATIVE_RECOVERY.md
FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md
CONTROL_PLANE_CERTIFICATION.md
RELATIONAL_RUNTIME_REPOSITORY.md
FABRIC_PIPELINE_BACKEND.md
FABRIC_CAPTURE_REST_TRANSPORTS.md
EXECUTION_ENGINE_STRATEGY.md
FABRIC_EXECUTION_MODEL.md
CDC_DESIGN.md
CONTROL_PLANE_DESIGN.md
REPOSITORY_STRUCTURE.md
CICD_DESIGN.md
ECOSYSTEM_BLUEPRINT.md
```

If docs disagree with code/tests, inspect implementation and repair docs before continuing.
