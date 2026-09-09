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
.cert-venv/bin/python certification_harness/smoke_installed_wheel.py \
  --wheel dist/fabric_data_framework-*.whl
```

The smoke verifies every regular `fabric_data_framework` package file in the active installation against the same file in the candidate wheel, then runs self-contained framework semantic probes.

If installed package bytes differ from the candidate wheel, certification stops before live Fabric mutation.

## 5. Real Fabric certification root

Use a dedicated DEV certification workspace and an attached certification Lakehouse.

Conventional layout:

```text
/lakehouse/default/Files/framework_cert/
  CANDIDATE.json
  exactly one fabric_data_framework-*.whl
  integration-inputs/        # framework-owned exact bundle when live checks are enabled
  certification-output/      # generated evidence
```

The workspace, capacity, Lakehouse and SQL endpoints are environment/infra prerequisites. Framework certification owns its certification Environment, Spark Job Definition, Copy Job and Data Pipeline; it does not create enterprise capacity, networking or production data stores.

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

## 8. Bootstrap framework-owned DEV Fabric assets

Do not hand-build the certification Pipeline, Copy Job or Spark Job Definition in the Fabric UI. The exact candidate wheel owns deterministic definitions for four named items:

```text
fabric-framework-certification-env       type=Environment
fabric-framework-certification-job       type=SparkJobDefinition
fabric-framework-certification-copy      type=CopyJob
fabric-framework-certification-pipeline  type=DataPipeline
```

The bootstrap sequence is intentionally ordered:

```text
exact candidate wheel
-> Environment definition contains exact wheel bytes
-> publish Environment using stable beta=false API
-> Spark Job Definition V2 binds Environment + certification Lakehouse
-> Copy Job binds cert_copy_source -> cert_copy_landing in the same Lakehouse
-> Data Pipeline invokes the same SJD and forwards the seven framework child parameters
-> getDefinition read-back verifies every framework-owned part
```

A provider-generated `.platform` part is ignored during semantic comparison. Missing, duplicated, unsupported or changed framework-owned parts fail closed.

Mutation is never implicit. Put the Fabric bearer token only in a runtime environment variable and explicitly authorize item mutation:

```bash
export FABRIC_ACCESS_TOKEN='<ephemeral-token>'

fabric-framework bootstrap-certification-assets \
  --workspace-id '<dedicated-dev-workspace-uuid>' \
  --lakehouse-id '<certification-lakehouse-uuid>' \
  --candidate-manifest 'dist/CANDIDATE.json' \
  --candidate-wheel 'dist/fabric_data_framework-0.4.0-py3-none-any.whl' \
  --control-plane-sql-server '<control-plane-sql-host>' \
  --control-plane-sql-database '<control-plane-database>' \
  --warehouse-sql-server '<warehouse-sql-host>' \
  --warehouse-sql-database '<warehouse-database>' \
  --certification-root '/lakehouse/default/Files/framework_cert' \
  --allow-item-mutation \
  --output fabric-certification-assets.json
```

Without `--allow-item-mutation`, the same command is read-back-only: every exact named item must already exist and its definition must match.

The output is credential-free and retains exact item IDs, actions, definition hashes and candidate wheel SHA256. It deliberately reports:

```text
definition_read_back_status=DEFINITION_READ_BACK_VERIFIED
pipeline_parameter_contract_status=PROVIDER_VALIDATION_REQUIRED
```

`DEFINITION_READ_BACK_VERIFIED` is not Fabric certification PASS. Microsoft Fabric supports runtime Pipeline parameters and Spark Job Definition activity command-line arguments, but the public DataPipeline item-definition schema does not currently list the top-level `parameters` member. A real DEV create/read-back/run must therefore prove this provider contract before the Pipeline path can contribute PASS evidence.

### Environment library boundary

Normal connected DEV workspaces may resolve the framework wheel dependencies during Environment publishing. A workspace with outbound access protection cannot reach public PyPI/Conda repositories.

For such a workspace, download an explicitly reviewed dependency wheel bundle in a compatible Linux/Fabric-runtime environment and pass every additional wheel explicitly:

```bash
fabric-framework bootstrap-certification-assets \
  ... \
  --dependency-wheel wheels/pydantic-....whl \
  --dependency-wheel wheels/sqlalchemy-....whl \
  --allow-item-mutation
```

The bootstrap never snapshots arbitrary package versions from the machine running the CLI. Exact dependency bytes must be supplied intentionally when the Fabric workspace cannot resolve them.

## 9. Use bootstrap identities to build integration inputs

Environment-dependent certification binds one approved workspace and four readable/executable Fabric identities:

```text
workspace_id
item_read_id          # the certification Lakehouse is a valid read-only Core item smoke target
pipeline_item_id      # fabric-framework-certification-pipeline
copy_job_id           # fabric-framework-certification-copy
spark_job_id          # fabric-framework-certification-job
```

Read the three created executable item IDs from `fabric-certification-assets.json`; use the known certification Lakehouse ID as `item_read_id`.

Then build the exact framework-owned integration input bundle with those physical IDs. The bundle is credential-free and binds:

```text
framework_artifact_sha256
  exact candidate wheel bytes

integration_inputs_hash
  exact framework-owned certification project + environment + physical non-secret bindings
```

The current builder entry point is `certification_harness/build_integration_inputs.py`, and the GitHub workflow is `.github/workflows/candidate-integration-inputs.yml`.

A customer/domain release identity does not participate in framework candidate certification.

### Optional read-only binding audit

`fabric-framework discover-certification-bindings` remains available when an operator wants an independent read-only name-to-ID audit. It follows Fabric Core List Items pagination, requires exact case-sensitive name/type matches and fails closed on zero or multiple matches. It does not create, update, delete or run items.

Discovery is an audit tool, not a prerequisite for first-time bootstrap.

## 10. Runtime-only values and secrets

The integration runner config declares allowed environment-variable names. Actual credential/connection values are supplied at runtime only.

Typical runtime names may include:

```text
FABRIC_ACCESS_TOKEN
CONTROL_PLANE_DATABASE_URL
WAREHOUSE_DATABASE_URL
WAREHOUSE_ADMIN_DATABASE_URL
```

The framework also supports the `fabric-user` SQL lane inside Fabric Spark runtime. In that lane only SQL server/database identities are retained; a fresh Microsoft Entra SQL token is acquired through Fabric runtime credentials when a connection opens.

Do not commit or retain:

```text
passwords
client secrets
bearer tokens
signed URLs
connection strings containing credentials
```

For Fabric-native SQL user authentication details, see [`reference/FABRIC_SQL_AUTH.md`](reference/FABRIC_SQL_AUTH.md).

## 11. Live mutation authorization

Asset bootstrap authorization and certification execution authorization are separate.

Asset creation/update/publish requires:

```text
--allow-item-mutation
```

Environment-dependent certification execution requires:

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

The framework-owned Pipeline child persists the durable framework outcome through the generic seven-parameter child contract. A semantic framework `FAILED` result may coexist with provider `Completed`; this is intentional for retry and reconciliation-fail-closed proof.

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
real Environment publish/dependency resolution
real Lakehouse Delta behavior
real Fabric identity/REST authorization
real DataPipeline parameter/provider contract
real Pipeline/Copy/Spark execution
real SQL Control Plane transaction/CAS behavior
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
