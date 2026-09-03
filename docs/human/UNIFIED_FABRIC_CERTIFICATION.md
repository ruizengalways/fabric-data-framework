# Unified Fabric Certification

This is the default operator path for validating an exact Framework wheel in a real Microsoft Fabric environment.

The goal is simple: **CI proves reusable code contracts; the unified runner re-proves the environment-facing boundaries for the exact wheel in real Fabric without making an operator copy many notebook cells or fill a certification form by hand.**

Framework developers who need a start-to-finish procedural runbook should use [`FRAMEWORK_DEVELOPER_CERTIFICATION.md`](FRAMEWORK_DEVELOPER_CERTIFICATION.md). This document defines the unified runner contract and operational semantics.

## 1. Default notebook experience

Put the exact Framework artifact in the conventional attached-Lakehouse directory:

```text
/lakehouse/default/Files/framework_cert/
  CANDIDATE.json
  fabric_data_framework-<version>-py3-none-any.whl
  SHA256SUMS
```

Then run:

```python
from fabric_data_framework.certification import certify, print_certification_summary

report = certify(spark=spark)
print_certification_summary(report)
```

With only the Framework artifact present, this automatically executes the bounded real-Fabric suite:

```text
exact installed candidate / wheel-byte identity
Lakehouse Delta write/read
FULL -> REPLACE + incomplete-FULL destructive guard
WATERMARK -> SCD1
WATERMARK -> SCD2
retry / idempotency
reconciliation fail-closed
```

The JSON report is written under:

```text
/lakehouse/default/Files/framework_cert/certification-output/
```

No manual PASS dropdown is required.

### Important: no SQL Database auto-discovery

`certify(spark=spark)` does **not** scan the Fabric workspace and choose a SQL Database.

If `customer-inputs/` is absent, the run is bounded-only and no Control Plane SQL Database is contacted.

If `customer-inputs/` exists, its exact `runner-config.json` declares which runtime environment-variable name represents the Control Plane database URL and which names represent Warehouse/runtime credentials. The actual runtime-only values must already exist in the process environment or be supplied explicitly through `runtime_environment`.

## 2. Full environment certification

The exact Customer certification input artifact produced for the same Framework candidate can be extracted under:

```text
/lakehouse/default/Files/framework_cert/customer-inputs/
  INPUTS.json
  runner-config.json
  release-manifest.json
  project/
  dist/
```

The unified runner verifies that the Customer bundle binds the same candidate Git SHA, wheel SHA256 and Framework version before any live provider stage runs.

For an approved disposable/certification environment where the ordinary live mutations are authorized:

```python
from fabric_data_framework.certification import certify, print_certification_summary

runtime_environment = {
    "CONTROL_PLANE_DATABASE_URL": control_plane_database_url,
    "WAREHOUSE_DATABASE_URL": warehouse_database_url,
}

report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
)
print_certification_summary(report)
```

The variables `control_plane_database_url` and `warehouse_database_url` should come from the organization's approved runtime secret/credential mechanism. Do not hard-code real secrets into the Notebook or source-controlled configuration.

When `runtime_environment` is omitted, the unified runner falls back to the current process environment.

The runner then attempts, in dependency order:

```text
bounded exact-wheel suite
Fabric item read / authorization smoke
real Control Plane reference conformance
reviewed production Control Plane certification
Fabric Pipeline
Fabric Copy capture
Fabric Spark capture
Warehouse normal commit
Warehouse ambiguous-COMMIT recovery drill
five representative live business paths:
  full.replace
  watermark.scd1
  watermark.scd2
  retry.idempotency
  reconciliation.fail_closed
```

It reuses the existing approved runners; it does not maintain a second implementation of Pipeline, Capture, Warehouse, recovery or business-path semantics.

## 3. How physical resources and runtime values are resolved

Physical Fabric IDs, dataset selections and execution recipes belong in the exact Customer certification input bundle. The notebook operator should not type them repeatedly.

The resolution model is intentionally split:

```text
source-controlled exact Customer bundle
  -> environment name
  -> Control Plane profile
  -> workspace/item IDs
  -> dataset selections
  -> execution/fault/business-path recipes
  -> names of required runtime environment variables

runtime-only environment
  -> actual Control Plane database URL
  -> actual Warehouse database URL
  -> optional Warehouse Admin database URL
  -> optional explicit Fabric access token
```

For the reference Customer certification harness, the normal runtime names are:

```text
CONTROL_PLANE_DATABASE_URL
WAREHOUSE_DATABASE_URL
WAREHOUSE_ADMIN_DATABASE_URL   # only when the reviewed session-termination recipe requires it
FABRIC_ACCESS_TOKEN            # optional explicit token; Notebook execution may obtain current Fabric identity
```

The source-controlled runner config contains environment-variable **names**, not secret values.

Conceptually, SQL Database selection is therefore:

```text
runner-config.json
  control_plane_database_url_env_var = CONTROL_PLANE_DATABASE_URL

runtime_environment/process environment
  CONTROL_PLANE_DATABASE_URL = <actual approved Control Plane SQL Database URL>
```

If that runtime value is missing, the check remains not ready/blocked. The Framework does not search for another database.

For Fabric REST access, the runner first honors the configured access-token environment variable. In a Fabric Notebook it can also try the current NotebookUtils Fabric/Power BI token when no explicit token was supplied. The token is not written into the certification report.

Do not place passwords, bearer tokens, connection strings or signed URLs into retained evidence references.

## 4. Control Plane migration is separate

Production Control Plane certification historically does not silently migrate a database. The unified runner preserves that boundary.

For a newly created dedicated certification Control Plane database, schema bootstrap must be an explicit decision:

```python
report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
    allow_control_plane_migration=True,
)
```

Once the schema is already deployed, leave `allow_control_plane_migration=False` on normal certification reruns.

## 5. Warehouse session termination stays separately authorized

`allow_live_mutations=True` may run the reviewed ordinary certification mutations and the configured ambiguous-COMMIT fault drill. It does **not** silently grant Admin-level exact-session termination authority.

If, and only if, company governance has approved the reviewed Warehouse fault recipe to terminate the exact certification session:

```python
runtime_environment = {
    "CONTROL_PLANE_DATABASE_URL": control_plane_database_url,
    "WAREHOUSE_DATABASE_URL": warehouse_database_url,
    "WAREHOUSE_ADMIN_DATABASE_URL": warehouse_admin_database_url,
}

report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
    allow_warehouse_session_termination=True,
)
```

Never enable this against shared or production resources merely to make a check green.

## 6. External enterprise evidence is not automatable into existence

The runner can consume and validate the seven reviewed Control Plane evidence references:

```text
backend service identity
identity / access control
network security
backup / restore
availability / recovery
monitoring / alerting
retention / governance
```

It cannot infer those controls from a successful SQL connection. If the exact Customer input bundle still reports incomplete or unbound external evidence, the unified report shows that condition as `BLOCKED`; it does not manufacture PASS.

The same rule applies to a missing real Warehouse fault controller.

## 7. Result semantics

Every stage has one of four statuses:

```text
PASS      the actual check executed and passed
FAIL      the actual check executed and failed
NOT_RUN   intentionally not executed, usually because authorization/prerequisites were absent
BLOCKED   a required external/configuration prerequisite is not ready
```

Overall status is fail-closed:

- any real `FAIL` -> overall `FAIL`;
- PASS plus blocked/not-run stages -> `PARTIAL`;
- all requested/available stages PASS -> `PASS`.

A unified report always retains:

```text
release_authorized = false
```

Certification execution never freezes a candidate and never publishes a release.

## 8. Why CI and real Fabric both exist

Do not run the full Framework pytest suite in a Fabric Notebook merely to repeat CI. PR/main CI remains responsible for hundreds of deterministic unit, contract, recovery, package-boundary and failure-path tests.

Real Fabric reruns the boundaries CI cannot prove:

```text
exact candidate bytes install in Fabric
real Lakehouse Delta behavior
real Fabric REST authorization
real Fabric SQL transaction/CAS behavior
real Pipeline/Copy/Spark execution
real Warehouse commit/recovery behavior
real representative end-to-end business paths
```

This is complementary evidence, not duplicate test theater.

## 9. Manual runbook is now troubleshooting/reference

`FIRST_FABRIC_NOTEBOOK_TEST.md` retains the explicit cells so individual probes can be isolated when debugging an unexpected failure or when validating an older wheel that predates the unified runner.

For new candidate bytes, start with this unified runner instead of copying the cells one by one.

## 10. Exact-byte rule after Framework changes

Real-Fabric evidence belongs to the exact tested wheel. If Framework code changes, build a new main artifact and run certification again. Results from an older wheel remain historical evidence only and must not be relabeled as proof for new bytes.
