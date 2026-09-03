# MACHINE — Unified Real-Fabric Certification

Purpose: recover the exact architecture and fail-closed boundaries of the one-call Fabric certification surface after a context reset.

## Canonical owners

```text
src/fabric_data_framework/certification/
  models.py       credential-free unified status/report contracts
  bounded.py      exact-wheel + Lakehouse + provider-neutral semantic bounded probes
  unified.py      composition of existing approved environment/business-path runners
  simple.py       minimal Fabric Notebook operator API / conventional directory discovery
  resources/      wheel-packaged copies of exact release integration/readiness policy

src/fabric_data_framework/cli/certification.py
  removable CLI presentation over the simple API
```

The certification package is an **orchestrator**, not a second semantics implementation. Environment stages must delegate to the existing approved owners under `evidence/`.

## Why this exists

PR/main CI proves deterministic Python contracts, algorithms, package boundaries and recovery behavior. It cannot prove that one exact built wheel works against one real Fabric tenant/resource set.

The unified runner therefore re-executes only the relevant real-environment boundaries and produces one report, instead of requiring an operator to copy many notebook cells and manually mark a form.

## Minimal public API

The public default is:

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

Full ordinary live certification, only after mutation approval:

```python
report = certify(
    spark=spark,
    allow_live_mutations=True,
)
```

Admin-level Warehouse exact-session termination remains separate:

```python
allow_warehouse_session_termination=True
```

It must never be inferred from ordinary mutation approval.

## Bounded suite

`bounded.py` owns the automated equivalent of the original first-company Notebook cells:

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

The Lakehouse probe performs a real Delta write/read. The semantic probes reuse Framework implementation primitives; they are not handwritten expected-PASS JSON.

## Exact Customer bundle contract

Full environment orchestration consumes the existing exact Customer candidate-input artifact without asking the Notebook operator to retype its physical bindings:

```text
customer-inputs/
  INPUTS.json
  runner-config.json
  release-manifest.json
  project/
  dist/
```

Before any approved live stage, the runner requires the Customer bundle to bind the same:

```text
candidate_git_sha
candidate_wheel_sha256
framework_version
```

The runner config remains credential-free. Secret values are resolved only from the runtime environment.

## Runtime token boundary

Fabric REST authentication first uses the configured access-token environment variable. In a Fabric Notebook, when that value is absent, the runner may attempt the current NotebookUtils `pbi` token for Fabric/Power BI REST access.

The token value must never be retained in:

```text
UnifiedCertificationReport
IntegrationEvidenceManifest
release proof bundles
evidence references
logs intentionally authored by certification code
```

SQL database URLs remain runtime values named by the exact Customer runner config.

## Exact extension boundary

When an exact Customer bundle is supplied, the runner may install local extension wheels from `customer-inputs/dist/` only after SHA256 verification against `ReleaseManifest.artifact_sha256`.

Installation uses `--no-deps` so the certification helper does not silently re-resolve the Framework/runtime dependency graph.

## Ordered environment stages

The unified orchestrator follows the existing approved dependency order:

```text
bounded exact-wheel suite
  -> Fabric item read
  -> Control Plane
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

Each provider step delegates to the established runner:

```text
approved_control_plane_runner.py
approved_pipeline_runner.py
approved_capture_runner.py
approved_warehouse_runner.py
approved_warehouse_fault_runner.py
approved_business_path_runner.py
```

## Control Plane has two distinct surfaces

The unified report may contain:

```text
control.reference_conformance
control.external_evidence
control.cert
```

`control.reference_conformance` can prove the actual selected SQL backend's Framework schema/rollback/CAS behavior once temporary writes are explicitly authorized. It does **not** promote missing enterprise evidence.

`control.external_evidence` reflects whether the exact Customer inputs carry the seven complete/review-bound references.

`control.cert` is the existing approved production-control-plane evidence runner and must not PASS without complete safe external evidence plus deterministic conformance.

Optional explicit `allow_control_plane_migration=True` exists for a newly provisioned certification Control Plane. Normal production certification must not silently migrate the database.

## External evidence and Warehouse fault controller remain real blockers

The unified runner reads `INPUTS.json.live_prerequisite_blockers`.

At minimum, preserve these blocker semantics exactly:

```text
control_plane_external_evidence_incomplete
control_plane_external_evidence_not_review_bound
warehouse_real_fault_controller_not_configured
```

The runner may surface a clearer unified status, but it cannot reinterpret any of these as PASS.

## Four check states

Unified status vocabulary:

```text
PASS      actual check executed and passed
FAIL      actual check executed and failed
NOT_RUN   execution intentionally did not occur
BLOCKED   required external/config prerequisite is not ready
```

Rules:

- a real FAIL always dominates overall status;
- blocked/unrun later stages do not retroactively change earlier PASS;
- lack of privilege is not a Framework FAIL unless the check was expected/authorized to run and actually failed;
- missing evidence is not evidence;
- no latest/PASS-wins merge policy is introduced.

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

Full release still uses the existing exact retained evidence/readiness/candidate-certification chain.

## Packaged policy mirror

A wheel-only Fabric environment does not have the repository `release/` directory, so exact copies of:

```text
release/0.4.0/integration-evidence-template.json
release/0.4.0/readiness-spec.json
```

are packaged under:

```text
src/fabric_data_framework/certification/resources/
```

Tests must lock packaged JSON semantics to the canonical release JSON. If release policy changes, both must change in the same PR or CI must fail.

## Evidence identity rule after any Framework change

All real-Fabric evidence is byte-specific. Once this certification feature changes Framework source, the previously tested PR #99 wheel remains historical evidence only.

A new successful `main` framework-ci artifact is required before the unified runner itself can be certified in company Fabric. Never reuse the old PR #99 PASS values for the new wheel.

## Recovery checklist for a new conversation

1. Read `docs/machine/STATE.md` first for the latest merged SHA/CI/release truth.
2. Read this file for unified-runner architecture.
3. Read Customer `docs/CURRENT_STATUS.md` and its certification runbook before creating exact Customer inputs.
4. Verify current Customer production pin is still the released Framework version; do not infer migration from candidate testing.
5. Verify control-plane external evidence and Warehouse fault-controller blockers from current Customer `main`.
6. Build/download a **new exact main artifact** after any Framework source change.
7. Put one framework wheel + `CANDIDATE.json` in the conventional Lakehouse root.
8. Put the matching exact Customer input artifact under `customer-inputs/` when full environment testing is intended.
9. Start with `certify(spark=spark)`; enable live mutations only when the DEV/UAT certification resources are approved.
10. Keep Warehouse session termination separately authorized.
