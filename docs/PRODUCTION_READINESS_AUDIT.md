# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit  
Last updated: 2026-08-29

## Evidence model

Keep these levels separate:

```text
1. portable semantic/runtime implementation
2. deterministic CI/reference proof
3. retained real provider/Fabric/database execution evidence
4. external enterprise controls
```

Green CI proves levels 1/2 only. Executable HTTP/SQL/evidence code is not live provider evidence until approved service runs are retained for the exact environment and release hash.

## Current release state

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
current main          = 395736a3a400480da5876a43591961c478426314
latest CI             = Actions 33255472348
full test baseline    = 477
```

**Release decision: blocked.** The blocker is now real approved DEV execution/certification and retained enterprise controls, not another broad provider-neutral abstraction.

## Current assessment

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
Approved evidence harness/preflight               IMPLEMENTED + CI PROVEN contract
Read-only Fabric item smoke runner                IMPLEMENTED + CI PROVEN runner contract
Staged integration evidence merge                 IMPLEMENTED + CI PROVEN merge contract
Approved control-plane certification runner       IMPLEMENTED + CI PROVEN runner contract
Approved Fabric Pipeline evidence runner          IMPLEMENTED + CI PROVEN runner contract
Real approved DEV Fabric execution                NOT YET PROVEN
Real production SQL backend                       NOT YET PROVEN
External enterprise controls                      EXTERNAL / NOT YET RETAINED
```

## Latest hardening milestones

```text
PR #32  Actions 33251177339 / 407 tests
  approved-run preflight + read-only item smoke

PR #34  Actions 33253215030 / 419 tests
  orthogonal cheatsheet semantics + exact 14 presets

PR #35  Actions 33253394201 / 430 tests
  semantic onboarding + CLI

PR #37  Actions 33253581049 / 441 tests
  full-baseline -> WATERMARK bootstrap

PR #39  Actions 33253817758 / 455 tests
  strict staged integration evidence merge

PR #41  Actions 33254804867 / 466 tests
  approved production control-plane certification runner

PR #43  Actions 33255472348 / 477 tests
  approved Fabric Pipeline evidence runner + provider-exception audit redaction
```

Earlier provider/runtime baselines remain PR #17/#19/#21/#22/#24/#26/#28/#30.

## Capture/history truth

The framework separates source semantics, change granularity, read strategy, delete semantics, Bronze meaning and provider family. All fourteen cheatsheet semantic rows are first-class at semantic/onboarding level.

```text
watermark/current state -> observed-change history ceiling
watermark + soft delete -> delete correctness depends on tombstone retention/extraction
net CDC -> batch/window grain; collapsed intermediate changes cannot be reconstructed
snapshot history/diff -> snapshot grain
full ordered CDC/log/Debezium/CDF -> full captured event fidelity only under proven order/completeness/retention
API/files -> SOURCE_DEFINED until payload contract proves stronger semantics
```

SCD2 never upgrades source fidelity.

## Bootstrap readiness

Provider-neutral deterministic contracts exist for:

```text
snapshot -> CDC
full baseline -> WATERMARK
```

Watermark bootstrap requires complete baseline, exact boundary consistency, deterministic ordering and post-boundary visibility proof. A generic timestamp is not automatically safe.

## Fabric Pipeline readiness

The established `FabricPipelineBackend` enforces:

```text
remote Fabric terminal state
  + exact generated dataset_run_id
  + durable framework DatasetDispatchOutcome
  -> semantic handoff
```

Fabric `Completed` alone is insufficient.

PR #43 adds the approved exact-release execution bridge:

```bash
fabric-framework integration-pipeline-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/prerequisites-merged.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --check-id fabric.pipeline \
  --dataset-id crm.customer \
  --evidence-reference artifact:pipeline-run \
  --output evidence/pipeline-partial.json \
  --allow-pipeline-execution
```

The runner requires the same exact-spec prerequisite manifest to already contain:

```text
FABRIC_ITEM_READ PASS
CONTROL_PLANE_CERTIFICATION PASS
selected FABRIC_PIPELINE_RUN NOT_RUN
```

It refuses automatic rerun once the selected Pipeline check is substantive. It validates release manifest identity/config bundle hash, physical binding, production-eligible relational profile, runtime token/DB prerequisites and explicit mutation authorization before retrieving the DB URL value.

It creates the parent `PipelineRunAudit` before remote execution so the real relational child `dataset_run` FK path is valid. PASS requires provider `Completed` plus the exact durable child outcome with `SUCCEEDED` status and matching native correlation.

Credential-like unexpected provider exception text is redacted before persistence into dataset-run audit state.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT
```

No live exact-release Fabric Pipeline run is retained yet.

Microsoft currently documents both Data Factory `jobType=Pipeline` on-demand execution and newer DataPipeline-specific execute-job endpoints. PR #43 deliberately reuses the already tested transport rather than silently combining an API migration with the evidence-runner semantic change.

## Copy Job / Spark readiness

Concrete item-specific REST transports and `FabricCaptureAdapter.execute_with_evidence()` already exist. Provider `Completed` does not prove rows/landing/bounds/native checkpoint; successful capture requires the provider-specific post-run observation resolver and a verified `CaptureReceipt` + native evidence pair.

The next reusable runner must preserve those requirements and add the same staged prerequisite/rerun/authorization discipline used by Pipeline.

## Fabric Warehouse target commit readiness

Preferred transaction:

```text
BEGIN TRAN
  target mutation
  framework target-side operation marker
COMMIT TRAN
```

The control-plane target-operation CAS remains execution/retry authority. Matching marker proves COMMITTED; marker absence remains UNRESOLVED unless an independently certified no-late-commit proof exists. Real transaction and ambiguous COMMIT/network drill remain unproven.

## Relational control-plane readiness

Production candidates remain:

```text
fabric_sql_database_v1
azure_sql_database_v1
```

PR #41 provides the approved execution bridge. Real selected-backend service/driver/auth/network execution and retained production-certified PASS remain missing.

## Approved evidence sequencing

Implemented stages:

```text
integration-run-preflight
integration-item-smoke-run
integration-control-plane-certify-run
integration-evidence-merge
integration-pipeline-run
integration-evidence-validate
```

Safe intended order:

```text
item read PASS
  -> control-plane certification PASS
  -> strict prerequisite evidence merge
  -> approved Pipeline run
  -> Copy/Spark capture stages
  -> Warehouse target/commit failure drills
  -> complete exact-release manifest
```

## Real approved-environment gaps

Still missing retained evidence for the exact candidate:

```text
enterprise Entra token acquisition
real workspace/item authorization
real Fabric SQL Database or Azure SQL Database certification PASS
real approved Pipeline execution
real Copy Job execution + post-run observation
real bounded Spark execution + observation
real Fabric Warehouse target+marker transaction
ambiguous Warehouse COMMIT/network drill
production-approved marker-absence certifier
live Kafka consumer coordination if release scope includes Kafka
live Delta CDF bounded read/retention if release scope includes Delta
capacity/SKU/throttling/gateway behavior
backup/restore/HA/DR/monitoring/retention/governance controls
complete certified exact-release evidence bundle
```

## Next order

When approved real inputs are available:

1. set exact DEV candidate release hash and real item UUIDs;
2. run real item smoke;
3. run real production control-plane certification;
4. merge prerequisites;
5. run approved Pipeline stage;
6. run approved Copy Job and Spark capture stages;
7. execute Warehouse target+marker and ambiguous COMMIT drill;
8. merge all required evidence and pass `--require-certified`;
9. prove Kafka/Delta only if part of `0.4.0` public scope;
10. run exact-candidate release audit.

If live inputs are unavailable to the current execution context, the next implementation slice is the approved Copy Job + Spark capture runner based on `execute_with_evidence()`.

## External controls this repo must not fake

Capacity/SKU/throttling, tenant/workspace provisioning, Entra/RBAC, private networking/gateway, secret authority, source CDC/CDF retention configuration, broker/database/API access, backup/restore/DR, monitoring/on-call, privacy/retention/governance and enterprise change controls remain external evidence.

## Release gate

`0.4.0` may be considered only when exact candidate code/tests/docs and retained approved evidence agree.

```text
CI PROVEN != FABRIC PROVEN
CI PROVEN != PRODUCTION DB PROVEN
provider contract != approved live service evidence
```
