# Current Status — fabric-data-framework

Last updated: 2026-08-29

## Current phase and release gate

`v0.3.0` remains the latest immutable public framework release. Source version `0.4.0` is an unreleased development line. **Do not publish v0.4.0 yet.**

Latest release-significant merged baselines:

```text
PR #17 -> 83a27d9350a6018abc272e9afebdef5d660de519
durable target-operation idempotency / control-plane v4 journal
315 tests

PR #19 -> fd6d5039a5852e32d823b178970816ff292472a2
provider-native downstream recovery contracts
322 tests

PR #21 -> 6377eafd4875c3cfe1d7bf21a982f6c11d47aea1
production control-plane backend certification contract
332 tests

PR #22 -> 650b7d30b2e31e21d01c56465e8871b91aae4779
Fabric REST Job Scheduler + Data Pipeline backend
344 tests

PR #24 -> 2fa8e2c4bc6875b529a4968694722d4108a635ff
SQLAlchemy production-oriented runtime repository + relational Fabric child/parent handoff
350 tests

PR #26 -> 8f23942acd5b03d817e42b97d9f490acc6bee89f
concrete Fabric Copy Job + Spark Job Definition capture REST transports
GitHub Actions 33247494948
362 tests
Python 3.11 + 3.13 + static + wheel SUCCESS
```

The reusable framework now has portable/reference semantics, durable target-operation state, provider recovery contracts, a certified control-plane contract, a concrete Fabric Pipeline execution backend, a SQLAlchemy runtime repository, and concrete Copy Job / Spark Job Definition capture transports. Release remains blocked on provider-specific target commit/source-position proof, real Fabric/Kafka/Delta executions, real production SQL backend certification and enterprise evidence.

## Core product model

```text
source fidelity classification
  -> immutable DatasetConfig
  -> capability profile / ExecutionPlan
  -> environment-local physical binding
  -> capture/execution transport
  -> durable CaptureReceipt / runtime evidence
  -> target operation
  -> reconciliation / DQ
  -> framework checkpoint/state commit
```

**Capture fidelity is an upper bound on history fidelity.** Provider-native progress never silently becomes framework downstream state.

## Durable target-operation model

Control-plane v4 persists attempt-independent target mutation state:

```text
target_operation        expected-version CAS current state
target_operation_event  append-only lifecycle evidence
```

Fail-closed claim behavior:

```text
new               -> EXECUTE
SUCCEEDED         -> SKIP_SUCCEEDED
IN_PROGRESS retry -> RECONCILE_REQUIRED
UNKNOWN retry     -> RECONCILE_REQUIRED
NOT_COMMITTED     -> CAS reopen -> EXECUTE
```

Provider probes may resolve only to `COMMITTED`, `NOT_COMMITTED` or `UNRESOLVED`. Unknown outcome never grants blind retry.

Canonical runbook: `TARGET_OPERATION_IDEMPOTENCY.md`.

## Provider-native recovery model

Framework downstream checkpoint remains semantic truth.

- Kafka consumer-group offsets are transport cursors; `MISSING`, `BEHIND`, `ALIGNED`, `AHEAD` are realigned to framework progress and retention gaps fail closed.
- Delta CDF resume planning requires the next unapplied version to remain inside provider earliest/latest retained availability.
- target commit probes persist `COMMITTED`, `NOT_COMMITTED` or `UNRESOLVED` evidence into the durable operation journal.

Canonical runbook: `PROVIDER_NATIVE_RECOVERY.md`.

## Production control-plane / relational runtime

Production-candidate certification profiles:

```text
sqlite_reference_v1       reference-only forever
fabric_sql_database_v1    production candidate
azure_sql_database_v1     production candidate
```

`SqlAlchemyControlPlaneRepository` is now the production-oriented runtime repository surface. Runtime construction requires an explicitly migrated exact schema; it never silently migrates.

Configuration truth remains:

```text
released domain artifact -> complete immutable DatasetConfig
relational control plane  -> deployed metadata + config_hash + runtime/evidence state
```

Every SQL-backed dataset read validates deployed `config_hash` and domain against the released artifact.

Durable runtime evidence includes pipeline/dataset/step lifecycle, `DatasetDispatchOutcome`, capture receipt, reconciliation, quarantine, attempt lineage and reprocess state. Dedicated CAS modules remain authoritative for target-operation and CDC state.

Canonical runbooks:

```text
CONTROL_PLANE_CERTIFICATION.md
RELATIONAL_RUNTIME_REPOSITORY.md
```

## Fabric Pipeline backend

```text
framework ready wave
  -> FabricPipelineBackend
  -> Fabric REST on-demand Pipeline job
  -> Location/job-instance/root correlation
  -> terminal remote status
  -> exact durable SQL DatasetDispatchOutcome
```

Critical invariant:

> **Fabric `Completed` is not framework success.**

The exact `dataset_run_id` must have a durable terminal framework outcome. Missing/mismatched/non-terminal evidence fails closed. `Deduped` is not treated as successful execution of the requested framework attempt.

Canonical runbook: `FABRIC_PIPELINE_BACKEND.md`.

## Concrete Fabric capture transports

PR #26 implements concrete REST transport contracts for:

```text
FABRIC_COPY_JOB -> ExecutionKind.FABRIC_COPY_JOB
SPARK           -> ExecutionKind.SPARK_JOB_DEFINITION
```

### Copy Job

Current transport shape:

```text
POST /workspaces/{workspace}/items/{copyJob}/jobs/instances?jobType=Execute
GET  /workspaces/{workspace}/copyJobs/{copyJob}/jobs/instances/{jobInstance}
```

The default Copy Job capability is `FABRIC_NATIVE` progress ownership. The transport rejects framework lower/upper source bounds and arbitrary per-run framework parameters. Native Copy Job incremental progress is provider state; it is not substituted for the framework downstream checkpoint.

Current Copy Job CDC product semantics must also remain source-fidelity constrained: the provider currently documents net-change CDC, not guaranteed full intermediate row-change history.

### Spark Job Definition

Current transport shape:

```text
POST /workspaces/{workspace}/sparkJobDefinitions/{sjd}/jobs/sparkjob/instances
```

Framework-bounded Spark capture requires an explicit `FabricSparkExecutionDataResolver` to translate bounds/runtime values into the selected released SJD `executionData` contract. The framework does not invent a universal command-line syntax.

### Mandatory post-run observation

A provider job `Completed` proves job identity/status, but generic job-instance status does not generically prove rows, landing reference, exact framework source bounds, native incremental checkpoint, snapshot completeness or schema evidence.

Therefore successful Copy/Spark execution requires `FabricCaptureObservation` before `FabricNativeRunEvidence` can become a `CaptureReceipt`. Failed/cancelled/deduped jobs never invoke the success observer.

Native diagnostics retain workspace/item/job/root/status/failure correlation. Invalid timeout/poll settings are validated before any remote POST, preventing an invalid local invocation from creating an orphan Fabric job.

Canonical runbook: `FABRIC_CAPTURE_REST_TRANSPORTS.md`.

Correct evidence label:

```text
IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT
```

not `FABRIC PROVEN`.

## Implemented development runtime

Current `main` includes:

- immutable metadata/effective config and bounded runtime overrides;
- 14-pattern source-fidelity onboarding catalog;
- independent capture/apply semantics and progress ownership;
- immutable ExecutionPlan + capability profiles;
- APPEND, REPLACE, UPSERT, SCD1, SCD2, SNAPSHOT_DIFF;
- canonical CDC + snapshot/bootstrap handoff;
- Debezium/Kafka and Delta CDF reference adapters/recovery;
- replay-stable file/API capture boundaries;
- durable target-operation CAS journal + provider-neutral commit probe;
- control-plane v4 + backend certification contract;
- SQLAlchemy relational runtime repository;
- Fabric REST Job Scheduler client;
- Fabric Data Pipeline execution backend;
- concrete Copy Job and Spark Job Definition capture REST transports;
- immutable release/delivery contracts.

## Evidence boundary

Still unproven in a retained approved environment:

```text
real Entra token acquisition and workspace/item authorization
live Pipeline / Copy Job / Spark Job Definition execution with native IDs
real Copy/Spark post-run metrics/boundary observation
real Fabric SQL Database or Azure SQL Database driver/auth/network/concurrency behavior
live Kafka seek/commit/rebalance behavior
live Delta CDF bounded read/retention behavior
provider-specific target commit proof
capacity/throttling/gateway behavior
approved DEV end-to-end success and failure drills
```

Never upgrade CI/reference evidence to `FABRIC PROVEN` or `PRODUCTION DB PROVEN` without retained approved service evidence.

## Exact next implementation sequence

1. implement Fabric Warehouse target-native commit proof around the existing `TargetOperationIntent` / `TargetCommitProbe` contract;
2. prefer a framework operation marker committed in the **same explicit Warehouse transaction** as the target mutation; use Warehouse Query Insights/query labels only as secondary diagnostic correlation because historical query visibility can lag;
3. add provider-specific source-position discovery where a provider exposes authoritative positions;
4. wire live Kafka/Delta clients if those profiles remain in release scope;
5. run approved DEV Fabric Pipeline + Copy/Spark + SQL repository executions retaining native/framework correlation and failure drills;
6. run control-plane certification against the selected real SQL backend and retain enterprise evidence;
7. exact candidate audit/docs/CI and only then decide whether to publish `0.4.0`.

## Repository boundary

- `fabric-data-framework`: reusable semantics/runtime/transports/package; current hardening work lives here.
- `fabric-customer`: business metadata/config/bounded extensions; do not force it to consume unreleased `0.4.0` yet.
- `fabric-infra`: optional infrastructure/capacity/workspace lifecycle automation; independent from framework development.

## Durable project memory

New conversations should read in this order:

```text
docs/CURRENT_STATUS.md
docs/PRODUCTION_READINESS_AUDIT.md
docs/GUARANTEE_COVERAGE.md
docs/PROJECT_BLUEPRINT.md
docs/PRODUCTION_REQUIREMENTS.md
docs/CAPTURE_PATTERN_CATALOG.md
docs/TARGET_OPERATION_IDEMPOTENCY.md
docs/PROVIDER_NATIVE_RECOVERY.md
docs/CONTROL_PLANE_CERTIFICATION.md
docs/RELATIONAL_RUNTIME_REPOSITORY.md
docs/FABRIC_PIPELINE_BACKEND.md
docs/FABRIC_CAPTURE_REST_TRANSPORTS.md
docs/EXECUTION_ENGINE_STRATEGY.md
docs/FABRIC_EXECUTION_MODEL.md
docs/CDC_DESIGN.md
docs/CONTROL_PLANE_DESIGN.md
docs/REPOSITORY_STRUCTURE.md
docs/CICD_DESIGN.md
docs/ECOSYSTEM_BLUEPRINT.md
```

If docs disagree with code/tests, inspect implementation and repair docs before continuing.
