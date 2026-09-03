# Framework Developer Certification Runbook

Audience: engineers developing `fabric-data-framework` who need to certify a changed Framework build in real Microsoft Fabric before release evidence can be considered complete.

This document is intentionally procedural. A new engineer should be able to follow it from a Framework code change through CI, exact-artifact selection, Fabric execution, result review and handoff without relying on chat history.

## 1. The mental model

There are three different things and they must not be mixed:

```text
PR/main CI
  proves deterministic code, package and contract behavior

bounded Fabric certification
  proves the exact wheel can run the core Framework semantics in real Fabric/Lakehouse

full environment certification
  additionally proves the configured real Control Plane, Fabric items, Warehouse and five live business paths
```

A green CI run is not real-Fabric evidence. A green bounded Fabric run is not full release evidence. A certification run never freezes or releases a candidate.

## 2. Important answer: how does `certify(spark=spark)` know which SQL Database to use?

It does **not** discover or guess a SQL Database.

The default call:

```python
from fabric_data_framework.certification import certify, print_certification_summary

report = certify(spark=spark)
print_certification_summary(report)
```

looks only in the conventional Lakehouse directory:

```text
/lakehouse/default/Files/framework_cert/
```

It requires one exact Framework wheel plus `CANDIDATE.json`.

If this directory does **not** contain:

```text
customer-inputs/
```

then the runner executes the bounded suite only. SQL Control Plane, Pipeline, Copy, Spark, Warehouse and live business-path stages remain `NOT_RUN`/`BLOCKED` as appropriate. No SQL Database is contacted.

When `customer-inputs/` exists, the chain is:

```text
customer-inputs/runner-config.json
  -> declares control_plane_profile
  -> declares the runtime environment-variable name for the Control Plane database URL
  -> declares physical workspace/item IDs for Fabric items

runtime environment
  -> supplies the actual process-local database URL value

unified runner
  -> reads the configured environment-variable name
  -> uses that exact runtime value
```

For the reference Customer certification harness, the normal names are:

```text
CONTROL_PLANE_DATABASE_URL
WAREHOUSE_DATABASE_URL
WAREHOUSE_ADMIN_DATABASE_URL
FABRIC_ACCESS_TOKEN
```

The source-controlled Customer bundle contains the **names**, not the secret values.

Therefore:

```text
certify(spark=spark)
```

means:

> run the fullest safe certification that can be resolved from the conventional certification directory and current runtime environment.

It does not mean:

> scan my workspace and automatically choose a SQL Database.

## 3. Developer flow overview

Follow this order after changing Framework code:

```text
1. develop locally
2. run local tests
3. open PR
4. require PR CI success
5. merge to main
6. require independent main CI success
7. use the exact main wheel artifact from that run
8. upload the exact artifact to an isolated Fabric certification workspace
9. run bounded certification first
10. prepare/extract exact Customer certification inputs for the same Framework bytes
11. provide runtime-only Control Plane/Warehouse connectivity
12. run full certification only with approved mutation permissions
13. review one unified report
14. retain permitted evidence/reference
15. do not infer candidate freeze or release authorization
```

If Framework source changes after step 6, start again from a new exact main artifact. Old Fabric results belong only to the old wheel bytes.

## 4. Before opening the PR

From the Framework repository, run the normal local verification appropriate for your change. At minimum the repository must remain compatible with the normal CI lanes.

Do not certify a locally hand-built wheel as release evidence when a main CI artifact is expected. Local testing is development feedback; the real Fabric candidate should come from a successful Framework `main` CI run so source SHA and wheel bytes are independently retained.

## 5. PR and main CI

The normal sequence is:

```text
feature branch
  -> pull request
  -> framework-ci PASS
  -> merge
  -> independent framework-ci push run on main PASS
```

The main run must include successful Framework test lanes and wheel build.

For real Fabric certification, record the exact main run identity:

```text
main Git SHA
workflow run ID
artifact name
wheel filename
wheel SHA256 from CANDIDATE.json/SHA256SUMS
```

Do not use an older successful artifact merely because the package version string is still `0.4.0`. Exact wheel bytes are the identity boundary.

## 6. Download the exact Framework artifact

From the successful Framework `main` CI run, download:

```text
framework-wheel-<40-character-main-SHA>
```

It must contain:

```text
fabric_data_framework-<version>-py3-none-any.whl
CANDIDATE.json
SHA256SUMS
```

Keep those three files together.

`CANDIDATE.json` binds the wheel to the exact Framework source SHA and workflow run. `SHA256SUMS` verifies the built file bytes.

## 7. Prepare an isolated Fabric certification workspace

Use a disposable or explicitly approved certification environment, normally DEV first.

Prepare the resources required for the level of certification you intend to run.

For bounded certification:

```text
[ ] Fabric Notebook
[ ] attached default Lakehouse
[ ] write/read permission under Files/framework_cert/
```

For full certification the approved Customer input bundle may additionally reference pre-provisioned resources such as:

```text
[ ] existing Fabric item for read-only identity smoke
[ ] certification Pipeline
[ ] certification Copy item/job
[ ] certification Spark job definition
[ ] dedicated Control Plane SQL Database
[ ] dedicated certification Warehouse
[ ] certification source/target/progress/control tables required by the Customer recipes
[ ] reviewed external Control Plane evidence when release policy requires it
[ ] approved Warehouse fault controller for ambiguous-COMMIT evidence
```

The Framework runner does not silently create enterprise infrastructure just to make a check pass.

## 8. Upload the Framework artifact

Create:

```text
/lakehouse/default/Files/framework_cert/
```

Upload:

```text
CANDIDATE.json
SHA256SUMS
fabric_data_framework-<version>-py3-none-any.whl
```

There must be exactly one `fabric_data_framework-*.whl` in the certification root. The public API deliberately rejects an ambiguous directory containing multiple Framework wheels.

Install the exact wheel using the normal Fabric notebook package mechanism, for example:

```text
%pip install /lakehouse/default/Files/framework_cert/fabric_data_framework-0.4.0-py3-none-any.whl
```

Restart the Python session if Fabric requires it after installation.

## 9. Run bounded certification first

Run:

```python
from fabric_data_framework.certification import certify, print_certification_summary

report = certify(spark=spark)
print_certification_summary(report)
```

Expected bounded checks include:

```text
identity.exact
lakehouse.smoke
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

The output is written under:

```text
/lakehouse/default/Files/framework_cert/certification-output/
```

If only the Framework artifact is present, an overall `PARTIAL` result is normal because environment-specific stages were not configured. Inspect individual check statuses; do not interpret `PARTIAL` as a bounded Framework failure when all bounded checks are PASS and the remaining stages are legitimately `NOT_RUN`/`BLOCKED`.

Stop and investigate any real bounded `FAIL` before attempting privileged/full certification.

## 10. Prepare the exact Customer certification input bundle

Full certification intentionally separates generic Framework code from environment/domain configuration.

The reference certification harness lives in `fabric-customer` and owns:

```text
physical Fabric workspace/item IDs
representative certification datasets
Pipeline/Copy/Spark recipes
Warehouse mutation/fault recipes
five business-path scenarios
a bounded Customer certification extension wheel
Control Plane profile selection
credential-free runtime environment-variable names
```

The Customer candidate-input workflow/build process binds those values to:

```text
the exact Framework candidate Git SHA
the exact Framework wheel SHA256
the exact Customer Git SHA
the exact Customer/domain release hash
```

Extract the resulting exact bundle to:

```text
/lakehouse/default/Files/framework_cert/customer-inputs/
```

Expected top-level layout:

```text
customer-inputs/
  INPUTS.json
  runner-config.json
  release-manifest.json
  project/
  dist/
```

The unified runner rejects a Customer bundle that does not match the Framework wheel currently being certified.

## 11. Understand `runner-config.json`

This file is the non-secret routing contract.

Conceptually it contains values like:

```json
{
  "environment": "DEV",
  "control_plane_profile": "fabric_sql_database_v1",
  "fabric_access_token_env_var": "FABRIC_ACCESS_TOKEN",
  "control_plane_database_url_env_var": "CONTROL_PLANE_DATABASE_URL",
  "warehouse_database_url_env_var": "WAREHOUSE_DATABASE_URL",
  "warehouse_admin_database_url_env_var": "WAREHOUSE_ADMIN_DATABASE_URL",
  "bindings": [
    {
      "check_id": "fabric.item.read",
      "workspace_id": "...",
      "item_id": "..."
    }
  ]
}
```

The exact file is generated by the Customer certification input builder. Do not manually edit exact retained input bundles after generation.

Notice what is deliberately absent:

```text
passwords
access tokens
secret connection strings
```

## 12. Supply the actual SQL Database and Warehouse runtime values

For full certification, the actual database URLs must come from an approved runtime-only secret source.

The public API now allows the runtime mapping to be explicit:

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

Here `control_plane_database_url` and `warehouse_database_url` should already be variables obtained from your organization's approved secret/credential mechanism. Do not hard-code real credentials into the Notebook or commit them to Git.

If `runtime_environment` is omitted, the runner reads the current process environment instead.

The runner checks required values for presence but does not retain their secret values in the run plan/report.

### Control Plane SQL Database selection

The Control Plane database is therefore selected by this exact pair:

```text
runner-config.json:
  control_plane_database_url_env_var = CONTROL_PLANE_DATABASE_URL

runtime_environment/process environment:
  CONTROL_PLANE_DATABASE_URL = <actual approved database URL>
```

If the runtime value is absent, the relevant check is blocked/not ready. The Framework does not pick another database.

### Warehouse selection

Warehouse works the same way:

```text
runner-config.json:
  warehouse_database_url_env_var = WAREHOUSE_DATABASE_URL

runtime_environment/process environment:
  WAREHOUSE_DATABASE_URL = <actual approved certification Warehouse URL>
```

Admin/session-control credentials, when required by the reviewed ambiguous-COMMIT recipe, remain separate.

## 13. Fabric REST identity

Physical workspace/item IDs come from `runner-config.json`.

Fabric REST authentication uses the configured token environment-variable name. In Fabric Notebook execution, the runner may also obtain the current Notebook Fabric/Power BI token when an explicit token was not supplied.

The token is runtime-only and must not appear in retained certification output.

## 14. Control Plane schema bootstrap

Certification does not silently migrate an existing production-eligible Control Plane database.

For a newly created dedicated certification database, and only when migration is explicitly intended:

```python
report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
    allow_control_plane_migration=True,
)
```

After the baseline schema exists, normal reruns should leave:

```text
allow_control_plane_migration=False
```

## 15. Full certification execution

Once the exact Customer bundle is present and ordinary certification mutations are approved:

```python
from fabric_data_framework.certification import certify, print_certification_summary

report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
)

print_certification_summary(report)
```

The runner attempts the configured stages in dependency order and emits one report.

The expected full surface includes:

```text
bounded Framework/Lakehouse checks
Fabric item read
Control Plane conformance/certification
Pipeline
Copy
Spark
Warehouse commit
Warehouse ambiguous-COMMIT drill
business.full.replace
business.watermark.scd1
business.watermark.scd2
business.retry.idempotency
business.reconciliation.fail_closed
```

A missing reviewed enterprise evidence set or unconfigured real fault controller remains `BLOCKED`. Do not replace it with synthetic PASS.

## 16. Warehouse session termination requires a separate approval

`allow_live_mutations=True` is not blanket admin permission.

If the reviewed Warehouse ambiguous-COMMIT recipe requires terminating the exact test session, that remains separately authorized:

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

Never enable this merely to get a green report against shared or production resources.

## 17. How to read the report

Every check has one of four states:

```text
PASS
FAIL
NOT_RUN
BLOCKED
```

Interpret them literally:

- `PASS`: the actual configured check executed and passed;
- `FAIL`: the actual check executed and failed;
- `NOT_RUN`: execution was intentionally skipped, commonly because authorization was not granted;
- `BLOCKED`: a required configuration/external prerequisite is not ready.

Overall status is fail-closed:

```text
any FAIL                         -> FAIL
PASS plus NOT_RUN/BLOCKED        -> PARTIAL
all applicable required checks PASS -> PASS
```

The report always keeps:

```text
release_authorized = false
```

A developer certification run does not freeze/select a candidate and does not publish `v0.4.0`.

## 18. What evidence may be retained

Retain only what company policy permits.

Useful non-secret anchors normally include:

```text
Framework main SHA
Framework CI run ID
wheel SHA256
Customer/domain release hash
check IDs and statuses
non-secret provider/run references
unresolved blocker names
```

Never retain secret values merely to make a report self-contained.

## 19. Stop conditions

Stop and investigate rather than overriding a real defect when any of these occur:

```text
candidate/wheel identity mismatch
Lakehouse write/read failure
FULL destructive guard failure
incorrect SCD1 result
incorrect SCD2 history/current invariant
retry creates duplicate mutation/history
forced reconciliation does not block state advance
Control Plane transaction/CAS conformance failure
Pipeline/Copy/Spark actual execution failure
Warehouse commit/recovery invariant failure
business-path evaluator failure
```

Missing permissions or unavailable external proof are different: those should remain `NOT_RUN`/`BLOCKED` until the prerequisite is genuinely available.

## 20. After certification

Record the exact tested identities and result class in the canonical machine/recovery documentation when the engineering slice materially changes current state.

If all you achieved was bounded certification, say bounded certification. If Warehouse or external enterprise evidence was not run, do not describe the candidate as Warehouse-proven or release-proven.

Before any release decision, separately follow the release-candidate/readiness governance. Full certification execution is evidence input; it is not release authorization.

## 21. Troubleshooting

If the unified runner fails unexpectedly, use:

```text
docs/human/FIRST_FABRIC_NOTEBOOK_TEST.md
```

for individual bounded probes, and use the corresponding approved runner/evidence documentation for provider-specific debugging.

Do not permanently replace the unified runner with ad-hoc notebook code. Fix the reusable runner/configuration contract when the problem is generic.

## 22. New-employee completion checklist

Before declaring the Framework certification work complete, verify:

```text
[ ] I developed and tested the Framework change locally
[ ] PR framework-ci passed
[ ] the change was merged
[ ] independent main framework-ci passed
[ ] I used the exact main CI artifact, not a random local wheel
[ ] CANDIDATE.json and wheel bytes matched
[ ] bounded Fabric checks passed
[ ] I understand that certify(spark=spark) does not auto-discover SQL databases
[ ] exact customer-inputs/ was generated for the same Framework bytes before full certification
[ ] Control Plane/Warehouse runtime URLs came from an approved runtime-only source
[ ] I did not commit credentials into Git or retained evidence
[ ] I enabled allow_live_mutations only in an approved certification environment
[ ] I enabled Warehouse session termination only with explicit separate approval
[ ] every PASS corresponds to a check that actually executed
[ ] unavailable prerequisites remained NOT_RUN/BLOCKED
[ ] I retained the exact Framework SHA/run/wheel hash with the result
[ ] I did not infer candidate freeze, release readiness or release authorization from certification alone
```
