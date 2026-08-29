# Relational Runtime Repository — Production Runtime Contract

Status: executable/reference contract for unreleased `0.4.0`

Last updated: 2026-08-29

## Purpose

`SqlAlchemyControlPlaneRepository` is the durable runtime adapter that connects the existing framework dispatcher/Fabric child execution to the certified relational control-plane schema.

It closes an important architecture gap:

```text
old reference runtime
    ControlPlaneRepository Protocol
    -> InMemoryControlPlane

later durable primitives
    control_plane.py
    control_plane_io.py
    target_operation_io.py

current runtime
    ControlPlaneRepository contract
    -> SqlAlchemyControlPlaneRepository
    -> same certified relational schema
```

This is consolidation, not a third state system.

---

## 1. Source of truth for configuration

The runtime intentionally does **not** reconstruct a complete `DatasetConfig` from normalized SQL rows.

Correct model:

```text
source-controlled domain config
    -> immutable released domain artifact
    -> DatasetConfig runtime catalog

same config
    -> deployment materialization
    -> relational dataset/policy rows + config_hash

runtime read
    -> find deployed SQL dataset
    -> find released DatasetConfig
    -> require config_hash equality
    -> require domain equality
    -> return released DatasetConfig
```

Why?

The normalized schema is designed for operational queryability and currently does not persist every physical/logical field needed to reconstruct the original Pydantic object. For example, older schema materialization does not persist `SourceConfig.connection_ref` directly in the `dataset` table.

Inventing or dropping such values during SQL reconstruction would be unsafe. The immutable release artifact remains semantic truth; SQL proves which exact config hash was deployed.

A runtime config mismatch fails closed.

---

## 2. Explicit migration rule

Constructing the runtime repository never migrates the database.

Required deployment order:

```bash
fabric-framework control-plane-migrate \
  --database-url "$CONTROL_PLANE_DATABASE_URL"

# materialize released metadata/config
fabric-framework metadata-materialize ...

# then start runtime with SqlAlchemyControlPlaneRepository
```

`SqlAlchemyControlPlaneRepository(...)` requires:

```text
current_schema_version == CONTROL_PLANE_SCHEMA_VERSION
```

If not, construction fails.

This preserves the production certification invariant that validation/runtime startup cannot hide an unapplied migration.

---

## 3. Runtime configuration catalog

Example:

```python
from sqlalchemy import create_engine
from fabric_data_framework import SqlAlchemyControlPlaneRepository

engine = create_engine(control_plane_url)
configs = load_released_domain_configs()

repository = SqlAlchemyControlPlaneRepository(
    engine,
    domain="customer",
    domain_git_sha=domain_git_sha,
    framework_version="0.4.0",
    configs=configs,
)
```

For every dataset read, the repository checks:

```text
dataset exists in relational control plane
released catalog contains dataset_id
SQL config_hash == released DatasetConfig.config_hash
SQL domain == runtime domain
```

A deployed row cannot silently override the released semantic object.

`deploy_dataset()` exists as an explicit deployment/materialization operation and updates the local catalog. It should not be called as a hidden runtime read side effect.

---

## 4. Durable runtime evidence

The SQL repository persists or reads the runtime evidence required by dispatcher and Fabric execution:

```text
pipeline_run
dataset_run
step_run
capture_receipt
reconciliation_result
quarantine_batch
dataset_attempt_lineage
reprocess_request
watermark compatibility state
```

The existing dedicated modules remain authoritative for stronger specialized semantics:

```text
control_plane_io.py
    CDC checkpoint CAS
    replay marker semantics

 target_operation_io.py
    target-operation CAS/journal
```

Do not duplicate those state machines inside the generic repository.

---

## 5. Lifecycle update semantics

### Pipeline run

The same `pipeline_run_id` may transition from `RUNNING` to a terminal pipeline status.

Immutable identity includes:

```text
environment
domain
run_mode
domain_git_sha
framework_version
config_bundle_hash
```

A later write that changes those values is rejected.

### Dataset run

The same `dataset_run_id` may transition from `RUNNING` to a terminal dataset status.

Immutable identity includes:

```text
pipeline_run_id
dataset_id
attempt
effective_config_hash
```

Status, row accounting, mutation counts, error fields, retryability and completion time may advance.

### Step run

A step identity is bound to:

```text
dataset_run_id
step_name
```

The status/details/completion evidence may be updated without changing semantic identity.

---

## 6. Durable DatasetDispatchOutcome

The repository exposes:

```python
repository.get_dataset_outcome(dataset_run_id)
```

This reads `dataset_run` and returns the stable orchestration contract:

```text
dataset_run_id
status
retryable
error_code
error_message
```

This is the key child/parent bridge for Fabric Pipeline execution.

---

## 7. Fabric child/parent handoff

The intended live topology is:

```text
parent framework dispatcher
    -> FabricPipelineBackend
    -> Fabric Data Pipeline child

child runtime
    -> execute dataset stages
    -> target operation/reconciliation/state gates
    -> write terminal DatasetRunAudit through SQL repository

Fabric provider
    -> returns Completed

parent
    -> repository.get_dataset_outcome(exact dataset_run_id)
    -> require terminal semantic outcome
    -> attach native job/root correlation as StepRunAudit
```

This is deliberately stronger than trusting the Fabric job status.

If Fabric says `Completed` but no matching SQL dataset outcome exists, the parent fails closed.

---

## 8. Run mode fidelity

`PipelineRunAudit` now carries `run_mode` because the relational `pipeline_run` table already requires it.

The dispatcher passes the requested run mode into every RUNNING/FAILED/final pipeline audit.

This matters for:

```text
RETRY
BACKFILL
REPLAY
FULL_REBUILD
```

A non-normal execution must never be stored as a normal production run merely because an older audit model omitted the field.

---

## 9. Watermark compatibility warning

The original `ControlPlaneRepository` Protocol contains:

```python
commit_watermark(dataset_id, position)
```

That older shape does not carry a `StateCommitGate`, committing dataset run identity or expected version.

Therefore the SQL repository implements it only as a compatibility surface. New stateful production execution must use the dedicated gated/CAS state primitives where correctness depends on concurrency and commit proof.

Do not treat the generic compatibility method as a substitute for the stronger state contracts.

---

## 10. Production backend certification

A SQL repository implementation does not itself certify the physical database.

Before production use, the actual instance must independently pass:

```text
control-plane schema/version checks
transaction rollback probe
target-operation CAS probe
CDC checkpoint CAS probe
backend service identity evidence
IAM/access evidence
network security evidence
backup/restore evidence
availability/recovery evidence
monitoring/alerting evidence
retention/governance evidence
```

See `CONTROL_PLANE_CERTIFICATION.md`.

SQLite remains reference-only.

---

## 11. Current evidence boundary

CI/reference proof can establish:

```text
runtime refuses unmigrated schema
released config hash mismatch fails closed
pipeline/dataset/step lifecycle writes are durable
semantic identities cannot be rewritten
provider details survive in step_run.details
DatasetDispatchOutcome is readable from SQL
Fabric child/parent handoff works against reference SQLAlchemy storage
non-normal run_mode is persisted by dispatcher
```

It still does not prove:

```text
Fabric SQL Database / Azure SQL Database driver behavior
real concurrent transaction behavior beyond certification probes
real Entra authentication
network/failover/restore behavior
live Fabric Pipeline child execution
live cross-process timing between provider completion and SQL outcome commit
```

Correct label after CI: `IMPLEMENTED + CI PROVEN RELATIONAL RUNTIME`, not `PRODUCTION DB PROVEN`.
