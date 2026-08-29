# Current Status — fabric-data-framework

Last updated: 2026-08-29

## Current phase and release gate

`v0.3.0` remains the latest immutable public release. Source version `0.4.0` is an unreleased development line. **Do not publish v0.4.0 yet.**

Latest release-significant merged baselines:

```text
PR #14 -> 4b20300c822e16a398342e0cc97da90ee51b035a
mainstream capture/onboarding + Delta CDF reference slice
310 tests

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
Fabric REST Job Scheduler transport + Data Pipeline execution backend
GitHub Actions 33246151126
344 tests
Python 3.11 + 3.13 + static + wheel SUCCESS
```

The portable/reference operation journal, provider recovery, control-plane certification contract and first executable Fabric orchestration transport/backend are now implemented. Release remains blocked because real production SQL repository wiring, live Fabric/Kafka/Delta transports/provider probes, approved DEV executions and external enterprise evidence are not yet retained.

## Current product model

Routine datasets should onboard through source-controlled metadata and bounded extension points rather than framework edits:

```text
source/capture classification
    -> source fidelity + delete visibility
    -> DatasetConfig + capture selection
    -> capability profile / execution engines
    -> immutable ExecutionPlan
    -> environment-local physical bindings
    -> execution backend
    -> durable target/reconciliation/state evidence
```

Capture fidelity remains an upper bound on history fidelity.

Canonical source guide: `CAPTURE_PATTERN_CATALOG.md`.

## Mainstream capture patterns

The executable catalog covers:

```text
FULL_SNAPSHOT
WATERMARK_INCREMENTAL
WATERMARK_LOOKBACK
WATERMARK_TOMBSTONE
CDC_NET_CURRENT
CDC_NET_OBSERVATION
CDC_FULL
TRANSACTION_LOG_CDC
DEBEZIUM_KAFKA
DELTA_CDF
EVENT_SOURCE
SNAPSHOT_DIFF
API_CURSOR_INCREMENTAL
FILE_INCREMENTAL
```

Domain CI can require classification for every dataset:

```bash
fabric-framework capture-onboarding-validate \
  --config-dir <dataset-config-dir> \
  --selections <capture-selections.json> \
  --require-all
```

Checked-in examples under `docs/examples/capture-patterns/` are loaded by tests.

## Durable target-operation model

A target mutation has attempt-independent semantic identity over:

```text
dataset_id
operation_kind
target_reference
effective_config_hash
input_fingerprint
semantic_version
```

Control-plane v4 persists:

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

Provider commit probes map only retained evidence to `COMMITTED`, `NOT_COMMITTED` or `UNRESOLVED`; probe failure remains `UNKNOWN`.

Canonical runbook: `TARGET_OPERATION_IDEMPOTENCY.md`.

## Provider-native recovery model

Framework downstream state remains semantic truth.

Kafka consumer-group offsets are transport cursors only. The framework explicitly classifies provider cursor state as `MISSING`, `BEHIND`, `ALIGNED` or `AHEAD`, derives seek plans from the framework checkpoint and fails closed on retention gaps.

Delta CDF resume planning checks the next required version against provider earliest/latest availability and fails closed when retained history no longer contains the next unapplied version.

Canonical runbook: `PROVIDER_NATIVE_RECOVERY.md`.

## Production control-plane certification contract

PR #21 added explicit profiles:

```text
sqlite_reference_v1       reference-only forever
fabric_sql_database_v1    production candidate
azure_sql_database_v1     production candidate
```

Certification is separate from migration and validates:

```text
exact schema v4
required tables/migration history
transaction rollback
target-operation CAS
CDC checkpoint CAS
backend service identity evidence
IAM/access
network security
backup/restore
availability/recovery
monitoring/alerting
retention/governance
```

Passing SQLite tests never makes SQLite production-certified. A real Fabric SQL Database or Azure SQL Database instance still must run the certification suite and retain the external evidence bundle.

Canonical runbook: `CONTROL_PLANE_CERTIFICATION.md`.

## Fabric Pipeline backend

PR #22 implemented the first real HTTP/runtime orchestration path behind the provider-neutral planner.

Implemented flow:

```text
framework dependency-ready wave
  -> FabricPipelineBackend
  -> compile ExecutionPlan
  -> FabricPipelineBinding
  -> FabricRestPipelineTransport
  -> Fabric v1 on-demand item job
  -> Location/job-instance correlation
  -> Retry-After aware polling
  -> terminal remote status
  -> exact durable framework dataset outcome check
```

Stable child correlation parameters:

```text
framework_pipeline_run_id   Guid
framework_dataset_run_id    Guid
dataset_id                  Text
run_mode                    Text
attempt                     Integer
effective_config_hash       Text
execution_plan_hash         Text
```

Critical invariant:

> **Fabric `Completed` is not framework success.**

A matching terminal framework outcome for the exact `dataset_run_id` must exist. Missing, mismatched or non-terminal outcome evidence fails closed. Fabric `Deduped` is currently blocked/retryable rather than treated as success.

Native provider evidence is retained in `StepRunAudit.details`:

```text
workspace_id
pipeline_item_id
job_instance_id
root_activity_id
job_type
remote_status
failure_reason
execution_plan_hash
```

The dispatcher remains authoritative for dependencies/criticality. A physical backend must return exactly the selected ready wave.

Canonical runbook: `FABRIC_PIPELINE_BACKEND.md`.

## Implemented development runtime

Current `main` includes:

- immutable metadata/effective config and allow-listed overrides;
- independent capture/apply semantics, engines and progress ownership;
- immutable ExecutionPlan + capability profiles;
- 14-pattern source-fidelity onboarding model;
- composite WATERMARK + overlap;
- Bronze/DQ/quarantine/no-silent-loss accounting;
- APPEND, REPLACE, UPSERT, SCD1, SCD2, SNAPSHOT_DIFF;
- canonical CDC + bootstrap/handoff;
- Debezium/Kafka and Delta CDF adapters/reference recovery;
- Fabric capture adapter contracts;
- replay-stable file/API boundaries;
- explicit retry/replay/rebuild semantics;
- target-operation CAS journal + target commit-probe contract;
- control-plane v4 + typed operator reads;
- control-plane backend certification contract;
- Fabric REST Job Scheduler client;
- pluggable ready-wave dispatcher;
- Fabric Data Pipeline execution backend;
- immutable release/delivery contracts.

## Evidence boundary

Do not describe CI-proven transport/backend code as a live Fabric integration.

Still unproven in a retained approved environment:

```text
real token acquisition and workspace/item authorization
real Data Pipeline per-run parameter acceptance
live POST/poll execution with native IDs
real child SJD/Notebook/native activity
production SQL repository implementation/wiring
real Fabric Copy/Spark/Dataflow capture transports
live Kafka seek/commit/rebalance behavior
live Delta CDF bounded reads/retention drill
provider-specific target commit probes
capacity/throttling/gateway behavior
approved DEV end-to-end execution + failure drills
```

Correct current label for PR #22: `IMPLEMENTED + CI PROVEN TRANSPORT/BACKEND`, not `FABRIC PROVEN`.

## Exact next implementation sequence

1. implement/wire a production SQLAlchemy `ControlPlaneRepository` so Fabric child/parent execution uses the certified relational store rather than reference in-memory abstractions;
2. add relational dataset-outcome read/write and native step-evidence paths required by the Pipeline handoff;
3. implement selected live Fabric capture transports and provider-specific target commit/source-position probes;
4. run approved DEV end-to-end executions retaining framework + native Fabric/Kafka/Delta correlation and failure drills;
5. run control-plane certification against the selected real SQL backend and retain external evidence;
6. exact-candidate audit/docs/CI and only then make the next immutable release decision.

## Repository boundary

- `fabric-data-framework`: reusable semantics/runtime/transports/package; current hardening work lives here.
- `fabric-customer`: business metadata/config/bounded extensions; do not force it to consume unreleased `0.4.0` yet.
- `fabric-infra`: optional infrastructure/capacity/workspace lifecycle automation; independent from data-framework development.

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
docs/FABRIC_PIPELINE_BACKEND.md
docs/EXECUTION_ENGINE_STRATEGY.md
docs/FABRIC_EXECUTION_MODEL.md
docs/CDC_DESIGN.md
docs/CONTROL_PLANE_DESIGN.md
docs/REPOSITORY_STRUCTURE.md
docs/CICD_DESIGN.md
docs/ECOSYSTEM_BLUEPRINT.md
```

If docs disagree with code/tests, inspect implementation and repair docs before continuing.
