# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine core: **COMPLETE WITH EXTERNAL RUNNER/ESTATE VALIDATION BLOCKERS RECORDED**.

## Last completed step

Implemented the provider-neutral delivery spine required before a real Fabric estate is authorized:

- framework package version advanced to `0.3.0`;
- GitHub Actions PR/main CI with Python 3.11/3.13 test matrix, Ruff/static checks and wheel build;
- tag-triggered framework release workflow with version/tag guardrail, wheel SHA-256 and no-overwrite GitHub Release behaviour;
- deterministic semantic config-bundle hashing;
- immutable `ReleaseManifest` and release identity;
- environment-local `EnvironmentBindings` and credential-free deployment planning;
- control-plane migration CLI;
- idempotent semantic metadata materialization into relational control-plane definition tables;
- deployment-history persistence;
- `fabric-framework` CLI entry point for CI/CD runners;
- explicit protection of runtime state during promotion.

No enterprise Fabric workspace, tenant setting, capacity, connection, credential or runtime state was modified by this implementation.

## Implemented Phase 3 commands

```text
fabric-framework validate-tag
fabric-framework control-plane-migrate
fabric-framework metadata-materialize
fabric-framework release-manifest
fabric-framework deployment-plan
fabric-framework deployment-record
```

These commands are provider-neutral. GitHub Actions, Azure Pipelines, Fabric Deployment Pipeline automation, `fabric-cicd`, Fabric CLI or a future internal deployment service can call the same release/control-plane contracts.

## Promotion correctness now enforced

The immutable release identity contains:

```text
domain_release_version
domain_git_sha
framework_version
config_bundle_hash
config_schema_version
control_plane_schema_version
fabric_item_manifest_version
build_id
```

Environment bindings are outside that identity. DEV/UAT/PROD can therefore resolve different workspace/Lakehouse/Warehouse/connection resources while proving they received the same release hash.

Semantic materialization updates only release-definition tables. It does not copy or reset watermark, dataset state/lease, runtime overrides, run history, reconciliation/quarantine/schema observations, reprocess history or deployment history. `deployment_history` is appended independently in the target environment.

## Tests/checks executed locally

- `pytest -q`: **37 passed**.
- `python -m compileall`: PASS.
- wheel build: PASS (`fabric_data_framework-0.3.0-py3-none-any.whl`).
- wheel contents include new `delivery.py` and `cli.py`: PASS.
- Framework/Customer GitHub Actions workflow YAML files parse successfully.

New Phase 3 tests cover config-bundle hashing, same-release DEV/UAT/PROD planning, environment-local bindings, idempotent semantic materialization, preservation of existing watermark state, deployment-history recording, release tag/version guardrails and the CLI migrate -> materialize -> manifest -> plan flow.

## Remote GitHub Actions validation

A real pull-request workflow was triggered for Phase 3 (`framework-ci`, run `33127392418`). Two attempts were made.

Both attempts failed **before any workflow step executed**. All three jobs (`test-python-3.11`, `test-python-3.13`, `build-wheel`) reported:

```text
runner_id = 0
runner_name = ""
steps = []
```

and terminated within roughly two seconds. The failed-job rerun request itself was accepted by GitHub, so the workflow exists and Actions mutation permission is available, but no GitHub-hosted runner was assigned on either attempt.

Therefore this is recorded as an external GitHub Actions runner/account infrastructure blocker, not as a code/test failure. The repository API available to this project does not expose enough billing/hosted-runner account detail to state whether the root cause is quota, billing/payment, account policy or another hosted-runner restriction. That cause must not be guessed.

The workflow remains in the repository so it becomes the real PR gate once runner availability is restored.

## Immutable release state

The tag-triggered `v0.3.0` release workflow is defined, but no immutable `v0.3.0` framework release is claimed yet. Creating the tag before hosted-runner availability is restored would only trigger the same external execution blocker and would not prove the release workflow.

Customer must not claim successful exact-release integration against `0.3.0` until this immutable framework artifact exists.

## Current Microsoft Fabric external boundary

Current Microsoft documentation confirms Fabric CI/CD is built on Fabric REST APIs, supports Git integration with GitHub/Azure DevOps, supports deployment-pipeline automation, and supports noninteractive identities subject to tenant settings, permissions and per-API/item identity support.

The framework does not embed tenant credentials or claim a real Fabric deployment has succeeded. The external write edge remains an adapter/integration task requiring an approved company Fabric identity and target bindings.

## Known limitations / external blockers

- GitHub-hosted runner assignment is currently blocked before job execution on this private repository; two real attempts produced `runner_id=0` and no steps.
- Consequently no tag-triggered `v0.3.0` GitHub Release has yet been proven/published.
- No real Fabric item deployment has been executed from these workflows.
- No service principal/managed identity is configured in this repository.
- No physical enterprise control-plane database adapter has been exercised; SQLite/SQLAlchemy is the local contract proof.
- No Fabric Pipeline/Notebook item definition exists yet.
- No protected GitHub environments/approval rules are configured through code in this repository.
- Late/out-of-order correction, deletes and remaining capture/apply strategy catalog are pending.
- No Terraform.

## Exact next implementation step

The next coherent runtime slice is metadata-driven multi-dataset orchestration and failure isolation, while the delivery infrastructure blocker can be resolved independently:

1. generic dataset dispatcher/executor selection from metadata;
2. execution-group filtering and bounded concurrency contract;
3. dependency blocking without cancelling unrelated branches;
4. critical vs non-critical failure aggregation into `SUCCESS`, `PARTIAL_SUCCESS` or `FAILED`;
5. retry eligibility and dataset-level attempt lineage;
6. Customer fixtures with multiple datasets proving one failure does not stop unrelated datasets;
7. preserve the same audit/quarantine/reconciliation/state semantics per dataset.

When GitHub-hosted runners become available, rerun PR/main CI and then create/prove the immutable `v0.3.0` release before Customer exact-release integration is marked complete.

A real GitHub-driven Fabric deployment adapter can be wired as soon as an approved tenant identity/workspace binding is available. Do not fake either external validation path.
