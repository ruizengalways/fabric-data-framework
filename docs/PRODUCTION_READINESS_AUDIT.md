# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-29

## Evidence model

This audit separates:

1. portable semantic implementation;
2. deterministic CI/reference proof;
3. real provider/Fabric execution evidence;
4. external enterprise controls.

Green CI proves levels 1/2 only. Executable HTTP/SQL code is not real Fabric/production-database evidence until approved service runs are retained.

## Current assessment

```text
Portable semantic implementation        STRONG / broad core product slice
Deterministic certification              STRONG for implemented slices
Source-fidelity onboarding               IMPLEMENTED / CI PROVEN reference
Target-operation journal                 IMPLEMENTED / CI PROVEN reference
Provider-native recovery contracts       IMPLEMENTED / CI PROVEN reference
Control-plane certification framework    IMPLEMENTED / CI PROVEN contract
Fabric Data Pipeline backend             IMPLEMENTED / CI PROVEN backend
SQLAlchemy runtime repository            IMPLEMENTED / CI PROVEN relational runtime
Copy Job REST capture transport          IMPLEMENTED / CI PROVEN transport contract
Spark Job Definition capture transport   IMPLEMENTED / CI PROVEN transport contract
Provider-specific target commit proof    NEXT P0 / NOT YET IMPLEMENTED
Real Fabric/Kafka/Delta execution        NOT YET PROVEN
Real production SQL backend              NOT YET PROVEN
External enterprise controls             EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest validated merged implementation:

```text
8f23942acd5b03d817e42b97d9f490acc6bee89f
PR #26 validation: GitHub Actions 33247494948
362 tests
Python 3.11 + 3.13 + wheel/static checks green
Copy Job + Spark Job Definition concrete capture REST transports
```

Previous relational runtime baseline:

```text
2fa8e2c4bc6875b529a4968694722d4108a635ff
PR #24 validation: GitHub Actions 33246594883
350 tests
SQLAlchemy runtime repository + durable Fabric child/parent outcome handoff
```

`v0.3.0` remains the latest public release. **Do not publish v0.4.0 yet.**

## Capability assessment

| Capability | Code | CI/reference proof | Real service | Assessment |
|---|---:|---:|---:|---|
| Typed metadata/effective config | Yes | Yes | N/A | IMPLEMENTED |
| 14-pattern source-fidelity catalog | Yes | Yes | N/A | IMPLEMENTED reference |
| Capture onboarding CI claims/examples | Yes | Yes | N/A | IMPLEMENTED/CI PROVEN |
| APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF | Yes | Yes | No | IMPLEMENTED reference |
| Canonical CDC + downstream checkpoint | Yes | Yes | No | IMPLEMENTED reference |
| Kafka cursor coordination/retention safety | Yes | Yes | No live broker drill | IMPLEMENTED/CI PROVEN reference |
| Delta CDF normalization/resume safety | Yes | Yes | No live Lakehouse CDF | IMPLEMENTED/CI PROVEN reference |
| Durable target-operation identity/CAS | Yes | Yes | No live target | IMPLEMENTED/CI PROVEN reference |
| Provider-neutral target commit probe | Yes | Yes | No provider-specific commit proof | IMPLEMENTED/CI PROVEN contract |
| Control-plane v4 schema/migrations | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Backend certification profiles/probes | Yes | Yes | No real mssql candidate run | IMPLEMENTED/CI PROVEN contract |
| Fabric REST Job Scheduler client | Yes | Yes | No live Fabric call | IMPLEMENTED/CI PROVEN transport |
| Fabric Data Pipeline backend | Yes | Yes | No live Pipeline job | IMPLEMENTED/CI PROVEN backend |
| Remote Pipeline Completed requires framework outcome | Yes | Yes | No live child handoff | IMPLEMENTED/CI PROVEN |
| SQLAlchemy `ControlPlaneRepository` | Yes | Yes | No real Fabric/Azure SQL | IMPLEMENTED/CI PROVEN relational runtime |
| Durable relational DatasetDispatchOutcome | Yes | Yes | No cross-process real DB | IMPLEMENTED/CI PROVEN |
| Copy Job specific REST start/status paths | Yes | Yes | No live Copy Job | IMPLEMENTED/CI PROVEN transport contract |
| Copy Job FABRIC_NATIVE progress guardrails | Yes | Yes | No live incremental drill | IMPLEMENTED/CI PROVEN contract |
| Copy Job CDC fidelity documented as net-change constrained | Yes | Yes | Provider semantics not live-certified here | IMPLEMENTED metadata guardrail |
| Spark Job Definition dedicated REST start path | Yes | Yes | No live SJD | IMPLEMENTED/CI PROVEN transport contract |
| Spark framework-bound executionData resolver | Yes | Yes | No real child contract | IMPLEMENTED/CI PROVEN contract |
| Mandatory Copy/Spark post-run observation | Yes | Yes | No real observer | IMPLEMENTED/CI PROVEN contract |
| Invalid local wait settings blocked before remote POST | Yes | Yes | N/A | IMPLEMENTED/CI PROVEN |
| Fabric native job/root correlation | Yes | Yes | No real native IDs | IMPLEMENTED/CI PROVEN model |
| Fabric Warehouse target-native commit proof | No | No | No | P0 GAP |
| Approved DEV hybrid execution | No | No | No | P0 GAP |

## Concrete Fabric capture readiness

Canonical runbook: `docs/FABRIC_CAPTURE_REST_TRANSPORTS.md`.

### Copy Job

The concrete transport uses the current item-specific API shapes for on-demand execution and instance status. The transport requires `FABRIC_NATIVE` progress ownership and rejects framework lower/upper bounds and arbitrary per-run framework parameters.

Native Copy Job incremental progress is provider state. It must not be copied into framework downstream state merely because a provider run completed.

Current product semantics also constrain CDC claims: Copy Job CDC currently documents net-change capture rather than guaranteed preservation of every intermediate change event. Source-fidelity onboarding remains authoritative.

### Spark Job Definition

The concrete SJD transport uses the dedicated Spark on-demand endpoint. Framework-bounded capture requires an explicit resolver from framework request/bounds into the selected released SJD `executionData`; the reusable framework does not invent a universal child command-line convention.

### Post-run observation

A generic Fabric job instance proves native job identity/status/timestamps but not generic rows, landing, exact framework bounds, native incremental checkpoint, snapshot completeness or schema evidence.

Therefore `Completed` requires a provider/item-specific `FabricCaptureObservation` before the existing Fabric capture adapter can produce a `CaptureReceipt`.

Failed/cancelled/deduped provider jobs do not run the success observer. Bounds observed after Spark completion are compared against requested framework bounds and mismatch fails closed.

Correct claim: `IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT`, not `FABRIC PROVEN`.

## Relational runtime readiness

Canonical runbook: `docs/RELATIONAL_RUNTIME_REPOSITORY.md`.

`SqlAlchemyControlPlaneRepository` validates the released immutable `DatasetConfig` against deployed SQL `config_hash` and persists runtime/evidence state. Construction requires an explicitly migrated exact schema and never silently migrates.

Deterministically proven paths include pipeline/dataset/step lifecycle, durable `DatasetDispatchOutcome`, capture receipt, reconciliation, quarantine, attempt lineage and reprocess state.

Correct claim: `IMPLEMENTED + CI PROVEN RELATIONAL RUNTIME`, not `PRODUCTION DB PROVEN`.

## Fabric Pipeline readiness

Canonical runbook: `docs/FABRIC_PIPELINE_BACKEND.md`.

```text
framework planner
  -> ready wave
  -> FabricPipelineBackend
  -> Fabric REST Pipeline job
  -> terminal provider status
  -> exact durable framework outcome
  -> native job/root step evidence
```

`Completed` alone never means framework success.

Correct claim: `IMPLEMENTED + CI PROVEN TRANSPORT/BACKEND`, not `FABRIC PROVEN`.

## Control-plane readiness

Current control-plane schema is v4. Production candidate profiles remain:

```text
fabric_sql_database_v1
azure_sql_database_v1
```

The portable runtime repository and certification suite now exist. The remaining control-plane release gate is execution against a real selected SQL backend plus retained identity/IAM/network/backup/DR/monitoring/governance evidence.

## Next P0: Fabric Warehouse target commit proof

The provider-neutral `TargetCommitProbe` exists, but a Fabric Warehouse implementation is still missing.

Current Microsoft Fabric Warehouse product semantics make the preferred proof design:

```text
BEGIN TRAN
  target mutation
  framework-owned target-side operation marker
COMMIT TRAN
```

The marker uses the existing semantic `TargetOperationIntent.operation_key`. Because Warehouse explicit transactions are ACID, the target mutation and marker can be one atomic target-side unit when both statements are supported in the same explicit transaction.

After an ambiguous client/network outcome, a read-only provider probe should inspect the target-side marker:

```text
marker committed and identity matches -> COMMITTED
absence + independently certified no-open/delayed-commit boundary -> NOT_COMMITTED
otherwise -> UNRESOLVED
```

**Absence alone must not automatically mean `NOT_COMMITTED`.** That inference requires provider/session recovery semantics to be certified for the failure boundary.

Warehouse Query Insights/query labels can retain `distributed_statement_id`, label and command as secondary correlation. They cannot be the sole immediate commit truth because completed query history can take up to 15 minutes to appear.

This target-side marker is provider-native proof, not a second framework control plane. The durable framework target-operation journal remains the semantic retry gate.

## Remaining release-significant work

### P0 portable/provider integration

1. implement Fabric Warehouse atomic target-operation marker contract and provider-specific commit probe;
2. add source-position discovery where selected providers expose authoritative positions;
3. wire real Kafka/Delta clients if those profiles remain release scope.

### P0 real evidence

1. run control-plane certification against the selected real Fabric SQL Database/Azure SQL Database candidate;
2. execute approved DEV Fabric Pipeline + SQL repository flow retaining framework/native IDs;
3. execute real Copy Job and Spark Job Definition capture paths with retained observation evidence;
4. exercise Warehouse ambiguous target-commit failure boundaries and prove marker/query correlation behavior;
5. run Kafka cursor and Delta retention failure drills if included in release scope;
6. retain auth/network/capacity and enterprise-control evidence.

### Release decision

Only after exact-candidate code/tests/docs and retained real evidence agree may `0.4.0` be considered for public release.

## External evidence this repo must not fake

Capacity/SKU/throttling, tenant settings, workspace/domain provisioning, Entra/RBAC, gateway/private networking, secret authority, source CDC/CDF enablement/retention, broker/database/API access, backup/restore, monitoring/on-call, privacy/retention and enterprise change controls remain external evidence.

## Release gate

Current decision: **release remains blocked. PR #26 closes the portable concrete Copy Job / Spark Job Definition REST transport gap. The next implementation gate is Fabric Warehouse target-native commit proof, followed by approved live DEV executions and production SQL backend certification.**
