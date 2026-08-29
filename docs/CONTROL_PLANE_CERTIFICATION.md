# Control-Plane Backend Certification

Status: canonical production-backend qualification contract for unreleased `0.4.0`

## Purpose

The framework requires a small relational control plane for definitions, runtime state, checkpoints, leases, recovery evidence, deployment evidence and the durable target-operation journal.

The framework does **not** make one database product part of the semantic API. Instead:

```text
framework contracts
    -> SQLAlchemy relational schema + transactions + expected-version CAS
    -> backend profile
    -> deterministic conformance
    -> enterprise external evidence
    -> production certification
```

This allows the same framework semantics to be used with a Fabric-native SQL Database deployment or an Azure SQL Database deployment without introducing different watermark, CDC or idempotency rules.

SQLite remains the local/CI reference backend only.

---

## 1. Certification levels

### Reference certified

A backend instance is `reference_certified` only when all deterministic checks pass, including temporary write probes:

```text
SQLAlchemy dialect matches selected profile
control-plane schema is exactly current version
all required tables exist
all declared migration versions are recorded
transaction rollback behaves atomically
stale target-operation expected-version writer is rejected
stale CDC-checkpoint expected-version writer is rejected
```

This proves the framework relational contract in the tested database instance.

It does not prove enterprise IAM, networking, backup/restore, HA/failover or monitoring.

### Production certified

A backend instance is `production_certified` only when:

```text
selected profile is production-eligible
AND reference_certified == true
AND all required external evidence references are present
```

Required external evidence categories:

```text
identity / access control
network security
backup + restore drill
availability / recovery
monitoring + alerting
retention / governance
```

An external-evidence JSON file records references to approved tickets, runbooks, drill results or platform evidence. The framework does not pretend to verify those enterprise systems from unit tests.

### Important invariant

> Passing all deterministic tests can never promote `sqlite_reference_v1` to production certification.

That rule is enforced in the typed backend profile.

---

## 2. Built-in backend profiles

### `sqlite_reference_v1`

Use for:

- deterministic CI;
- local development;
- framework semantics tests;
- migration/reference tests.

It is explicitly `production_eligible=False`.

### `fabric_sql_database_v1`

Fabric SQL Database is the preferred Fabric-native **candidate**, not an automatic certification. Microsoft documents SQL Database in Fabric as a transactional database built on the Azure SQL Database engine and supporting standard Transact-SQL access. That product shape fits the framework's small OLTP-style control-plane workload better than treating an analytical Warehouse as the operational state store.

Current product behavior and tenant/security constraints must be revalidated before deployment. Do not infer networking, encryption, availability or restore guarantees merely from T-SQL compatibility.

Microsoft references to re-check when deploying:

- SQL Database in Fabric overview: https://learn.microsoft.com/fabric/database/sql/overview
- SQL Database in Fabric limitations: https://learn.microsoft.com/fabric/database/sql/feature-comparison-sql-database-fabric
- SQL Database tutorial/connectivity: https://learn.microsoft.com/fabric/database/sql/tutorial-introduction

### `azure_sql_database_v1`

Azure SQL Database is the supported non-Fabric-native production candidate for organizations that want the control plane outside Fabric or require a deployment/security capability not satisfied by the current Fabric SQL Database environment.

It uses the same framework `mssql` SQLAlchemy family and must pass exactly the same framework conformance probes plus its own external enterprise evidence.

### Why Fabric Warehouse is not the default control-plane profile

Fabric Warehouse remains appropriate for analytical warehouse workloads, but the control plane is an operational/transactional state workload. Microsoft documents Warehouse-specific T-SQL and transaction limitations, and those constraints should not leak into watermark/CAS/idempotency semantics.

Reference:

- Fabric Data Warehouse limitations: https://learn.microsoft.com/fabric/data-warehouse/limitations
- Fabric Warehouse transactions: https://learn.microsoft.com/fabric/data-warehouse/transactions

A future Warehouse profile could be added only if it is explicitly certified against the full control-plane conformance suite. It is intentionally not assumed today.

---

## 3. Explicit migration before certification

Certification never silently migrates the database.

Correct deployment sequence:

```bash
fabric-framework control-plane-migrate \
  --database-url "$CONTROL_PLANE_DATABASE_URL"

fabric-framework control-plane-certify \
  --database-url "$CONTROL_PLANE_DATABASE_URL" \
  --profile <profile> \
  ...
```

Why keep these separate?

If certification automatically ran migrations, an operator could believe an old environment was already compliant when the certification command itself had changed it. Deployment mutation and validation must remain separate auditable steps.

If the database has no schema, an old schema, missing tables or missing migration history, certification reports failure and skips the destructive conformance probes.

---

## 4. Reference/CI conformance

For the local deterministic reference store:

```bash
fabric-framework control-plane-migrate \
  --database-url "sqlite:///control.db"

fabric-framework control-plane-certify \
  --database-url "sqlite:///control.db" \
  --profile sqlite_reference_v1 \
  --run-conformance \
  --require-reference-certified \
  --output control-plane-certification.json
```

`--run-conformance` performs temporary writes using reserved `__cert_*` dataset IDs. It tests rollback and CAS behavior, then cleans up its probe records.

Use this option only against a database/environment approved for certification probes.

Expected result:

```text
reference_certified = true
production_certified = false
```

---

## 5. Production-candidate conformance

Example Fabric SQL Database flow:

```bash
fabric-framework control-plane-migrate \
  --database-url "$FABRIC_SQL_DATABASE_URL"

fabric-framework control-plane-certify \
  --database-url "$FABRIC_SQL_DATABASE_URL" \
  --profile fabric_sql_database_v1 \
  --run-conformance \
  --external-evidence control-plane-external-evidence.json \
  --require-production-certified \
  --output control-plane-certification.json
```

Example Azure SQL Database flow is identical except:

```text
--profile azure_sql_database_v1
```

A production requirement cannot be requested without the explicit `--run-conformance` opt-in.

---

## 6. External evidence file

Example:

```json
{
  "identity_access_control_reference": "change:CHG-1234 / Entra group + managed identity review",
  "network_security_reference": "architecture:NET-82 / approved connectivity path",
  "backup_restore_reference": "drill:DR-2026-08-15 / restore evidence",
  "availability_recovery_reference": "runbook:CP-HA-01 / failover and recovery objective",
  "monitoring_alerting_reference": "monitor:CP-01 / availability + failed-run alerting",
  "retention_governance_reference": "policy:DATA-RET-07 / runtime evidence retention"
}
```

These values are references, not secrets. Do not place passwords, tokens, connection strings or private keys in this file.

The certification artifact should be retained with the release/deployment evidence for the environment that was tested.

---

## 7. What the conformance probes actually prove

### Transaction rollback

The suite inserts a unique reserved dataset row inside a transaction, rolls the transaction back, and proves that the row is not visible afterwards.

This detects a backend/configuration that does not provide the atomic transaction behavior assumed by framework state mutations.

### Target-operation CAS

The suite:

```text
claim semantic operation -> v1 IN_PROGRESS
mark UNKNOWN            -> v2 UNKNOWN
attempt stale v1 write  -> must fail
reconcile COMMITTED     -> v3 SUCCEEDED
```

This proves the backend preserves the expected-version behavior used to prevent stale retries from overwriting a newer operation outcome.

### CDC-checkpoint CAS

The suite:

```text
initial checkpoint -> version 1
advance checkpoint -> version 2
attempt version-1 writer again -> must fail
```

This proves stale downstream CDC progress cannot overwrite newer state.

### Probe cleanup

Certification probe rows are removed after each probe. Existing business dataset rows are not removed or rewritten by the suite.

---

## 8. What deterministic certification does not prove

Even against a real SQL backend, the conformance suite does not by itself prove:

- Entra/group/managed-identity governance;
- network isolation/private connectivity;
- firewall policy;
- credential rotation;
- backup retention and a successful restore drill;
- zone/region failure behavior;
- RPO/RTO;
- tenant/capacity quotas;
- alert routing and on-call response;
- privacy and evidence-retention policy;
- platform feature availability at a future deployment date.

Those are intentionally external evidence requirements.

---

## 9. Relationship to existing framework runtime

This certification layer does not create a third control-plane repository implementation.

Current framework code already has:

```text
control_plane.py
    relational schema + additive migrations

control_plane_io.py
    durable runtime-state persistence such as CDC checkpoint CAS

target_operation_io.py
    semantic target-operation CAS + event journal

operator.py
    typed read-only operational projections

repository.py
    older portable repository protocol/reference adapter for definition/run abstractions
```

Certification qualifies the relational engine backing the current durable SQLAlchemy primitives. It does not change the target-operation state machine, checkpoint semantics or operator read model.

Future refactoring may consolidate repository interfaces, but it must preserve these certified semantics rather than introduce a parallel source of truth.

---

## 10. Deployment decision rule

Recommended decision order:

```text
Need Fabric-native operational control plane?
    -> evaluate fabric_sql_database_v1

Enterprise requirement not satisfied by current Fabric SQL Database deployment?
    -> evaluate azure_sql_database_v1

Local development / CI only?
    -> sqlite_reference_v1

Analytical Warehouse because it already exists?
    -> do not use by convenience alone;
       first create and pass an explicit certified backend profile
```

The framework intentionally makes the **semantic contract stable while the physical control-plane product remains replaceable**.
