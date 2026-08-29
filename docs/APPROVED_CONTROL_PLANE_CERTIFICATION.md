# Approved Control-Plane Certification Runner

Status: implementation/runbook checkpoint  
Last updated: 2026-08-29

## Purpose

This command bridges the exact-release approved integration configuration to the existing production control-plane certification contract without putting a database URL on the command line or in source control.

```text
ApprovedIntegrationRunnerConfig
  control_plane_profile
  control_plane_database_url_env_var
        ↓
exact IntegrationEvidenceSpec / release_hash
        ↓
explicit conformance-write authorization
        ↓
runtime environment lookup
        ↓
certify_control_plane_backend(..., run_conformance=True)
        ↓
safety-validated certification report
        ↓
CONTROL_PLANE_CERTIFICATION partial IntegrationEvidenceManifest
        ↓
integration-evidence-merge
```

The runner never migrates the database. The selected database must already have the exact framework control-plane schema.

## Source-controlled configuration

The approved runner config stores the **name** of the environment variable, never its value:

```json
{
  "environment": "DEV",
  "domain": "customer",
  "framework_version": "0.4.0",
  "release_hash": "<64 hex candidate hash>",
  "control_plane_database_url_env_var": "CONTROL_PLANE_DATABASE_URL",
  "control_plane_profile": "fabric_sql_database_v1"
}
```

Allowed production-candidate profiles remain:

```text
fabric_sql_database_v1
azure_sql_database_v1
```

The approved evidence runner rejects reference-only profiles such as `sqlite_reference_v1`.

## External evidence

Production certification also requires retained references for:

```text
backend service identity
identity / access control
network security
backup / restore drill
availability / recovery
monitoring / alerting
retention / governance
```

Example file shape:

```json
{
  "backend_service_identity_reference": "inventory:fabric-sql-dev",
  "identity_access_control_reference": "ticket:iam-123",
  "network_security_reference": "ticket:network-123",
  "backup_restore_reference": "drill:restore-123",
  "availability_recovery_reference": "drill:ha-123",
  "monitoring_alerting_reference": "runbook:monitoring-123",
  "retention_governance_reference": "policy:retention-123"
}
```

These values are references, not credentials. Credential-like text, signed URLs and URI user-info credentials are rejected before retention.

## Command

Set the runtime secret outside source control:

```bash
export CONTROL_PLANE_DATABASE_URL='<approved runtime SQLAlchemy URL>'
```

Then execute the selected evidence check:

```bash
fabric-framework integration-control-plane-certify-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --check-id control-plane.certify \
  --external-evidence evidence/control-plane-external.json \
  --evidence-reference artifact:control-plane-certification \
  --report-output evidence/control-plane-certification-report.json \
  --output evidence/control-plane-partial.json \
  --allow-conformance-writes
```

`--allow-conformance-writes` is mandatory because certification executes temporary transaction rollback and optimistic-CAS probes. The probes use reserved certification rows and clean them up; they must still run only in an approved certification environment/database.

## Fail-closed behavior

Execution is rejected before certification when:

```text
runner config and spec environment/domain/framework/release differ
selected check is not CONTROL_PLANE_CERTIFICATION
runtime DB env-var is absent/blank
conformance writes are not explicitly authorized
profile is not production eligible
external evidence is incomplete
retained references look credential-bearing
```

Database/driver exceptions occur inside the integration evidence harness. Raw exception text is not copied into the partial manifest; the retained failure contains only the exception type. A certification report is written only after its retained text passes the evidence-safety check.

A failed certification report is still useful retained evidence and yields a `FAIL` partial manifest. It does not certify the release.

## Merge into staged evidence

After a PASS result:

```bash
fabric-framework integration-evidence-merge \
  --spec evidence-spec.json \
  --input evidence/item-read-partial.json \
  --input evidence/control-plane-partial.json \
  --output evidence/merged.json
```

The existing strict merge rules still apply. Contradictory reruns are never silently resolved by latest/PASS/FAIL precedence; explicitly choose the intended rerun artifact.

## Evidence language

Passing deterministic CI for this command proves only:

```text
IMPLEMENTED + CI PROVEN APPROVED CONTROL-PLANE CERTIFICATION RUNNER CONTRACT
```

It becomes `PRODUCTION DB PROVEN` only after a retained run against the selected real approved backend, exact release hash and required enterprise evidence.
