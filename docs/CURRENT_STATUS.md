# Current Status — fabric-data-framework

Status: Canonical recovery checkpoint  
Last updated: 2026-08-29

## Release gate

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
latest main baseline  = 395736a3a400480da5876a43591961c478426314
latest full CI        = Actions 33255472348
full test baseline    = 477
```

**Do not publish `0.4.0` yet.** Portable semantics, runtime contracts and approved-runner surfaces are broad. The remaining gate is retained exact-release approved real-environment evidence plus required enterprise controls.

## Release-significant merged sequence

```text
PR #17  durable target-operation journal / control-plane v4
PR #19  provider-native downstream recovery contracts
PR #21  production control-plane backend certification contract
PR #22  Fabric REST Job Scheduler + Data Pipeline backend
PR #24  SQLAlchemy relational runtime repository
PR #26  concrete Copy Job + Spark Job Definition REST transports
PR #28  Fabric Warehouse same-transaction target commit proof
PR #30  approved DEV integration evidence harness
PR #32  approved-run preflight + read-only item smoke runner
        Actions 33251177339 / 407 tests
PR #34  orthogonal cheatsheet semantics + exact 14 presets
        Actions 33253215030 / 419 tests
PR #35  semantic onboarding validation + CLI
        Actions 33253394201 / 430 tests
PR #37  full-baseline -> WATERMARK bootstrap
        Actions 33253581049 / 441 tests
PR #39  strict staged integration evidence merge
        Actions 33253817758 / 455 tests
PR #41  approved production control-plane certification runner
        Actions 33254804867 / 466 tests
PR #43  approved Fabric Pipeline evidence runner + persistent provider-error redaction
        Actions 33255472348 / 477 tests
```

Docs checkpoints keep recovery context synchronized between code slices.

## Governing architecture and invariants

```text
source semantic truth
  -> immutable DatasetConfig + semantic onboarding selection
  -> capability profile / immutable ExecutionPlan
  -> environment-local physical binding
  -> provider/native capture or orchestration
  -> verified receipt/native evidence or durable framework outcome
  -> normalize/order/dedup/DQ/apply
  -> target-operation commit proof / reconciliation
  -> downstream checkpoint/state commit
  -> retained exact-release integration evidence
```

Invariants:

```text
capture fidelity <= truthful history fidelity
provider/native cursor != framework downstream semantic checkpoint
provider Completed != framework semantic success
unknown target commit outcome never permits blind re-execution
source-controlled approved-run config stores env-var names, never secret values
mutating approved checks require explicit authorization
contradictory staged reruns are never silently arbitrated
```

## Cheatsheet semantic coverage

Canonical detail: `CHEATSHEET_PATTERN_ALIGNMENT.md`.

At semantic-contract + onboarding-validation level all fourteen cheatsheet rows are first-class and tested. The formerly missing/partial combinations are now explicit:

```text
Full Snapshot -> Snapshot Bronze
Watermark + Lookback -> Raw Append Bronze
Watermark + Lookback + Soft Delete -> Raw Append Bronze
Full Changes -> Current Bronze (intentionally lossy)
```

Legacy `CapturePattern` remains supported through compatibility projection.

## Bootstrap / history safety

Implemented reference contracts:

```text
snapshot -> CDC fenced no-gap/no-double-apply handoff
full baseline -> WATERMARK fenced handoff
```

Watermark bootstrap requires a complete authoritative baseline, exact boundary consistency, deterministic ordering and proof that post-boundary changes remain visible. A generic timestamp is not automatically sufficient.

Retroactive/back-dated SCD2 rewriting remains intentionally unsupported/fail-closed unless a future explicit rewrite policy is introduced.

## Fabric/provider execution contracts

Implemented reference/transport/backend scope:

```text
Fabric REST Job Scheduler
Fabric Data Pipeline backend
Copy Job REST capture transport
Spark Job Definition REST capture transport
Fabric capture observation -> verified CaptureReceipt
Fabric Warehouse target mutation + same-transaction marker
provider-neutral target commit tri-state
Debezium/Kafka normalization + recovery
Delta CDF normalization + bounded recovery
```

Passing deterministic tests does not prove a live provider.

## Target-operation recovery

Control-plane v4 persists attempt-independent target-operation state and append-only lifecycle evidence.

```text
new               -> EXECUTE
SUCCEEDED         -> SKIP_SUCCEEDED
IN_PROGRESS retry -> RECONCILE_REQUIRED
UNKNOWN retry     -> RECONCILE_REQUIRED
NOT_COMMITTED     -> CAS reopen -> EXECUTE
```

Target probes resolve only `COMMITTED`, `NOT_COMMITTED`, or `UNRESOLVED`; ambiguous outcomes never permit blind retry.

Fabric Warehouse preferred transaction:

```text
BEGIN TRAN
  target mutation
  framework target-side operation marker
COMMIT TRAN
```

Marker absence alone is not non-commit proof.

## Relational control plane

`SqlAlchemyControlPlaneRepository` is the production-oriented repository. Released artifacts remain complete immutable DatasetConfig truth; SQL stores deployed config identity plus runtime/evidence state.

Production-candidate profiles:

```text
fabric_sql_database_v1
azure_sql_database_v1
```

Runtime never silently migrates production schema.

## Approved evidence system

Canonical runbooks:

```text
DEV_INTEGRATION_EVIDENCE.md
APPROVED_CONTROL_PLANE_CERTIFICATION.md
APPROVED_PIPELINE_EVIDENCE.md
INTEGRATION_EVIDENCE_MERGE.md
```

### Evidence identity and merge

`IntegrationEvidenceSpec` binds exact environment/domain/framework/release/check list. Required checks certify only on PASS.

PR #39 strict staged merge:

```text
NOT_RUN = absence
one substantive result = retain unchanged
identical substantive duplicate = allowed
different rerun evidence = conflict
no latest/PASS-wins/FAIL-wins arbitration
```

Failed/conflicting merge does not overwrite retained output. Source partial manifests remain retained.

### Read-only item stage

`integration-item-smoke-run` is the safe first live-capable Fabric call. It validates exact binding and returned item identity. CI proves the runner contract only; no live exact-release item evidence is retained yet.

### Control-plane certification stage

PR #41 adds:

```text
integration-control-plane-certify-run
```

Requirements:

```text
exact config/spec identity
production-eligible profile
runtime-only DB URL value
complete IAM/network/restore/HA/monitoring/retention references
explicit conformance-write authorization
existing certify_control_plane_backend(run_conformance=True)
credential-safe retained report
```

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED CONTROL-PLANE CERTIFICATION RUNNER CONTRACT
```

Real selected-backend PASS remains unproven.

### Pipeline execution stage

PR #43 adds:

```text
integration-pipeline-run
```

The runner refuses remote mutation unless the same exact-spec prerequisite manifest already contains:

```text
FABRIC_ITEM_READ PASS
CONTROL_PLANE_CERTIFICATION PASS
selected FABRIC_PIPELINE_RUN NOT_RUN
```

It also validates:

```text
release manifest domain/framework/release hash
exact dataset config bundle hash
selected dataset exists in release bundle
workspace/pipeline item binding
production-eligible relational control-plane profile
Fabric token + control-plane DB runtime inputs
explicit Pipeline execution authorization
```

Before remote invocation the runner records the parent `PipelineRunAudit`, satisfying the real relational child FK path. It reuses `FabricPipelineBackend`; the backend generates the exact `dataset_run_id` passed to the reusable child Pipeline.

PASS requires:

```text
provider status = Completed
exact durable DatasetDispatchOutcome exists for generated dataset_run_id
outcome is terminal
outcome.status = SUCCEEDED
native workspace/item/job/root correlation matches invocation
```

Provider `Completed` with no durable child outcome is retained as FAIL. Any existing substantive Pipeline evidence in the prerequisite manifest blocks automatic rerun.

Credential-like unexpected provider exception text is redacted before persistence to dataset-run audit state.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT
```

No live exact-release Pipeline evidence is retained yet.

## Still unproven in approved infrastructure

```text
enterprise Entra token acquisition
real workspace/item authorization smoke
real Fabric SQL Database / Azure SQL Database certification PASS
real approved Pipeline execution
real Copy Job capture + post-run observation
real bounded Spark execution + post-run observation
real Fabric Warehouse target+marker transaction
ambiguous Warehouse COMMIT/network failure drill
production-approved marker-absence certifier
live Kafka coordination if release scope includes Kafka
live Delta CDF bounded read/retention if release scope includes Delta
capacity/throttling/gateway behavior
backup/restore/HA/DR/monitoring/retention/governance evidence
complete exact-release approved DEV evidence bundle
```

Never promote CI/reference evidence to a live-service evidence label without retained approved execution for the exact release hash.

## Exact next order

Preferred real-evidence path when approved enterprise inputs are available:

1. replace placeholder DEV release hash/item UUIDs with exact candidate values;
2. run staged read-only item preflight and real item smoke;
3. run real production control-plane certification;
4. merge item + control-plane prerequisite evidence;
5. run approved Pipeline evidence stage;
6. run approved Copy Job and bounded Spark capture stages;
7. execute real Warehouse target+marker transaction and ambiguous COMMIT drill;
8. merge all required evidence and pass `integration-evidence-validate --require-certified`;
9. prove Kafka/Delta live only if part of the `0.4.0` public promise;
10. run exact-candidate release audit.

If real enterprise credentials/tenant/database are unavailable in the current execution context, the next reusable implementation slice is an explicitly-authorized **approved Copy Job + Spark capture runner**. It must call the existing `FabricCaptureAdapter.execute_with_evidence()` exactly once and build PASS only from the verified `CaptureReceipt` + native evidence pair.

## Repository boundaries

```text
fabric-data-framework  reusable semantics/runtime/transports/evidence/package
fabric-customer        domain/business config + bounded extensions
fabric-infra           optional capacity/workspace/infrastructure lifecycle
```

Do not force `fabric-customer` to consume unreleased `0.4.0` as stable dependency yet.

## Canonical recovery order

For a new conversation, read:

```text
README.md
CURRENT_STATUS.md
CHEATSHEET_PATTERN_ALIGNMENT.md
PRODUCTION_READINESS_AUDIT.md
DEV_INTEGRATION_EVIDENCE.md
APPROVED_CONTROL_PLANE_CERTIFICATION.md
APPROVED_PIPELINE_EVIDENCE.md
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
