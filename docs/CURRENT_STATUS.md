# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine core: **COMPLETE; `v0.3.0` RELEASE PENDING ONLY**.
- Public-repository GitHub-hosted CI: **VALIDATED ON `ubuntu-latest`**.
- UI-driven framework release initiation: **AVAILABLE ON `main`**.
- Release build-backend fix: **MERGED AND CI-VALIDATED**.
- Phase 4 dispatcher: **CI-VALIDATED ON PR #9 AS 0.4.0 CANDIDATE; HELD OPEN UNTIL 0.3.0 RELEASE**.

## Last completed step

The first UI-triggered `framework-release` run (`33147093082`) was executed from `main` with version `0.3.0`.

It successfully completed release-candidate validation:

```text
Checkout release source                 SUCCESS
Resolve immutable release tag           SUCCESS -> v0.3.0
Prepare manual release source            SUCCESS -> tag did not exist
Install and validate release candidate  SUCCESS
  package/tag validation                 SUCCESS
  Ruff                                   SUCCESS
  compile                                SUCCESS
  pip check                              SUCCESS
  pytest                                 37 passed
Build immutable wheel and checksum       FAILURE
```

The failure was isolated to the packaging environment, not framework correctness:

```text
BackendUnavailable: Cannot import 'setuptools.build_meta'
```

`pyproject.toml` declares `setuptools>=77` as the build backend, while the release job used `pip wheel --no-build-isolation` without first installing that backend into the runner environment.

Framework PR #12 aligned the release job with the already-proven CI packaging contract by explicitly installing `setuptools>=77` before the no-build-isolation wheel build. PR #12 was squash-merged to `main` as commit `8474471e6079c54d2d1cecd3605faed0b6782345`.

PR CI run `33147330354` passed, and merge-triggered `main` run `33147361942` also passed:

```text
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
runner            GitHub-hosted ubuntu-latest
```

The failed release run stopped before tag creation and before GitHub Release creation. No immutable artifact needs cleanup or movement; `v0.3.0` remains safe to create from the corrected workflow.

## Existing delivery spine

Framework source version `0.3.0` remains on `main` and provides:

```text
fabric-framework validate-tag
fabric-framework control-plane-migrate
fabric-framework metadata-materialize
fabric-framework release-manifest
fabric-framework deployment-plan
fabric-framework deployment-record
```

Release workflow capabilities now include:

- GitHub Actions UI initiation via `workflow_dispatch`;
- manual release restricted to `main`;
- package/tag identity validation;
- Ruff, compile, dependency and pytest gates;
- explicit build-backend installation;
- immutable wheel build;
- portable `SHA256SUMS` generation and verification;
- annotated tag creation only after validation/build succeeds;
- immutable GitHub Release creation;
- recovery when a tag exists without a Release;
- refusal to overwrite an existing Release or move an existing tag.

## Phase 4 state

Framework PR #9 implements metadata-driven multi-dataset dispatcher/failure isolation as version `0.4.0`.

Its GitHub-hosted validation runs passed wheel build, Python 3.11, Python 3.13, static checks and **44 tests**. PR #9 remains intentionally open and must not merge until the immutable `v0.3.0` boundary has been frozen.

## Immutable release state

Immutable GitHub Release `v0.3.0` still does not exist.

The corrected workflow is now on `main`. The next operator action is:

```text
GitHub -> fabric-data-framework -> Actions -> framework-release -> Run workflow
Use workflow from: main
version: 0.3.0
```

Customer Phase 3 PR #6 performs true released-artifact integration: it downloads `fabric_data_framework-0.3.0-py3-none-any.whl` plus `SHA256SUMS`, verifies SHA-256, installs the released wheel, then runs cross-package tests and release/deployment-plan checks. It remains correctly blocked until the Framework Release exists.

## Current Microsoft Fabric external boundary

No enterprise Fabric workspace, tenant setting, capacity, connection, credential or runtime state has been modified. Real Fabric deployment remains a later adapter/integration step using approved tenant identity and environment bindings.

## Known limitations / blockers

- Immutable framework `v0.3.0` GitHub Release is still pending the corrected UI-triggered run.
- Customer exact released-wheel integration is blocked only on that release.
- Phase 4 PR #9 is held open behind the 0.3.0 release boundary.
- No real Fabric item deployment has executed.
- No physical enterprise control-plane store has been exercised.
- Late/out-of-order correction, delete handling, FULL/SNAPSHOT, CDC and recovery orchestration remain future runtime slices.
- No Terraform implementation yet; `fabric-infra` remains intentionally deferred.

## Exact next implementation sequence

1. Rerun `framework-release` from GitHub Actions on `main` with version `0.3.0`; verify tag, Release, wheel and `SHA256SUMS` assets.
2. Re-run Customer PR #6 exact integration and require released-wheel checksum verification, cross-package tests and DEV/UAT/PROD release-plan checks to pass; then merge Customer Phase 3.
3. Rebase/revalidate and merge Framework PR #9 as the `0.4.0` dispatcher slice.
4. Add the tiny Customer multi-dataset dispatcher scenario.
5. Continue with retry/backfill/replay, SNAPSHOT_DIFF, CDC/UPSERT, delete/schema/late-arrival handling and then the first real Fabric adapter.

Do not fake release or Fabric-estate validation.
