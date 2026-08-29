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
372 tests

PR #30 -> 732920e214ccdead20c632f7e70c0eb8f1267f0d
approved DEV integration evidence harness
GitHub Actions 33250676068
395 tests
Python 3.11 + 3.13 + static + wheel SUCCESS
```

The reusable portable implementation now covers the full execution/recovery chain and the evidence machinery needed to prove it in an approved environment. The main release blocker has therefore shifted from missing framework abstractions to **real approved DEV execution, failure drills, real SQL backend certification and retained external enterprise evidence**.

## Core framework flow

```text
source fidelity classification
  -> immutable DatasetConfig
  -> capability profile / ExecutionPlan
  -> environment-local binding
  -> Fabric/provider capture execution
  -> CaptureReceipt / native evidence
  -> TargetOperationIntent + CAS claim
  -> target mutation + provider-native proof
  -> reconciliation / DQ
  -> framework checkpoint/state commit
  -> approved-environment evidence manifest
```

**Capture fidelity is an upper bound on history fidelity.** Provider-native progress never silently becomes framework downstream state.

## Approved DEV evidence harness

PR #30 implements a credential-free, fail-closed evidence layer for running the already-implemented provider/runtime contracts in a real approved environment.

Canonical runbook: `DEV_INTEGRATION_EVIDENCE.md`.

### Authentication boundary

The framework now provides:

```text
EnvironmentAccessTokenProvider
AzureIdentityTokenProvider
```

Both are adapters into the existing `FabricRestClient` token-provider boundary. Tokens are acquired at call time and are not serialized into framework artifacts. The core framework does not hard-depend on or configure `azure-identity`; the deployment environment chooses the approved credential mechanism.

### Evidence spec and manifest

A source-controlled `IntegrationEvidenceSpec` binds evidence to:

```text
evidence schema version
environment
domain
framework version
exact release_hash
exact required/optional check list
```

`IntegrationEvidenceManifest` records sanitized per-check correlation evidence and a deterministic `manifest_hash`.

Required checks certify only when status is exactly `PASS`:

```text
PASS              -> satisfies required check
FAIL              -> blocks certification
NOT_RUN           -> blocks certification when required
EXTERNAL_REQUIRED -> blocks certification when required
```

Missing runners become `NOT_RUN`. Runner exceptions become sanitized `FAIL` records without copying raw provider/driver exception messages, because such messages can contain credentials or signed URLs. Runner IDs not declared in the spec are rejected instead of silently ignored.

The evidence validator rejects obvious credential-bearing material including bearer/authorization text, token/password/client-secret fields, signed URL query parameters and URI user-info credentials.

### Concrete DEV evidence builders

The harness has concrete projections for:

```text
FABRIC_ITEM_READ
FABRIC_PIPELINE_RUN
FABRIC_COPY_JOB_CAPTURE
FABRIC_SPARK_CAPTURE
FABRIC_WAREHOUSE_TARGET_COMMIT
CONTROL_PLANE_CERTIFICATION
```

Optional evidence kinds also exist for Kafka and Delta CDF when those providers are in release scope.

The minimum Fabric identity smoke is a read-only item GET. PASS verifies the returned item identity; HTTP 200 alone is insufficient.

Pipeline PASS requires provider `Completed`, matching item/job type, framework pipeline/dataset IDs, native job ID, root activity ID and retained evidence reference. It does **not** weaken the existing rule that Fabric `Completed` is not framework semantic success; the exact durable framework dataset outcome remains required by the Pipeline backend.

Copy/Spark approved evidence uses:

```python
adapter.execute_with_evidence(request)
```

which invokes the provider exactly once and returns both:

```text
FabricCaptureExecutionResult
  receipt          -> verified CaptureReceipt
  native_evidence  -> workspace/item/job/root/status diagnostics
```

The evidence builder verifies native success, execution-kind/receipt-engine consistency, job identity consistency, provider `Completed` and root correlation before it can produce PASS.

Warehouse evidence uses the same-transaction target operation marker from PR #28 as primary commit proof.

Control-plane evidence projects the existing `ControlPlaneCertificationReport`; the harness does not duplicate transaction rollback/CAS certification logic.

### Retained evidence gate

The CLI now supports:

```bash
fabric-framework integration-evidence-validate \
  --spec evidence-spec.json \
  --manifest evidence-manifest.json \
  --require-certified
```

The command fails unless schema/environment/domain/framework/release hash/check specification match exactly and every required check is PASS.

A schema-valid example is retained at:

```text
examples/dev_integration_evidence_spec.json
```

Its placeholder release hash must be replaced by the real immutable release hash for a real run.

Correct evidence label for PR #30:

```text
IMPLEMENTED + CI PROVEN EVIDENCE HARNESS CONTRACT
```

not `FABRIC PROVEN`.

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

Provider probes resolve only to `COMMITTED`, `NOT_COMMITTED` or `UNRESOLVED`. Unknown outcome never permits blind re-execution.

Canonical runbooks:

```text
TARGET_OPERATION_IDEMPOTENCY.md
PROVIDER_NATIVE_RECOVERY.md
FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md
```

## Fabric Warehouse target-native commit proof

PR #28 implements the first provider-specific `TargetCommitProbe`.

Preferred target transaction:

```text
BEGIN TRAN
  target mutation
  framework target-side operation marker
COMMIT TRAN
```

The control-plane target-operation CAS remains the execution serialization/retry authority. The target-side marker is independent provider-native proof that the target transaction committed; it is not used as a distributed lock.

Probe behavior remains fail closed:

```text
matching committed marker -> COMMITTED
marker absent              -> UNRESOLVED
marker absent + independently certified no-late-commit proof -> NOT_COMMITTED
```

Warehouse Query Insights / query labels remain secondary diagnostics only because historical visibility can lag.

CI proves the complete journal handoff:

```text
framework EXECUTE claim
  -> target mutation + marker commit
  -> simulated lost acknowledgement
  -> framework UNKNOWN
  -> FabricWarehouseTargetCommitProbe
  -> durable SUCCEEDED
  -> future claim SKIP_SUCCEEDED
```

Correct evidence label: `IMPLEMENTED + CI PROVEN PROVIDER COMMIT CONTRACT`, not `FABRIC WAREHOUSE PROVEN`.

## Concrete Fabric capture transports

PR #26 implements concrete REST transport contracts for Copy Job and Spark Job Definition.

Copy Job retains `FABRIC_NATIVE` progress ownership; framework source bounds are rejected. Current Copy Job CDC product semantics remain treated as net-change constrained, not full intermediate-event history.

Spark Job Definition supports framework-bounded capture only through an explicit resolver into the selected released SJD `executionData` contract.

Provider `Completed` alone is insufficient for `CaptureReceipt`; successful capture requires item/provider-specific `FabricCaptureObservation` for rows/landing/boundary/schema evidence that generic job status does not prove.

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

Runtime requires an explicitly migrated exact schema and validates deployed `config_hash`/domain against the released artifact. Dedicated target-operation and CDC CAS modules remain authoritative for their stronger state machines.

Production-candidate profiles remain:

```text
fabric_sql_database_v1
azure_sql_database_v1
```

Canonical runbooks:

```text
CONTROL_PLANE_CERTIFICATION.md
RELATIONAL_RUNTIME_REPOSITORY.md
```

## Implemented development/runtime surface

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
- provider-neutral and Fabric Warehouse target commit probes;
- control-plane v4 + production backend certification contract;
- SQLAlchemy relational runtime repository;
- Fabric REST Job Scheduler client;
- Fabric Data Pipeline execution backend;
- concrete Copy Job and Spark Job Definition capture transports;
- Fabric Warehouse atomic target mutation/marker proof contract;
- credential-safe approved-environment evidence spec/runner/manifest/gate;
- immutable release/delivery contracts.

## Evidence boundary

Still unproven in retained approved infrastructure:

```text
real Entra token acquisition under the selected enterprise identity
real workspace/item authorization
live Pipeline / Copy Job / Spark Job Definition executions
real Copy/Spark post-run observations
real Fabric Warehouse target mutation + marker transaction
network/client failure around Warehouse COMMIT and reconnect behavior
production-approved marker-absence certification
real Fabric SQL Database / Azure SQL Database driver/auth/network/concurrency behavior
real control-plane production certification + external evidence
live Kafka seek/commit/rebalance if in release scope
live Delta CDF bounded reads/retention drill if in release scope
capacity/throttling/gateway behavior
approved DEV success + failure drill evidence bundle
```

Never upgrade CI/reference evidence to `FABRIC PROVEN`, `FABRIC WAREHOUSE PROVEN` or `PRODUCTION DB PROVEN` without retained approved service evidence for the exact capability and release hash.

## Exact next implementation / execution sequence

The portable framework is now sufficiently broad that the next P0 should be evidence-driven rather than another abstraction layer:

1. create an environment-facing DEV runner/configuration entry point that binds the exact release hash to DEV workspace/item IDs and runtime-only credential/database inputs without putting secrets in source-controlled artifacts;
2. run the read-only Fabric item authorization smoke under the approved enterprise identity;
3. run control-plane certification against the chosen real Fabric SQL Database or Azure SQL Database instance and retain the report plus required external control references;
4. execute representative real Pipeline, Copy Job and bounded Spark paths while retaining framework run IDs, native job/root IDs and verified capture observations;
5. execute real Warehouse target mutation + marker transaction and an ambiguous COMMIT/network failure drill; do not approve marker-absence retry unless observed driver/session evidence supports it;
6. assemble the exact-release DEV `IntegrationEvidenceManifest` and pass `integration-evidence-validate --require-certified`;
7. prove Kafka/Delta only if those profiles are part of the `0.4.0` product promise;
8. run exact-candidate code/docs/evidence audit and only then decide whether to publish `0.4.0`.

## Repository boundary

- `fabric-data-framework`: reusable semantics/runtime/transports/evidence/package; current hardening work lives here.
- `fabric-customer`: business metadata/config/bounded extensions; do not force it to consume unreleased `0.4.0` yet.
- `fabric-infra`: optional infrastructure/capacity/workspace lifecycle automation; independent from framework development.

## Durable project memory

New conversations should read in this order:

```text
docs/CURRENT_STATUS.md
docs/PRODUCTION_READINESS_AUDIT.md
docs/DEV_INTEGRATION_EVIDENCE.md
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
