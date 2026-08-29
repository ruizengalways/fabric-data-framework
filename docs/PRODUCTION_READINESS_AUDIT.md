# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-29

## Evidence model

This audit separates:

1. portable semantic implementation;
2. deterministic CI/reference proof;
3. real provider/Fabric execution evidence;
4. external enterprise controls.

Green CI proves levels 1/2 only. Executable HTTP/SQL code against deterministic reference stores does not become real Fabric/production-database evidence until approved service runs are retained.

## Current assessment

```text
Portable semantic implementation        STRONG / broad core product slice
Deterministic certification              STRONG for implemented slices
Mainstream source onboarding             IMPLEMENTED / CI PROVEN reference
Target-operation journal                 IMPLEMENTED / CI PROVEN reference
Provider-native recovery contracts       IMPLEMENTED / CI PROVEN reference
Control-plane certification framework    IMPLEMENTED / CI PROVEN contract
Fabric REST Job Scheduler transport      IMPLEMENTED / CI PROVEN transport
Fabric Data Pipeline backend             IMPLEMENTED / CI PROVEN backend
SQLAlchemy runtime repository            IMPLEMENTED / CI PROVEN relational runtime
Real Fabric/Kafka/Delta execution        NOT YET PROVEN
Real production SQL backend              NOT YET PROVEN
External enterprise controls             EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest validated merged implementation:

```text
2fa8e2c4bc6875b529a4968694722d4108a635ff
PR #24 validation: GitHub Actions 33246594883
350 tests
Python 3.11 + 3.13 + wheel/static checks green
SQLAlchemy runtime repository + durable Fabric child/parent outcome handoff
```

Previous merged Fabric orchestration baseline:

```text
650b7d30b2e31e21d01c56465e8871b91aae4779
PR #22 validation: GitHub Actions 33246151126
344 tests
Fabric REST + Data Pipeline backend + fail-closed framework outcome handoff
```

`v0.3.0` remains the latest public release. **Do not publish v0.4.0 yet.**

## Capability assessment

| Capability | Code | CI/reference proof | Real service | Assessment |
|---|---:|---:|---:|---|
| Typed metadata/effective config | Yes | Yes | N/A | IMPLEMENTED |
| 14-pattern source-fidelity catalog | Yes | Yes | N/A | IMPLEMENTED reference |
| Capture onboarding CI claims/examples | Yes | Yes | N/A | IMPLEMENTED/CI PROVEN |
| WATERMARK + overlap | Yes | Yes | No | IMPLEMENTED reference |
| APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF | Yes | Yes | No | IMPLEMENTED reference |
| Bronze/DQ/quarantine/accounting | Yes | Yes | No production payload store | IMPLEMENTED reference |
| Canonical CDC + downstream checkpoint | Yes | Yes | No | IMPLEMENTED reference |
| Debezium/Kafka normalization | Yes | Yes | No live broker | ADAPTER/REFERENCE |
| Kafka cursor coordination/retention safety | Yes | Yes | No live broker drill | IMPLEMENTED/CI PROVEN reference |
| Delta CDF normalization/resume safety | Yes | Yes | No live Lakehouse CDF | IMPLEMENTED/CI PROVEN reference |
| Fabric capture adapters | Yes | Fake transport | No | ADAPTER CONTRACT |
| Durable target-operation identity/CAS | Yes | Yes | No live target | IMPLEMENTED/CI PROVEN reference |
| Target commit-probe contract | Yes | Yes | No native provider lookup | IMPLEMENTED/CI PROVEN reference |
| Control-plane v4 schema/migrations | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Backend certification profiles/probes | Yes | Yes | No real mssql candidate run | IMPLEMENTED/CI PROVEN contract |
| Fabric REST on-demand job client | Yes | Yes | No live Fabric call | IMPLEMENTED/CI PROVEN transport |
| Fabric Data Pipeline backend | Yes | Yes | No live Pipeline job | IMPLEMENTED/CI PROVEN backend |
| Remote Completed requires framework outcome | Yes | Yes | No live child handoff | IMPLEMENTED/CI PROVEN |
| Fabric native job/root correlation model | Yes | Yes | No real native IDs | IMPLEMENTED/CI PROVEN model |
| SQLAlchemy `ControlPlaneRepository` | Yes | Yes | No real Fabric/Azure SQL | IMPLEMENTED/CI PROVEN relational runtime |
| Released-config -> deployed-hash validation | Yes | Yes | No real SQL backend | IMPLEMENTED/CI PROVEN |
| Durable relational DatasetDispatchOutcome | Yes | Yes | No cross-process real DB | IMPLEMENTED/CI PROVEN |
| Fabric Completed -> SQL outcome -> native step handoff | Yes | Yes | No live Fabric job | IMPLEMENTED/CI PROVEN reference integration |
| Live Copy/Spark/Dataflow transports | Contracts/partial REST primitives | No live service | No | P0 GAP |
| Provider-specific target commit probes | Interface only | Reference probe flow | No | P0 GAP |
| Approved DEV hybrid execution | No | No | No | P0 GAP |

## Relational runtime readiness

Canonical runbook: `docs/RELATIONAL_RUNTIME_REPOSITORY.md`.

PR #24 consolidates the old runtime repository Protocol and later SQLAlchemy persistence into one production-oriented runtime surface.

Config model:

```text
released domain artifact -> complete immutable DatasetConfig
relational control plane  -> normalized deployed metadata + config_hash + runtime evidence
```

Every runtime config read requires the SQL `config_hash` and domain to match the released artifact. The framework does not reconstruct missing historic normalized fields with invented values.

Runtime construction requires the exact already-migrated schema; migration remains a separate explicit deployment step.

Deterministically proven SQL paths include:

```text
pipeline lifecycle update
dataset lifecycle update
step lifecycle/details update
durable DatasetDispatchOutcome read
capture receipt insert
reconciliation insert
quarantine insert
attempt lineage insert
reprocess request lifecycle
```

The SQL adapter deliberately does not duplicate the stronger target-operation/CDC CAS state machines already implemented in dedicated modules.

A deterministic integration test proves:

```text
child writes terminal DatasetRunAudit to SQL
provider returns Fabric Completed
parent reads exact DatasetDispatchOutcome
parent attaches Fabric job/root StepRunAudit details
```

Non-NORMAL run modes are retained in `pipeline_run.run_mode`.

Correct label: `IMPLEMENTED + CI PROVEN RELATIONAL RUNTIME`, not `PRODUCTION DB PROVEN`.

## Fabric Pipeline readiness

Canonical runbook: `docs/FABRIC_PIPELINE_BACKEND.md`.

Implemented shape:

```text
framework planner
  -> exact ready wave
  -> FabricPipelineBackend
  -> immutable ExecutionPlan
  -> environment-local FabricPipelineBinding
  -> Fabric REST Job Scheduler
  -> terminal provider status
  -> exact durable relational framework outcome
  -> provider correlation StepRunAudit
```

Still not proven:

- actual Entra token acquisition in the target tenant;
- workspace/item authorization;
- selected Data Pipeline parameter acceptance;
- live REST POST/poll behavior;
- real job/root IDs;
- real child SJD/Notebook/native activity;
- Fabric throttling/capacity/gateway behavior.

Correct label: `IMPLEMENTED + CI PROVEN TRANSPORT/BACKEND`, not `FABRIC PROVEN`.

## Control-plane readiness

Current schema remains v4:

```text
v1 initial control plane
v2 execution/order/capture/recovery/CDC
v3 append identity
v4 durable target-operation journal
```

Production candidates:

```text
fabric_sql_database_v1
azure_sql_database_v1
```

A real candidate still must pass exact schema/migration checks plus transaction rollback, target-operation CAS, CDC checkpoint CAS and retain backend identity, IAM/access, network, backup/restore, availability/recovery, monitoring/alerting and retention/governance evidence.

The repository implementation now exists; the remaining control-plane gap is **real candidate certification and external evidence**, not missing portable runtime code.

## Provider recovery readiness

### Target operation

```text
COMMITTED     -> SUCCEEDED
NOT_COMMITTED -> CAS reopen may retry
UNRESOLVED    -> UNKNOWN / blocked
probe error   -> UNKNOWN / blocked
```

### Kafka

Framework CDC checkpoint is semantic truth; consumer-group offset is transport state. Ahead/behind/missing cursors are explicitly realigned; retention gaps fail closed.

### Delta CDF

The next unapplied version must remain within provider earliest/latest retained availability. Missing history fails closed.

These are still provider-contract/reference claims until live clients are exercised.

## Remaining release-significant work

### P0 portable/provider integration

1. implement concrete Fabric Copy Job and Spark Job Definition capture transports on documented v1 REST APIs;
2. map native Copy/Spark run evidence into existing capture adapter/CaptureReceipt contracts;
3. add provider-specific target commit/source-position probes where provider evidence supports them;
4. wire real Kafka/Delta client calls if those provider profiles remain in release scope.

### P0 real evidence

1. run control-plane certification against the chosen real Fabric SQL Database or Azure SQL Database instance;
2. execute approved DEV Fabric Pipeline + SQL repository runs retaining framework/native IDs;
3. execute Copy/Spark/native capture paths in DEV;
4. retain successful target/reconciliation/state evidence;
5. run failure drills for provider 429, Pipeline failure/cancel, missing framework outcome, ambiguous commit, Kafka cursor drift/retention and Delta CDF retention gaps;
6. retain auth/network/capacity and enterprise control evidence.

### Release decision

Only after exact-candidate code/tests/docs and retained real evidence agree may `0.4.0` be considered for public release.

## External evidence this repo must not fake

Capacity/SKU/throttling, tenant settings, workspace/domain provisioning, Entra/RBAC, gateway/private networking, secret authority, source CDC/CDF enablement/retention, broker/database/API access, backup/restore, monitoring/on-call, privacy/retention and enterprise change controls remain external evidence.

## Release gate

Current decision: **release remains blocked. PR #24 closes the portable relational runtime/handoff gap. The next implementation gate is concrete Fabric Copy/Spark capture transports and provider evidence mapping, followed by real DEV execution and production SQL backend certification.**
