# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine core: **COMPLETE**.
- Self-hosted CI execution: **VALIDATED ON RUNNER `Bear`**.

## Last completed step

Implemented and validated the provider-neutral enterprise delivery spine and moved GitHub Actions execution from unavailable GitHub-hosted runners to the repository self-hosted runner `Bear`.

Phase 3 includes:

- framework package version `0.3.0`;
- GitHub Actions PR/main CI with Python 3.11/3.13 test matrix, static checks and wheel build;
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

## Local validation

- `pytest -q`: **37 passed**.
- `python -m compileall`: PASS.
- wheel build: PASS (`fabric_data_framework-0.3.0-py3-none-any.whl`).
- wheel contents include `delivery.py` and `cli.py`: PASS.
- Framework/Customer GitHub Actions workflow YAML parse: PASS.

## Remote GitHub Actions validation

The original GitHub-hosted `ubuntu-latest` jobs failed before runner assignment (`runner_id=0`, no steps), so workflow execution was moved to the self-hosted runner supplied for this project.

Framework PR #7 validated the real runner identity from GitHub job metadata:

```text
runner_id = 2
runner_name = "Bear"
runner_group_name = "Default"
labels = ["self-hosted"]
```

Because `Bear` is currently the runner display name rather than a custom label, workflows correctly use:

```yaml
runs-on: self-hosted
```

and do not use `[self-hosted, Bear]`. If a custom `Bear` label is added later, scheduling can be tightened without changing application/runtime architecture.

The first Bear execution exposed non-hermetic Ruff rule discovery from the self-hosted environment. CI was corrected to invoke Ruff with `--isolated` and an explicit core correctness policy (`E4,E7,E9,F`) so repository CI does not depend on runner-global Ruff configuration.

Framework CI run `33137284837` then completed successfully on Bear:

- `build-wheel`: **SUCCESS**;
- `test-python-3.13`: **SUCCESS**;
- `test-python-3.11`: **SUCCESS**.

This proves checkout, Python provisioning, package installation, isolated static checks, the framework test suite, wheel build and artifact upload on the self-hosted runner.

## Immutable release state

The tag-triggered `v0.3.0` release workflow is defined and now targets `self-hosted` execution. The immutable `v0.3.0` release has not yet been claimed in this status document; the immediate delivery step after the runner workflow change is merged is to create/prove the `v0.3.0` tag release on Bear.

Customer must not claim successful exact-release integration against `0.3.0` until the immutable framework artifact exists.

## Current Microsoft Fabric external boundary

The framework does not embed tenant credentials or claim a real Fabric deployment has succeeded. The external write edge remains an adapter/integration task requiring an approved company Fabric identity and target bindings.

## Known limitations / external blockers

- Immutable `v0.3.0` framework GitHub Release still needs to be created and proven on Bear.
- Customer exact-release integration remains gated on that artifact.
- Bear currently exposes only the `self-hosted` label; the display name itself is not a scheduler label.
- A single Bear runner provides one execution slot, so matrix/build jobs execute serially unless additional runners are added.
- No real Fabric item deployment has yet been executed from these workflows.
- No service principal/managed identity is configured in this repository.
- No physical enterprise control-plane database adapter has been exercised; SQLite/SQLAlchemy is the local contract proof.
- No Fabric Pipeline/Notebook item definition exists yet.
- Late/out-of-order correction, deletes and remaining capture/apply strategy catalog are pending.
- No Terraform.

## Exact next implementation step

1. Merge the self-hosted runner workflow change after the successful Bear CI run.
2. Create and prove immutable framework release `v0.3.0` on Bear.
3. Run Customer PR #6 source-contract and exact-release integration on an authorized self-hosted runner, then merge the exact `fabric-data-framework==0.3.0` dependency upgrade.
4. Continue with the metadata-driven multi-dataset dispatcher/failure-isolation slice.
5. Wire a real GitHub-driven Fabric deployment adapter when an approved tenant identity/workspace binding is available.

Do not fake release or Fabric-estate validation.
