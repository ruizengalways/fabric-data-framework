# Testing and certification

This is the canonical document for proving framework behavior from source tests through exact-wheel real Microsoft Fabric certification.

## 1. Keep the gates separate

```text
source tests
!= installed-wheel acceptance
!= real Fabric certification
!= release authorization
```

A green source CI run does not prove the wheel package. A clean installed-wheel PASS does not prove Fabric services. A Fabric certification report does not by itself publish or authorize a release.

## 2. Source-level development gate

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check src tests
```

This validates repository source code and contracts. Editable imports are allowed here.

## 3. Build the exact wheel

```bash
python -m pip install build
python -m build --wheel
```

CI retains exact candidate provenance such as Git SHA, wheel filename, wheel SHA256 and `CANDIDATE.json`.

The wheel SHA256 identifies executable framework bytes. Transport ZIP digests or version strings do not replace it.

## 4. Clean installed-wheel acceptance

Use an interpreter that does not import the repository source tree:

```bash
python -m venv .cert-venv
.cert-venv/bin/python -m pip install dist/fabric_data_framework-*.whl
.cert-venv/bin/python -m pip check
.cert-venv/bin/python certification/smoke_installed_wheel.py \
  --wheel dist/fabric_data_framework-*.whl
```

The smoke verifies every regular `fabric_data_framework` package file in the active installation against the same file in the candidate wheel, then runs self-contained framework semantic probes.

If installed package bytes differ from the candidate wheel, certification stops before live Fabric mutation.

## 5. Real Fabric certification root

Use a dedicated DEV certification environment and an attached Lakehouse.

Conventional layout:

```text
/lakehouse/default/Files/framework_cert/
  CANDIDATE.json
  exactly one fabric_data_framework-*.whl
  integration-inputs/        # optional framework-owned exact bundle
  certification-output/      # generated evidence
```

Install the exact wheel in the Fabric Environment, Publish, and restart the runtime if required.

## 6. Minimal installed-wheel Fabric entry point

```python
from fabric_data_framework.certification import certify_installed, print_certification_summary

report = certify_installed(
    spark=spark,
    certification_root="/lakehouse/default/Files/framework_cert",
)
print_certification_summary(report)
```

`certify_installed()` first attests the active installed package against the wheel, runs semantic acceptance, then delegates to the Fabric certification runtime.

With no integration-input bundle, the run remains bounded/self-contained.

## 7. Bounded real-Fabric suite

The bounded suite proves the safest framework-owned Fabric boundaries for the exact artifact, including:

```text
exact CANDIDATE/wheel identity
Lakehouse Delta write/read
FULL -> REPLACE and incomplete-FULL destructive guard
WATERMARK -> SCD1
WATERMARK -> SCD2
retry/idempotency
reconciliation fail-closed
```

Installed semantic preflight additionally covers framework-owned metadata/config, incremental watermark and CDC normalization/deduplication contracts.

These checks require actual Fabric execution before they can be marked Fabric-proven.

## 8. Discover and review DEV Fabric item bindings

Environment-dependent certification needs exact physical IDs for one approved workspace and four readable/executable Fabric items:

```text
workspace_id
item_read_id
pipeline_item_id     type=DataPipeline
copy_job_id          type=CopyJob
spark_job_id         type=SparkJobDefinition
```

Do not use example UUIDs and do not infer an ID from a display name manually. The framework provides a read-only discovery API that calls the Fabric Core List Items endpoint, follows pagination, requires an exact case-sensitive display-name and type match, and fails closed on zero or multiple matches. It never creates, updates, deletes or runs an item.

Inside a Fabric notebook, use a runtime token provider without retaining the token in the output:

```python
import notebookutils

from fabric_data_framework.certification import (
    discover_certification_bindings_from_names,
)

bindings = discover_certification_bindings_from_names(
    token_provider=lambda: notebookutils.credentials.getToken("pbi"),
    workspace_id="<dedicated-dev-certification-workspace-uuid>",
    item_read_name="<exact-readable-item-name>",
    item_read_type="Lakehouse",
    pipeline_name="<exact-certification-pipeline-name>",
    copy_job_name="<exact-certification-copy-job-name>",
    spark_job_name="<exact-certification-spark-job-name>",
)

print(bindings.model_dump_json(indent=2))
print(bindings.workflow_dispatch_inputs())
```

For a local/jumpbox CLI, place the token only in an environment variable; never pass a bearer token on the command line:

```bash
export FABRIC_ACCESS_TOKEN='<ephemeral-token>'

fabric-framework discover-certification-bindings \
  --workspace-id '<workspace-uuid>' \
  --item-read-name '<exact-readable-item-name>' \
  --item-read-type Lakehouse \
  --pipeline-name '<exact-pipeline-name>' \
  --copy-job-name '<exact-copy-job-name>' \
  --spark-job-name '<exact-spark-job-name>' \
  --output integration-bindings.json
```

Review `integration-bindings.json` against the dedicated DEV workspace before using its five UUID fields as inputs to `.github/workflows/candidate-integration-inputs.yml`. The discovery output is non-secret metadata, but it is still environment-specific configuration and should be reviewed like any other physical binding.

Discovery proves only that the principal can enumerate an exact item identity. It does **not** prove execution permission, item correctness, Control Plane availability, Warehouse access, business-path readiness or certification PASS.

## 9. Framework-owned integration inputs

Environment-dependent Control Plane, Pipeline, Copy, Spark, Warehouse and business-path checks use an exact framework-owned integration bundle.

The certification runtime resolves by default:

```text
framework_cert/integration-inputs/
```

or an explicit:

```python
integration_inputs_root="..."
```

The bundle carries non-secret configuration/recipes and must bind to the exact framework candidate. Framework certification identity is intentionally two-dimensional:

```text
framework_artifact_sha256
  exact candidate framework wheel bytes

integration_inputs_hash
  exact framework-owned integration configuration/recipe bundle
```

A customer/domain release identity does not participate in framework candidate certification.

## 10. Runtime-only values and secrets

The integration runner config declares allowed environment-variable names. Actual credential/connection values are supplied at runtime only.

Typical runtime names may include:

```text
FABRIC_ACCESS_TOKEN
CONTROL_PLANE_DATABASE_URL
WAREHOUSE_DATABASE_URL
WAREHOUSE_ADMIN_DATABASE_URL
```

Do not commit or retain:

```text
passwords
client secrets
bearer tokens
signed URLs
connection strings containing credentials
```

The one-call runtime mirrors only declared values into process environment for the duration of certification and restores previous process values afterward.

For Fabric-native SQL user authentication details, see [`reference/FABRIC_SQL_AUTH.md`](reference/FABRIC_SQL_AUTH.md).

## 11. Live mutation authorization

Normal environment-dependent live execution is explicit:

```python
report = certify_installed(
    spark=spark,
    certification_root="/lakehouse/default/Files/framework_cert",
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
)
```

Use only dedicated/approved certification resources.

A first-time dedicated certification Control Plane may additionally require:

```python
allow_control_plane_migration=True
```

This is not permission to silently migrate a shared or production database.

Warehouse Admin/exact-session termination remains a separate higher-risk authorization:

```python
allow_warehouse_session_termination=True
```

Do not infer Admin session-control permission from ordinary Warehouse or Fabric workspace access.

## 12. Environment-dependent stages

When the exact integration inputs and runtime prerequisites exist, the unified certification path may execute in dependency order:

```text
bounded exact-wheel suite
Fabric item read / authorization
Control Plane conformance/certification
Fabric Pipeline
Fabric Copy capture
Fabric Spark capture
Warehouse normal commit
Warehouse ambiguous-COMMIT recovery drill
representative business paths:
  full.replace
  watermark.scd1
  watermark.scd2
  retry.idempotency
  reconciliation.fail_closed
```

The framework reuses approved runners. It does not maintain a second implementation solely for certification.

## 13. Provider completion is not enough

Examples of necessary fail-closed boundaries:

```text
Fabric Pipeline Completed + no matching durable framework outcome != PASS
Copy/Spark provider success + no verified CaptureReceipt          != PASS
Warehouse call exception + unresolved target commit               != safe retry
```

The framework must prove its own semantic outcome for the exact run identity.

## 14. Result semantics

Certification/evidence uses explicit statuses such as:

```text
PASS      actual requested check executed and passed
FAIL      actual check executed and failed
NOT_RUN   intentionally not executed because authorization/prerequisite was absent
BLOCKED   required external/configuration prerequisite is unavailable
```

Missing real environment evidence is not converted into PASS.

Until exact real Fabric execution exists for the current executable artifact, use:

```text
FABRIC CERTIFICATION REQUIRED
```

## 15. Evidence rules

Retained evidence must preserve exact identity and reject contradictory reruns rather than use a “latest wins” or “PASS wins” rule.

Important evidence identities include:

```text
candidate Git/source provenance
framework_artifact_sha256
integration_inputs_hash
Fabric environment/workspace/item/run identities
non-secret evidence references
```

Any framework executable change produces new candidate bytes and requires new exact-byte evidence for release claims.

## 16. CI vs Fabric

CI should prove deterministic unit, contract, failure-path, package-boundary and installed-wheel behavior.

Real Fabric should prove boundaries CI cannot truthfully emulate:

```text
actual installed candidate bytes in Fabric
real Lakehouse Delta behavior
real Fabric identity/REST authorization
real SQL Control Plane transaction/CAS behavior
real Pipeline/Copy/Spark execution
real Warehouse commit/recovery behavior
```

Do not rerun the entire pytest suite inside a Notebook as a substitute for these environment proofs.

## 17. Framework certification vs simulator regression

`fabric-customer` may provide a frozen realistic source workload for implementation regression testing. Its `workload_digest` identifies source facts.

That lifecycle is separate:

```text
framework certification
  -> proves framework wheel + certification environment

implementation scenario validation
  -> proves a project against one verified source workload/truth set
```

The workload digest never replaces `framework_artifact_sha256`.

## 18. Release boundary

Certification always remains separate from release authorization. Continue with [`RELEASE.md`](RELEASE.md) for candidate freeze, readiness and exact-byte promotion.
