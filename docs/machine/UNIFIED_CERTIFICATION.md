# MACHINE — Unified Real-Fabric Certification

Purpose: recover the exact architecture and fail-closed boundaries of the one-call Fabric certification surface after a context reset.

## Canonical owners

```text
src/fabric_data_framework/certification/
  models.py       credential-free unified status/report contracts
  bounded.py      exact-wheel + Lakehouse + provider-neutral semantic bounded probes
  unified.py      composition of existing approved environment/business-path runners
  simple.py       public Fabric Notebook API, runtime bridge and first-time Control Plane bootstrap
  resources/      wheel-packaged copies of exact release integration/readiness policy

src/fabric_data_framework/execution/pipeline_child.py
  reusable remote Fabric Pipeline child contract + durable DatasetRunAudit handoff

src/fabric_data_framework/cli/certification.py
  removable CLI presentation over the simple API

docs/human/FRAMEWORK_DEVELOPER_CERTIFICATION.md
  start-to-finish human runbook for engineers developing/certifying Framework changes
docs/human/ONE_CALL_CERTIFICATION_RUNTIME.md
  runtime mapping, scoped extension bridge, first-time Control Plane bootstrap and Pipeline child contract
```

The certification package is an **orchestrator**, not a second semantics implementation. Environment stages delegate to the existing approved owners under `evidence/`.

## Minimal public API

```python
from fabric_data_framework.certification import certify

report = certify(spark=spark)
```

Conventional root:

```text
/lakehouse/default/Files/framework_cert/
  CANDIDATE.json
  exactly one fabric_data_framework-*.whl
  customer-inputs/                         # optional exact Customer input artifact
```

Default discovery is intentionally limited to this directory contract. It **never scans Fabric to guess a SQL Database, Warehouse or Pipeline**.

If `customer-inputs/` is absent, only bounded checks execute and environment-specific stages remain `NOT_RUN`/`BLOCKED`.

## Exact Customer bundle contract

Full environment orchestration consumes the existing exact Customer candidate-input artifact:

```text
customer-inputs/
  INPUTS.json
  runner-config.json
  release-manifest.json
  project/
  dist/
```

Before live stages, exact Customer inputs must bind the same:

```text
candidate_git_sha
candidate_wheel_sha256
framework_version
```

The runner config remains credential-free and owns:

```text
environment/profile
physical workspace/item IDs
dataset selections
execution recipes
runtime environment-variable names
```

Secret values remain runtime-only.

## Runtime resolution invariant

Full ordinary live certification may explicitly supply runtime-only values:

```python
report = certify(
    spark=spark,
    runtime_environment={
        "CONTROL_PLANE_DATABASE_URL": control_plane_database_url,
        "WAREHOUSE_DATABASE_URL": warehouse_database_url,
    },
    allow_live_mutations=True,
)
```

If `runtime_environment` is omitted, the public API starts from the current process environment.

SQL resource selection is exactly:

```text
runner-config.json.<runtime env-var field>
  -> exact environment-variable name
runtime_environment/current process environment
  -> actual runtime value
```

No resource auto-selection or fallback exists.

### Scoped process bridge

Approved Framework runners consume the explicit mapping, while exact Customer/domain Python entry points may consume process environment. `simple.certify` therefore resolves one mapping and temporarily mirrors **only runner-declared runtime names** into `os.environ` during the call.

```text
resolved runtime mapping
  -> declared names temporarily visible in os.environ
  -> approved runners + exact Customer extensions execute against the same values
  -> prior os.environ values restored before certify() returns
```

The bridge must never copy runtime values into retained certification models, input bundles or evidence references.

### Notebook Fabric token

If the runner-declared Fabric access-token variable is absent in a Fabric Notebook, the public API may obtain the current NotebookUtils `pbi` token and use it only in the resolved runtime for that call.

The token value must never be retained in:

```text
UnifiedCertificationReport
IntegrationEvidenceManifest
release proof bundles
evidence references
intentionally authored certification logs
```

## First-time dedicated Control Plane bootstrap

A newly provisioned certification SQL Database needs both:

```text
current Framework Control Plane schema
exact Customer semantic dataset definitions
```

A schema-only migration is insufficient because `SqlAlchemyControlPlaneRepository` deliberately requires the exact released dataset definition/config hash before Pipeline/Warehouse execution.

Explicit first-time call:

```python
report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
    allow_control_plane_migration=True,
)
```

The public API orders bootstrap fail-closed:

```text
bounded exact-wheel suite
  -> every bounded check PASS
  -> Customer INPUTS identity matches the same Framework bytes
  -> resolve the declared Control Plane URL
  -> apply baseline schema
  -> materialize exact Customer semantic metadata idempotently
  -> verify materialized config bundle hash
  -> continue normal unified environment stages
```

If bounded checks fail, SQL bootstrap is not attempted.

If the runtime Control Plane URL is absent, no other database is selected.

If the Customer bundle identity differs from the bounded exact wheel, bootstrap raises before semantic deployment.

Normal reruns keep:

```text
allow_control_plane_migration=False
```

The explicit migration flag is for a newly provisioned dedicated certification Control Plane. It must not be used to silently mutate a shared/production Control Plane merely to make certification pass.

## Bounded suite

`bounded.py` owns:

```text
identity.exact
lakehouse.smoke
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

Identity failure stops semantic/environment progression. The reconciliation probe intentionally creates an underlying reconciliation FAIL and passes only when state advance is blocked.

The Lakehouse probe performs a real Delta write/read. Semantic probes reuse Framework implementation primitives; they are not handwritten expected-PASS JSON.

## Exact extension boundary

When an exact Customer bundle is supplied, local extension wheels under `customer-inputs/dist/` are installed only after SHA256 verification against `ReleaseManifest.artifact_sha256`.

Installation uses `--no-deps` so certification does not silently re-resolve the Framework/runtime dependency graph.

Customer/domain extensions can provide bounded physical facts or mutations, but they cannot author Integration/Release PASS values.

## Ordered environment stages

The unified orchestrator follows:

```text
bounded exact-wheel suite
  -> Fabric item read
  -> Control Plane reference conformance / external evidence / approved certification
  -> base prerequisite merge
  -> Pipeline
  -> Copy
  -> Spark
  -> Warehouse normal commit
  -> Warehouse fault prerequisite merge
  -> Warehouse ambiguous COMMIT
  -> integration evidence merge
  -> five live business paths
  -> merged business-path release proof bundle
```

Existing approved owners:

```text
approved_control_plane_runner.py
approved_pipeline_runner.py
approved_capture_runner.py
approved_warehouse_runner.py
approved_warehouse_fault_runner.py
approved_business_path_runner.py
```

## Pipeline durable-outcome invariant

A Fabric Pipeline provider status `Completed` is not Framework semantic success.

The parent `FabricPipelineBackend` generates exactly seven stable correlation parameters:

```text
framework_pipeline_run_id
framework_dataset_run_id
dataset_id
run_mode
attempt
effective_config_hash
execution_plan_hash
```

The remote child executes through `execution/pipeline_child.py`:

```text
parse exact parameter bag
  -> read exact deployed DatasetConfig
  -> recompute/verify effective_config_hash
  -> recompute/verify execution_plan_hash
  -> customer/domain bounded physical executor returns semantic facts
  -> Framework persists exact DatasetRunAudit
  -> Framework reads exact DatasetDispatchOutcome
```

The parent PASS boundary is therefore:

```text
provider Completed
AND exact durable outcome exists for generated dataset_run_id
AND Framework semantic status satisfies the selected gate
```

A random Pipeline that merely reaches `Completed` cannot satisfy the Framework gate.

## Control Plane surfaces

The unified report may contain:

```text
control.reference_conformance
control.external_evidence
control.cert
```

`control.reference_conformance` proves actual selected SQL backend schema/rollback/CAS behavior once temporary writes are explicitly authorized.

`control.external_evidence` reflects whether exact Customer inputs carry the required complete/review-bound references.

`control.cert` remains the approved production-control-plane evidence runner and must not PASS without complete safe external evidence plus deterministic conformance.

## External evidence and Warehouse fault controller remain real blockers

Preserve these exact blocker semantics:

```text
control_plane_external_evidence_incomplete
control_plane_external_evidence_not_review_bound
warehouse_real_fault_controller_not_configured
```

Automation does not reinterpret them as PASS.

Admin-level Warehouse exact-session termination remains separate:

```python
allow_warehouse_session_termination=True
```

It is never inferred from `allow_live_mutations=True`.

## Unified status vocabulary

```text
PASS      actual check executed and passed
FAIL      actual check executed and failed
NOT_RUN   execution intentionally did not occur
BLOCKED   required external/config prerequisite is not ready
```

Rules:

- real FAIL dominates overall status;
- blocked/unrun later stages do not rewrite earlier PASS;
- missing privilege is not a synthetic Framework PASS;
- missing evidence is not evidence;
- no latest/PASS-wins merge policy exists.

## Release boundary

`UnifiedCertificationReport.release_authorized` is structurally fixed to `false`.

The unified runner:

```text
DOES NOT freeze/select a candidate
DOES NOT change release_allowed
DOES NOT create a release tag
DOES NOT publish v0.4.0
DOES NOT change fabric-customer production dependency
DOES NOT make Admin Override equivalent to evidence-based release readiness
```

Full release still uses the exact retained evidence/readiness/candidate-certification chain.

## Packaged policy mirror

Wheel-only Fabric environments do not have repository `release/`, so exact policy copies live under:

```text
src/fabric_data_framework/certification/resources/
```

Tests lock their semantics to canonical release JSON.

## Evidence identity rule after any Framework source change

All real-Fabric evidence is byte-specific. If Framework source changes, previously tested wheels remain historical evidence only.

A new successful `main` artifact is required before the changed certification surface itself can be certified. Never reuse PASS values from different wheel bytes.

## Recovery checklist for a new conversation

1. Read `docs/machine/STATE.md` for current merged code SHA/CI/release truth.
2. Read this file for unified architecture.
3. Read `docs/human/FRAMEWORK_DEVELOPER_CERTIFICATION.md` and `docs/human/ONE_CALL_CERTIFICATION_RUNTIME.md`.
4. Read Customer `docs/CURRENT_STATUS.md` and its company-Fabric runbook.
5. Confirm Customer production pin remains the immutable released Framework version.
6. Confirm control-plane external evidence and Warehouse fault-controller blockers from current Customer `main`.
7. After any Framework source change, use a new exact successful Framework `main` artifact.
8. Put one Framework wheel + `CANDIDATE.json` + `SHA256SUMS` in the conventional Lakehouse root.
9. Put the exact matching Customer input artifact under `customer-inputs/` for full certification.
10. Start bounded first. Use explicit runtime-only DB bindings for full certification.
11. For a newly created dedicated certification SQL Database, explicitly use `allow_control_plane_migration=True` only with approved live mutations.
12. Keep Warehouse session termination separately authorized.
13. Never infer candidate freeze/release from a unified certification report.
