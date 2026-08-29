# Current Status — fabric-data-framework

Last updated: 2026-08-29

## Current phase and release gate

`v0.3.0` remains the latest immutable public framework release. Source version `0.4.0` is an unreleased development line. **Do not publish v0.4.0 yet.**

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
344 tests

PR #24 -> 2fa8e2c4bc6875b529a4968694722d4108a635ff
SQLAlchemy production runtime repository + relational Fabric child/parent handoff
GitHub Actions 33246594883
350 tests
Python 3.11 + 3.13 + static + wheel SUCCESS
```

The portable/reference operation journal, provider recovery contracts, control-plane certification contract, Fabric REST/Pipeline backend and production-oriented SQLAlchemy runtime repository are now implemented. Release remains blocked because real Fabric/Kafka/Delta service execution, real production SQL backend certification, selected live capture transports/provider probes, approved DEV failure drills and external enterprise evidence are not yet retained.

## Current product model

Routine datasets onboard through source-controlled metadata and bounded extension points rather than framework edits:

```text
source/capture classification
    -> DatasetConfig + capture selection
    -> capability profile / execution engines
    -> immutable ExecutionPlan
    -> environment-local physical bindings
    -> execution backend
    -> durable relational runtime evidence
    -> target/reconciliation/state gates
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

Domain CI can require a source-fidelity selection for every dataset:

```bash
fabric-framework capture-onboarding-validate \
  --config-dir <dataset-config-dir> \
  --selections <capture-selections.json> \
  --require-all
```

## Durable target-operation model

Control-plane v4 persists attempt-independent target mutation state:

```text
target_operation        expected-version CAS current state
target_operation_event  append-only lifecycle evidence
```

Fail-closed behavior:

```text
new               -> EXECUTE
SUCCEEDED         -> SKIP_SUCCEEDED
IN_PROGRESS retry -> RECONCILE_REQUIRED
UNKNOWN retry     -> RECONCILE_REQUIRED
NOT_COMMITTED     -> CAS reopen -> EXECUTE
```

Provider commit probes map retained evidence only to `COMMITTED`, `NOT_COMMITTED` or `UNRESOLVED`.

Canonical runbook: `TARGET_OPERATION_IDEMPOTENCY.md`.

## Provider-native recovery model

Framework downstream state remains semantic truth.

Kafka consumer-group offsets are transport cursors. Cursor `MISSING`, `BEHIND`, `ALIGNED` and `AHEAD` states are handled relative to the framework checkpoint; retention gaps fail closed.

Delta CDF resume planning requires the next unapplied commit version to remain inside the provider's retained earliest/latest version range.

Canonical runbook: `PROVIDER_NATIVE_RECOVERY.md`.

## Production control-plane certification

Built-in profiles:

```text
sqlite_reference_v1       reference-only forever
fabric_sql_database_v1    production candidate
azure_sql_database_v1     production candidate
```

Certification is separate from migration and requires schema/migration checks, rollback, target-operation CAS, CDC checkpoint CAS and retained enterprise evidence for backend identity, IAM, networking, backup/restore, availability/recovery, monitoring and retention/governance.

Canonical runbook: `CONTROL_PLANE_CERTIFICATION.md`.

## Fabric Pipeline backend

PR #22 implemented:

```text
framework ready wave
  -> FabricPipelineBackend
  -> ExecutionPlan
  -> environment-local FabricPipelineBinding
  -> Fabric REST on-demand item job
  -> Location/job-instance correlation
  -> Retry-After aware polling
  -> terminal remote provider status
  -> exact durable framework dataset outcome
```

Critical invariant:

> **Fabric `Completed` is not framework success.**

A matching terminal framework outcome for the exact `dataset_run_id` must exist. Missing, mismatched or non-terminal evidence fails closed. Fabric `Deduped` is not treated as success for the requested framework attempt.

Native provider correlation is stored in `StepRunAudit.details`.

Canonical runbook: `FABRIC_PIPELINE_BACKEND.md`.

## SQLAlchemy relational runtime repository

PR #24 closes the portable runtime-store wiring gap.

`SqlAlchemyControlPlaneRepository` now implements the runtime repository contract over the certified relational schema and is exported as a public framework API.

Configuration truth remains deliberately split by responsibility:

```text
immutable released domain artifact
    -> complete DatasetConfig

relational control plane
    -> deployed normalized metadata + config_hash
    -> runtime/evidence state
```

On every dataset read the repository requires:

```text
dataset deployed in SQL
released runtime catalog contains dataset_id
SQL config_hash == released DatasetConfig.config_hash
SQL domain == runtime domain
```

The repository does not pretend to reconstruct a complete config from normalized SQL rows that historically did not persist every field such as `SourceConfig.connection_ref`.

Runtime construction also requires an already-migrated exact control-plane schema. It never silently migrates the store.

Durable SQL paths now include:

```text
pipeline_run lifecycle
dataset_run lifecycle + DatasetDispatchOutcome read
step_run + provider details
capture_receipt
reconciliation_result
quarantine_batch
dataset_attempt_lineage
reprocess_request
```

The existing stronger specialized CAS/state modules remain authoritative for CDC checkpoints, target-operation state and gated recovery. The generic legacy watermark method is compatibility-only and is not a replacement for gated/CAS production state transitions.

A deterministic test now proves this handoff:

```text
Fabric child simulation
    -> SQL terminal DatasetRunAudit
Fabric provider -> Completed
parent -> SQL get_dataset_outcome(exact run id)
parent -> native Fabric job/root step evidence
```

Non-NORMAL dispatcher run modes are also persisted in `pipeline_run.run_mode` rather than silently becoming NORMAL.

Canonical runbook: `RELATIONAL_RUNTIME_REPOSITORY.md`.

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
- SQLAlchemy relational runtime repository + durable Fabric child/parent outcome handoff;
- immutable release/delivery contracts.

## Evidence boundary

Do not describe CI-proven transport/repository code as a live Fabric or production SQL integration.

Still unproven in a retained approved environment:

```text
real token acquisition and workspace/item authorization
real Data Pipeline per-run parameter acceptance
live Pipeline POST/poll execution with native IDs
real child SJD/Notebook/native activity
real Fabric SQL Database/Azure SQL Database driver/auth/network/concurrency behavior
real Fabric Copy/Spark/Dataflow capture transports
live Kafka seek/commit/rebalance behavior
live Delta CDF bounded reads/retention drill
provider-specific target commit probes
capacity/throttling/gateway behavior
approved DEV end-to-end execution + failure drills
```

Correct current labels:

```text
PR #22  IMPLEMENTED + CI PROVEN TRANSPORT/BACKEND
PR #24  IMPLEMENTED + CI PROVEN RELATIONAL RUNTIME
```

Neither is `FABRIC PROVEN` or `PRODUCTION DB PROVEN` yet.

## Exact next implementation sequence

1. implement concrete Fabric Copy Job and Spark Job Definition capture transports on the documented Fabric v1 APIs, reusing the existing REST/job evidence model;
2. map native Copy Job/Spark job evidence into the existing `FabricNativeRunEvidence` / `CaptureReceipt` contracts without creating a second progress truth;
3. add provider-specific target commit/source-position probes where documented evidence exists;
4. wire real Kafka/Delta clients if those provider profiles are in the release scope;
5. run approved DEV end-to-end executions retaining framework + native provider IDs and failure drills;
6. run control-plane certification against the selected real SQL backend and retain enterprise evidence;
7. exact-candidate audit/docs/CI and only then make the next immutable release decision.

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
docs/FABRIC_PIPELINE_BACKEND.md
docs/RELATIONAL_RUNTIME_REPOSITORY.md
docs/EXECUTION_ENGINE_STRATEGY.md
docs/FABRIC_EXECUTION_MODEL.md
docs/CDC_DESIGN.md
docs/CONTROL_PLANE_DESIGN.md
docs/REPOSITORY_STRUCTURE.md
docs/CICD_DESIGN.md
docs/ECOSYSTEM_BLUEPRINT.md
```

If docs disagree with code/tests, inspect implementation and repair docs before continuing.
