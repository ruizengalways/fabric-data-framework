# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit  
Last updated: 2026-08-29

## 1. Evidence model

This audit keeps four levels separate:

```text
1. portable semantic/runtime implementation
2. deterministic CI/reference proof
3. retained real provider/Fabric/database execution evidence
4. external enterprise controls
```

Green CI proves levels 1/2 only. Executable HTTP/SQL/evidence code is not live provider evidence until approved service runs are retained for the exact environment and release hash.

## 2. Current release state

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
current main          = ad856d864eb5dec35f3c97ec66ca9e920cfa5e28
latest CI             = Actions 33254804867
full test baseline    = 466
```

**Release decision: blocked.** The blocker is now real approved DEV execution/certification and retained enterprise controls, not another broad provider-neutral abstraction.

## 3. Current assessment

```text
Portable semantic implementation                  STRONG / broad reusable slice
Deterministic CI                                  STRONG for implemented slices
Exact 14 cheatsheet semantic patterns             IMPLEMENTED + CI PROVEN reference
Semantic onboarding/overclaim guardrails          IMPLEMENTED + CI PROVEN reference
Snapshot -> CDC bootstrap                         IMPLEMENTED + CI PROVEN reference
Full baseline -> WATERMARK bootstrap              IMPLEMENTED + CI PROVEN reference
APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF     IMPLEMENTED + CI PROVEN reference
Target-operation CAS journal                      IMPLEMENTED + CI PROVEN reference
Provider-native recovery contracts                IMPLEMENTED + CI PROVEN reference
Control-plane certification framework             IMPLEMENTED + CI PROVEN contract
SQLAlchemy relational runtime                     IMPLEMENTED + CI PROVEN relational runtime
Fabric Data Pipeline backend                      IMPLEMENTED + CI PROVEN backend
Copy Job REST transport                           IMPLEMENTED + CI PROVEN transport contract
Spark Job Definition REST transport               IMPLEMENTED + CI PROVEN transport contract
Fabric Warehouse commit proof                     IMPLEMENTED + CI PROVEN provider contract
Approved-environment evidence harness             IMPLEMENTED + CI PROVEN contract
Approved-run preflight/read-only item runner      IMPLEMENTED + CI PROVEN contract
Staged integration evidence merge                 IMPLEMENTED + CI PROVEN evidence merge contract
Approved control-plane certification runner       IMPLEMENTED + CI PROVEN runner contract
Real approved DEV Fabric execution                NOT YET PROVEN
Real production SQL backend                       NOT YET PROVEN
External enterprise controls                      EXTERNAL / NOT YET RETAINED
```

## 4. Latest hardening milestones

```text
PR #32 -> e42dee86db3d4102c7264bc0d1f01f83fb8aade2
Actions 33251177339 / 407 tests
approved-run preflight + read-only Fabric item smoke runner

PR #34 -> 1c7d67bedd125f5fb5e983be791085fd1eaa9b0e
Actions 33253215030 / 419 tests
orthogonal cheatsheet semantics + exact 14 presets

PR #35 -> bf215fcb3538f9806b4002d2f154dbd46ae19412
Actions 33253394201 / 430 tests
semantic onboarding validation + CLI

PR #37 -> d69b2ff49f984331b6753bcd9274ea9a298ce798
Actions 33253581049 / 441 tests
full-baseline -> WATERMARK bootstrap

PR #39 -> 014cd334105de6f867b6320509b94147a444a2fa
Actions 33253817758 / 455 tests
strict staged integration evidence merge + CLI/runbook

PR #41 -> ad856d864eb5dec35f3c97ec66ca9e920cfa5e28
Actions 33254804867 / 466 tests
approved production control-plane certification runner + CLI/runbook
```

Earlier provider/runtime baselines remain:

```text
PR #17 target-operation journal
PR #19 provider-native recovery
PR #21 control-plane certification contract
PR #22 Fabric Pipeline backend
PR #24 SQLAlchemy runtime repository
PR #26 Copy Job + Spark Job Definition transports
PR #28 Fabric Warehouse same-transaction marker proof
PR #30 approved DEV evidence harness
```

## 5. Capture semantics and history truth

The framework separates source semantics, change granularity, read strategy, delete semantics, Bronze meaning and provider family.

At semantic/onboarding level all fourteen cheatsheet rows are first-class. The framework explicitly prevents common history overclaims:

```text
watermark/current state
  -> observed-change history only
  -> physical deletes absent unless another signal exists

watermark + soft delete
  -> delete correctness depends on tombstone retention/extraction reliability

net CDC
  -> batch/window-grain history
  -> intermediate changes already collapsed cannot be reconstructed

snapshot history/diff
  -> snapshot-grain history only

full ordered CDC/log/Debezium/CDF
  -> full captured event history only when order/completeness/retention are proven

API/files
  -> SOURCE_DEFINED until payload contract proves stronger semantics
```

SCD2 does not improve capture fidelity.

## 6. Bootstrap readiness

### Snapshot -> CDC

Provider-neutral fenced handoff exists and is deterministic CI proven.

### Full baseline -> WATERMARK

PR #37 requires explicit evidence that:

```text
baseline is complete
baseline is consistent through exact boundary W
watermark ordering is deterministic
post-W changes remain visible after W is committed
```

Strict mode uses a deterministic composite boundary. Lookback mode intentionally rereads overlap and requires idempotent downstream handling.

A generic timestamp column is not automatically certified as a safe bootstrap source contract.

## 7. Fabric capture/orchestration readiness

### Pipeline backend

Implemented REST execution backend requires provider terminal state plus exact durable framework dataset outcome. Fabric `Completed` alone is not semantic success.

### Copy Job / Spark Job Definition

Concrete item-specific REST transports exist. Successful framework capture requires provider-specific post-run observation to prove rows/landing/bounds/native progress before `CaptureReceipt`.

Correct current label:

```text
IMPLEMENTED + CI PROVEN TRANSPORT/BACKEND CONTRACT
```

No live exact-release Pipeline/Copy/Spark run is retained yet.

## 8. Fabric Warehouse target commit readiness

Preferred target transaction:

```text
BEGIN TRAN
  target mutation
  framework target-side operation marker
COMMIT TRAN
```

The control-plane CAS journal remains execution/retry authority. The marker is independent commit proof, not a distributed lock.

Probe rules:

```text
matching marker -> COMMITTED
marker absent -> UNRESOLVED
marker absent + independently certified no-late-commit proof -> NOT_COMMITTED
```

Marker absence alone never authorizes retry. Real Warehouse transaction and ambiguous COMMIT/network failure drill remain unproven.

## 9. Relational control-plane readiness

`SqlAlchemyControlPlaneRepository` and deterministic backend certification code exist.

Production candidates:

```text
fabric_sql_database_v1
azure_sql_database_v1
```

PR #41 now provides the approved exact-release execution bridge:

```bash
fabric-framework integration-control-plane-certify-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --check-id control-plane.certify \
  --external-evidence evidence/control-plane-external.json \
  --evidence-reference artifact:control-plane-certification \
  --report-output evidence/control-plane-certification-report.json \
  --output evidence/control-plane-partial.json \
  --allow-conformance-writes
```

The source-controlled config stores only the DB URL environment-variable **name**. The actual URL is runtime-only. The runner requires a production-eligible profile, complete enterprise evidence references and explicit conformance-write authorization, then reuses `certify_control_plane_backend(run_conformance=True)` without migrating schema.

Database/driver exceptions are captured by the integration evidence harness and retained only as exception-type failures. Credential-like external/report text is rejected before retention.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED CONTROL-PLANE CERTIFICATION RUNNER CONTRACT
```

Remaining proof is no longer a missing generic runner. It is the actual selected service/driver/auth/network execution and retained PASS.

## 10. Approved DEV evidence readiness

Canonical runbooks:

```text
DEV_INTEGRATION_EVIDENCE.md
APPROVED_CONTROL_PLANE_CERTIFICATION.md
INTEGRATION_EVIDENCE_MERGE.md
```

Implemented:

```text
IntegrationEvidenceSpec / Manifest / deterministic manifest_hash
secret-material rejection
ApprovedIntegrationRunnerConfig
runtime-secret presence-only preflight
explicit mutating-check authorization gate
read-only Fabric item smoke runner
approved production control-plane certification runner
provider-specific evidence result builders
exact-release validation
staged partial-manifest merge
```

### Staged merge

PR #39 allows independent real checks to be retained without rerunning prior successful stages.

```text
NOT_RUN -> absence
one substantive result -> retain
identical substantive duplicate -> accept
contradictory rerun evidence -> conflict
```

No status/timestamp precedence is used. Conflict or failed `--require-certified` does not overwrite the selected output file.

The merged manifest is not a replacement for retaining source partial manifests and evidence references.

### Safe sequencing

The intended first two real stages are now fully represented by CLI contracts:

```text
1. integration-item-smoke-run
2. integration-control-plane-certify-run
```

Only after both are retained successfully should representative mutating Fabric execution commands be authorized.

## 11. Real approved-environment gaps

Still missing retained evidence for the exact candidate:

```text
enterprise Entra token acquisition
real workspace/item authorization
real Fabric SQL Database or Azure SQL Database certification PASS
real Pipeline execution
real Copy Job execution + observation
real bounded Spark execution + observation
real Fabric Warehouse target+marker transaction
ambiguous Warehouse COMMIT/network drill
production-approved marker-absence certifier
live Kafka consumer coordination if in release scope
live Delta CDF bounded read/retention drill if in release scope
capacity/SKU/throttling/gateway behavior
backup/restore/HA/DR/monitoring/retention/governance controls
complete certified exact-release evidence bundle
```

## 12. Next execution / implementation order

Preferred real-evidence order when approved environment inputs are available:

1. set exact DEV candidate release hash and real item UUID bindings;
2. run `integration-run-preflight` for the read-only item check;
3. run live `integration-item-smoke-run` under approved enterprise identity;
4. run live `integration-control-plane-certify-run` against the selected approved DB;
5. merge item + control-plane partial evidence;
6. only after both prerequisites pass, explicitly authorize representative Pipeline/Copy/Spark checks;
7. execute real Warehouse target+marker transaction plus ambiguous COMMIT drill;
8. merge all required evidence and pass `integration-evidence-validate --require-certified`;
9. prove live Kafka/Delta only if part of the `0.4.0` public promise;
10. run exact-candidate release audit.

When real enterprise credentials/tenant/database are unavailable to the current execution context, the next reusable code slice is an explicitly-authorized approved Pipeline execution runner. It must reuse the existing Pipeline backend and retained durable framework dataset outcome; provider `Completed` alone must never produce PASS.

## 13. External controls this repo must not fake

```text
capacity/SKU/throttling
tenant settings
workspace/domain provisioning
Entra/RBAC
private networking/gateway
authorized secret store
source CDC/CDF retention configuration
broker/database/API access
backup/restore + DR
monitoring/on-call
privacy/retention/governance/change controls
```

These must be retained as enterprise/platform evidence rather than synthesized by unit tests.

## 14. Release gate

`0.4.0` may be considered only when exact candidate code/tests/docs and retained approved evidence agree. Until then:

```text
CI PROVEN != FABRIC PROVEN
CI PROVEN != PRODUCTION DB PROVEN
provider contract != approved live service evidence
```
