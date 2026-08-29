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
SQLAlchemy runtime repository + relational Fabric child/parent handoff
350 tests

PR #26 -> 8f23942acd5b03d817e42b97d9f490acc6bee89f
concrete Copy Job + Spark Job Definition capture REST transports
362 tests

PR #28 -> 67562e4312dc9c37e8b7fb8d79535bb621bd573f
Fabric Warehouse target-native atomic commit proof
GitHub Actions 33247800732
372 tests
Python 3.11 + 3.13 + static + wheel SUCCESS
```

Portable implementation now covers the full reusable execution chain from source-fidelity metadata through Fabric orchestration/capture, durable relational runtime evidence and provider-specific Fabric Warehouse ambiguous-commit reconciliation. Release remains blocked on **real approved service evidence**, real production SQL backend certification and any remaining live Kafka/Delta scope.

## Core framework flow

```text
source fidelity classification
  -> immutable DatasetConfig
  -> capability profile / ExecutionPlan
  -> environment-local binding
  -> Fabric/provider capture execution
  -> CaptureReceipt / runtime evidence
  -> TargetOperationIntent + CAS claim
  -> target mutation + provider-native proof
  -> reconciliation / DQ
  -> framework checkpoint/state commit
```

**Capture fidelity is an upper bound on history fidelity.** Provider-native progress never silently becomes framework downstream state.

## Target-operation / exactly-once recovery model

Control-plane v4 persists attempt-independent semantic target state:

```text
target_operation        expected-version CAS current state
target_operation_event  append-only lifecycle evidence
```

Claim behavior:

```text
new               -> EXECUTE
SUCCEEDED         -> SKIP_SUCCEEDED
IN_PROGRESS retry -> RECONCILE_REQUIRED
UNKNOWN retry     -> RECONCILE_REQUIRED
NOT_COMMITTED     -> CAS reopen -> EXECUTE
```

Provider probes resolve only to:

```text
COMMITTED
NOT_COMMITTED
UNRESOLVED
```

Unknown outcome never permits blind re-execution.

Canonical runbooks:

```text
TARGET_OPERATION_IDEMPOTENCY.md
PROVIDER_NATIVE_RECOVERY.md
FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md
```

## Fabric Warehouse target-native commit proof

PR #28 implements a provider-specific `TargetCommitProbe` for Fabric Warehouse.

Preferred target transaction:

```text
BEGIN TRAN
  target mutation
  framework target-side operation marker
COMMIT TRAN
```

`FabricWarehouseMarkerStore.execute_atomic()` passes the same SQLAlchemy target connection/transaction to the target mutation callback and marker insert. Runtime never creates the marker table implicitly; provisioning is a deployment responsibility.

The marker repeats the existing semantic target identity:

```text
operation_key
dataset_id
operation_kind
target_reference
effective_config_hash
input_fingerprint
semantic_version
```

plus run/native correlation.

Important responsibility split:

```text
control-plane target-operation CAS
    -> execution serialization / semantic retry gate

Warehouse target marker
    -> provider-native proof that target transaction committed
```

The target marker does not rely on Warehouse PK/UNIQUE enforcement as a distributed lock.

Probe behavior:

```text
matching committed marker
  -> COMMITTED

marker absent
  -> UNRESOLVED by default

marker absent
+ independent certified evidence that prior transaction cannot later commit
  -> NOT_COMMITTED
```

Marker absence **alone** never grants retry permission.

Warehouse Query Insights / query labels are secondary diagnostics only. They may retain statement correlation, but delayed history visibility means a present/absent Query Insights row is not primary immediate commit truth.

Deterministic journal integration now proves:

```text
framework claim EXECUTE
  -> target mutation + marker commit
  -> simulate lost client acknowledgement
  -> framework UNKNOWN
  -> FabricWarehouseTargetCommitProbe
  -> durable SUCCEEDED
  -> future claim SKIP_SUCCEEDED
```

Correct evidence label:

```text
IMPLEMENTED + CI PROVEN PROVIDER COMMIT CONTRACT
```

not `FABRIC WAREHOUSE PROVEN` yet.

## Concrete Fabric capture transports

PR #26 implements concrete REST transport contracts for:

```text
FABRIC_COPY_JOB -> ExecutionKind.FABRIC_COPY_JOB
SPARK           -> ExecutionKind.SPARK_JOB_DEFINITION
```

Copy Job retains `FABRIC_NATIVE` progress ownership; framework source bounds are rejected. Current Copy Job CDC product semantics are treated as net-change constrained, not full intermediate-event history.

Spark Job Definition supports framework-bounded capture only through an explicit resolver into the selected released SJD `executionData` contract.

Successful provider `Completed` status is insufficient for a `CaptureReceipt`: item/provider-specific `FabricCaptureObservation` must supply the rows/landing/boundary/schema evidence that generic job status does not prove.

Canonical runbook: `FABRIC_CAPTURE_REST_TRANSPORTS.md`.

## Fabric Pipeline backend

```text
framework ready wave
  -> FabricPipelineBackend
  -> Fabric REST Pipeline job
  -> provider terminal status
  -> exact durable relational DatasetDispatchOutcome
```

Fabric `Completed` is not framework success. The exact `dataset_run_id` must have a durable terminal framework outcome.

Canonical runbook: `FABRIC_PIPELINE_BACKEND.md`.

## Control-plane / relational runtime

`SqlAlchemyControlPlaneRepository` is the production-oriented runtime repository surface.

```text
released domain artifact -> complete immutable DatasetConfig
relational control plane  -> deployed metadata + config_hash + runtime/evidence state
```

Runtime requires an explicitly migrated exact control-plane schema and validates SQL `config_hash`/domain against the released artifact. Dedicated target-operation and CDC CAS modules remain authoritative for their stronger state machines.

Production-candidate control-plane profiles remain:

```text
fabric_sql_database_v1
azure_sql_database_v1
```

Canonical runbooks:

```text
CONTROL_PLANE_CERTIFICATION.md
RELATIONAL_RUNTIME_REPOSITORY.md
```

## Implemented development runtime

Current `main` includes:

- immutable metadata/effective config and bounded runtime overrides;
- 14-pattern source-fidelity onboarding catalog;
- independent capture/apply/progress ownership;
- immutable ExecutionPlan + capability profiles;
- APPEND, REPLACE, UPSERT, SCD1, SCD2, SNAPSHOT_DIFF;
- canonical CDC + snapshot/bootstrap handoff;
- Kafka/Debezium and Delta CDF reference recovery contracts;
- replay-stable file/API boundaries;
- durable target-operation CAS journal;
- provider-neutral and Fabric Warehouse provider-specific target commit probes;
- control-plane v4 + production backend certification contract;
- SQLAlchemy relational runtime repository;
- Fabric REST Job Scheduler client;
- Fabric Data Pipeline execution backend;
- concrete Copy Job and Spark Job Definition capture transports;
- Fabric Warehouse atomic target mutation/marker proof contract;
- immutable release/delivery contracts.

## Evidence boundary

Still unproven in a retained approved environment:

```text
real Entra token acquisition and workspace/item authorization
live Pipeline / Copy Job / Spark Job Definition executions
real Copy/Spark post-run observations
real Fabric Warehouse target mutation + marker transaction
network failure around Warehouse COMMIT and reconnect behavior
production-approved marker-absence certification
real Fabric SQL Database / Azure SQL Database driver/auth/network/concurrency behavior
live Kafka seek/commit/rebalance behavior if in release scope
live Delta CDF bounded reads/retention drill if in release scope
capacity/throttling/gateway behavior
approved DEV end-to-end success + failure drills
```

Never upgrade CI/reference evidence to `FABRIC PROVEN`, `FABRIC WAREHOUSE PROVEN` or `PRODUCTION DB PROVEN` without retained approved service evidence.

## Exact next implementation sequence

1. build a repeatable approved-DEV integration/evidence harness around current environment bindings, authentication injection and retained evidence manifests;
2. execute real Fabric Pipeline, Copy Job and Spark Job Definition smoke/integration paths while retaining framework run IDs + native job/root IDs;
3. execute Fabric Warehouse target mutation + marker transactions and ambiguous COMMIT failure drills; certify any marker-absence logic only from observed driver/session behavior;
4. run control-plane certification against the selected real Fabric SQL Database or Azure SQL Database backend and retain external evidence;
5. wire and prove live Kafka/Delta clients only if those profiles are in the `0.4.0` product scope;
6. exact-candidate audit/docs/CI and only then decide whether to publish `0.4.0`.

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
docs/FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md
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
