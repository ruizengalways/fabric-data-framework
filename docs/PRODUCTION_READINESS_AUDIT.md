# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-29

## Evidence model

This audit separates:

1. portable semantic implementation;
2. deterministic CI/reference proof;
3. real provider/Fabric execution evidence;
4. external enterprise controls.

Green Python CI proves levels 1/2 only. Executable HTTP code and fake-transport tests are not equivalent to an approved real Fabric run.

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
Production SQL repository wiring         NOT YET IMPLEMENTED/PROVEN
Real Fabric/Kafka/Delta execution        NOT YET PROVEN
External enterprise controls             EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest validated merged implementation:

```text
650b7d30b2e31e21d01c56465e8871b91aae4779
PR #22 validation: GitHub Actions 33246151126
344 tests
Python 3.11 + 3.13 + wheel/static checks green
Fabric REST + Data Pipeline backend + fail-closed framework outcome handoff
```

Previous merged production-control-plane contract:

```text
6377eafd4875c3cfe1d7bf21a982f6c11d47aea1
PR #21 validation: GitHub Actions 33241251160
332 tests
production backend profiles + transaction/CAS certification + external evidence gates
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
| Typed operator status/CLI | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Backend certification profiles | Yes | Yes | No real mssql candidate run | IMPLEMENTED/CI PROVEN contract |
| Transaction + target-operation + CDC CAS certification probes | Yes | Yes | No real mssql candidate run | IMPLEMENTED/CI PROVEN contract |
| Fabric REST on-demand job client | Yes | Yes | No live Fabric call | IMPLEMENTED/CI PROVEN transport |
| Typed Job Scheduler parameters | Yes | Yes | Tenant/item support not proven | IMPLEMENTED/CI PROVEN transport |
| Retry-After/provider retry evidence | Yes | Yes | No live throttle drill | IMPLEMENTED/CI PROVEN transport |
| Pluggable ready-wave dispatcher | Yes | Yes | N/A | IMPLEMENTED/CI PROVEN |
| Fabric Data Pipeline backend | Yes | Yes | No live Pipeline job | IMPLEMENTED/CI PROVEN backend |
| Remote Completed requires framework outcome | Yes | Yes | No live child handoff | IMPLEMENTED/CI PROVEN |
| Fabric native job/root correlation model | Yes | Yes | No real native IDs | IMPLEMENTED/CI PROVEN model |
| Production SQL `ControlPlaneRepository` | Partial relational primitives only | Reference helpers | No | P0 GAP |
| Live Copy/Spark/Dataflow transports | Contracts only | Fake transport | No | P0 GAP |
| Provider-specific target commit probes | Interface only | Reference probe flow | No | P0 GAP |
| Approved DEV hybrid execution | No | No | No | P0 GAP |

## Fabric Pipeline readiness

Canonical runbook: `docs/FABRIC_PIPELINE_BACKEND.md`.

Implemented execution shape:

```text
framework planner
  -> exact ready wave
  -> FabricPipelineBackend
  -> immutable ExecutionPlan
  -> environment-local FabricPipelineBinding
  -> FabricRestPipelineTransport
  -> POST on-demand item job
  -> require Location / job_instance_id
  -> Retry-After aware polling
  -> terminal provider status
  -> exact durable framework dataset outcome
  -> provider correlation StepRunAudit
```

Deterministically proven:

- bearer-token acquisition is injected rather than hard-coded;
- empty token fails;
- POST path/job identity are typed;
- Job Scheduler parameters include explicit type (`Guid`, `Text`, `Integer`, `Boolean`, etc.);
- provider 429/error payload can retain `errorCode`, `isRetriable` and `Retry-After`;
- malformed `Location` fails;
- unknown future provider status fails;
- `Deduped` is not treated as successful execution of the requested framework attempt;
- `Completed` requires an exact matching terminal framework `dataset_run_id` outcome;
- native job/root/workspace/item/plan correlation is represented in step evidence;
- provider-side parent failure is recorded before step evidence to respect relational FK ordering;
- backend result membership must exactly match the planner ready wave.

Still not proven:

- actual Entra token acquisition in the target tenant;
- workspace/item authorization;
- Data Pipeline per-run parameter support for the selected item/job type;
- live REST POST/poll behavior;
- real `job_instance_id` and `rootActivityId` retention;
- child SJD/Notebook/native activity using released wheels;
- child/parent handoff through a production SQL repository;
- Fabric throttling/capacity/gateway behavior.

Correct label: `IMPLEMENTED + CI PROVEN TRANSPORT/BACKEND`, not `FABRIC PROVEN`.

## Control-plane readiness

Current schema is v4:

```text
v1 initial control plane
v2 execution/order/capture/recovery/CDC
v3 append identity
v4 durable target-operation journal
```

PR #21 defines three backend profiles:

```text
sqlite_reference_v1       reference-only
fabric_sql_database_v1    production candidate
azure_sql_database_v1     production candidate
```

A production candidate must pass exact-schema/table/migration checks plus rollback, target-operation CAS and CDC checkpoint CAS probes, then retain backend-service identity, IAM/access, network, backup/restore, availability/recovery, monitoring/alerting and retention/governance evidence.

What remains is no longer the certification vocabulary; it is the **actual production repository implementation/wiring and real candidate execution**.

The old `ControlPlaneRepository` Protocol/InMemory adapter and later SQLAlchemy relational primitives must be consolidated behind one production runtime surface. Do not create a third state system.

## Recovery readiness

### Target operation

Ambiguous target mutation remains blocked until evidence resolves to:

```text
COMMITTED     -> SUCCEEDED
NOT_COMMITTED -> retry may reopen through CAS
UNRESOLVED    -> UNKNOWN / blocked
probe error   -> UNKNOWN / blocked
```

### Kafka

Framework CDC checkpoint is semantic truth; consumer-group offset is a transport cursor. Ahead/behind/missing cursors are explicitly realigned. Retention gaps fail closed.

### Delta CDF

The next unapplied commit version must remain within provider earliest/latest availability. Missing retained history fails closed rather than silently skipping.

These remain reference/provider-contract evidence until live services are exercised.

## Source-fidelity readiness

The framework deterministically blocks source-history overclaims, including:

- watermark feed called full event history;
- delete visibility claimed without delete signal;
- net CDC called full event history;
- snapshot history called event-grain;
- full CDC/CDF Bronze merge while claiming append-preserved events;
- lookback watermark without an actual overlap window.

Vendor/source configuration, retention and completeness still require external evidence.

## Remaining release-significant work

### P0 runtime integration

1. implement a production SQLAlchemy `ControlPlaneRepository` over the already-certified relational schema/primitives;
2. provide durable relational dataset-outcome read/write and step/native-evidence paths for Fabric child/parent handoff;
3. implement the selected live Fabric capture transports and provider-specific source/commit probes;
4. wire real Kafka/Delta client calls where those profiles are release scope.

### P0 real evidence

1. run control-plane certification against the chosen real Fabric SQL Database or Azure SQL Database instance;
2. execute approved DEV Fabric Pipeline runs retaining framework + native IDs;
3. retain a successful hybrid capture/apply/reconcile/state path;
4. run failure drills for 429/retry, Pipeline failure/cancel, missing framework outcome, ambiguous target outcome, Kafka cursor drift/retention and Delta CDF retention gaps;
5. retain auth/network/capacity and enterprise control evidence.

### Release decision

Only after exact-candidate code/tests/docs and retained real evidence agree may `0.4.0` be considered for public release.

## External evidence this repo must not fake

Capacity/SKU/throttling, tenant settings, workspace/domain provisioning, Entra/RBAC, gateway/private networking, secret authority, source CDC/CDF enablement/retention, broker/database/API access, backup/restore, monitoring/on-call, privacy/retention and enterprise change controls remain external evidence.

## Release gate

Current decision: **release remains blocked. PR #22 closes the portable/CI Fabric REST + Pipeline backend gap. The next implementation gate is a real relational production runtime repository/handoff, followed by live transports/provider probes and approved DEV evidence.**
