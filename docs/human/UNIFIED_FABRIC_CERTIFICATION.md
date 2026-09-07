# Unified Fabric Certification

This is the default operator path for validating an exact Framework wheel in a real Microsoft Fabric environment.

The goal is simple: **CI proves reusable code contracts; the unified runner re-proves environment-facing boundaries for the exact installed wheel in real Fabric without making an operator copy many notebook cells or manually invent PASS evidence.**

Framework developers who need a start-to-finish procedural runbook should use [`FRAMEWORK_DEVELOPER_CERTIFICATION.md`](FRAMEWORK_DEVELOPER_CERTIFICATION.md). This document defines the unified runner contract and operational semantics.

## 1. Default notebook experience

Put the exact Framework artifact in the conventional attached-Lakehouse directory:

```text
/lakehouse/default/Files/framework_cert/
  CANDIDATE.json
  fabric_data_framework-<version>-py3-none-any.whl
  SHA256SUMS
```

Install that exact wheel in the Fabric Environment/runtime, then prefer:

```python
from fabric_data_framework.certification import certify_installed, print_certification_summary

report = certify_installed(
    spark=spark,
    certification_root="/lakehouse/default/Files/framework_cert",
)
print_certification_summary(report)
```

The compatibility convenience API remains:

```python
from fabric_data_framework.certification import certify, print_certification_summary
report = certify(spark=spark)
print_certification_summary(report)
```

With only the Framework artifact present, certification executes the self-contained/bounded path:

```text
installed package vs exact wheel byte attestation
metadata/config smoke
incremental watermark smoke
CDC normalization/dedup smoke
Lakehouse Delta write/read
FULL -> REPLACE + incomplete-FULL destructive guard
WATERMARK -> SCD1
WATERMARK -> SCD2
retry / idempotency
reconciliation fail-closed
```

No manual PASS dropdown is required.

### Important: no SQL Database auto-discovery

The runner does **not** scan the Fabric workspace and choose a SQL Database, Warehouse or Pipeline.

Without an optional integration-input bundle, the run is bounded/self-contained and no Control Plane SQL Database is contacted.

## 2. Optional environment-dependent integration bundle

Historical code and CLI surfaces use the name:

```text
customer-inputs/
--customer-inputs
```

That spelling is retained for backward compatibility only. Architecturally it now means:

> optional framework certification integration-input bundle.

It is owned by the framework certification lifecycle, not by the `fabric-customer` source simulator.

A bundle may contain exact runtime declarations/recipes such as:

```text
INPUTS.json
runner-config.json
release-manifest.json
project/
dist/
```

The unified runner validates that the integration bundle is bound to the same Framework candidate identity before any live provider stage runs.

## 3. Full environment certification

For an approved disposable/certification environment where ordinary live mutations are authorized:

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

The variables should come from the organization's approved runtime secret/credential mechanism. Do not hard-code real secrets into the Notebook or source-controlled integration input.

When `runtime_environment` is omitted, the unified runner falls back to the current process environment for names declared by the exact runner config.

Depending on configured prerequisites and authorization, the runner may attempt in dependency order:

```text
bounded exact-wheel suite
Fabric item read / authorization smoke
real Control Plane reference conformance
reviewed Control Plane certification
Fabric Pipeline
Fabric Copy capture
Fabric Spark capture
Warehouse normal commit
Warehouse ambiguous-COMMIT recovery drill
representative live business paths:
  full.replace
  watermark.scd1
  watermark.scd2
  retry.idempotency
  reconciliation.fail_closed
```

It reuses approved Framework runners; it does not maintain a second implementation of Pipeline, Capture, Warehouse, recovery or business-path semantics.

## 4. Physical resources and runtime values

Physical Fabric IDs, dataset selections and execution/fault recipes belong in the exact integration-input bundle. The notebook operator should not type them repeatedly.

The resolution model is intentionally split:

```text
source-controlled exact integration bundle
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

Typical runtime names may include:

```text
CONTROL_PLANE_DATABASE_URL
WAREHOUSE_DATABASE_URL
WAREHOUSE_ADMIN_DATABASE_URL
FABRIC_ACCESS_TOKEN
```

The source-controlled runner config contains environment-variable **names**, not secret values.

Conceptually, SQL Database selection is:

```text
runner-config.json
  control_plane_database_url_env_var = CONTROL_PLANE_DATABASE_URL

runtime_environment/process environment
  CONTROL_PLANE_DATABASE_URL = <actual approved certification SQL Database URL>
```

If the runtime value is missing, the check remains not ready/blocked. The Framework does not search for another database.

For Fabric REST access, the runner first honors the configured token environment variable. In a Fabric Notebook it may use current NotebookUtils Fabric/Power BI identity when supported and no explicit token was supplied. Tokens are not written into retained reports.

Do not place passwords, bearer tokens, connection strings or signed URLs into retained evidence references.

## 5. Control Plane migration is separate

Certification must not silently migrate a shared/production database.

For a newly created dedicated certification Control Plane, schema bootstrap requires explicit authorization:

```python
report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
    allow_control_plane_migration=True,
)
```

Once the schema is already deployed, leave `allow_control_plane_migration=False` on normal reruns.

## 6. Warehouse session termination stays separately authorized

`allow_live_mutations=True` does not silently grant Admin-level exact-session termination authority.

If, and only if, governance approves the reviewed Warehouse fault recipe:

```python
report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
    allow_warehouse_session_termination=True,
)
```

Never enable this against shared or production resources merely to make a check green.

## 7. External enterprise evidence is not automatable into existence

The runner may consume reviewed Control Plane evidence such as identity/access, network security, backup/restore, availability/recovery, monitoring/alerting and retention/governance.

It cannot infer those controls from a successful SQL connection. Missing or unbound evidence is `BLOCKED`; the runner does not manufacture PASS.

The same rule applies to a missing real Warehouse fault controller.

## 8. Result semantics

Every stage has one of four statuses:

```text
PASS      the actual check executed and passed
FAIL      the actual check executed and failed
NOT_RUN   intentionally not executed because authorization/prerequisites were absent
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

## 9. Why CI and real Fabric both exist

Do not run the entire Framework pytest suite in a Fabric Notebook merely to repeat CI. PR/main CI remains responsible for deterministic unit, contract, recovery, package-boundary and failure-path tests.

Real Fabric reruns the boundaries CI cannot prove:

```text
exact candidate bytes installed in Fabric
real Lakehouse Delta behavior
real Fabric identity/REST authorization
real Fabric SQL transaction/CAS behavior
real Pipeline/Copy/Spark execution
real Warehouse commit/recovery behavior
```

Until those exact environment calls execute and retained evidence exists for the exact wheel bytes, report `FABRIC CERTIFICATION REQUIRED`.

## 10. Relationship to fabric-customer

`fabric-customer` may optionally provide a separate realistic source workload for end-to-end implementation testing. Its `workload_digest` can bind v1/v2 scenario comparisons.

That is a different lifecycle:

```text
framework certification
  proves framework wheel/environment behavior

customer scenario validation
  proves an implementation against frozen realistic source facts
```

Neither repository needs to import the other to perform its owned responsibility.
