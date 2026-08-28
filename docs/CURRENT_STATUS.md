# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine core: **COMPLETE; `v0.3.0` RELEASE PENDING ONLY**.
- Public-repository GitHub-hosted CI: **VALIDATED ON `ubuntu-latest`**.
- UI-driven framework release initiation: **AVAILABLE ON `main`; FIRST MANUAL RUN EXPOSED A RELEASE BUILD-BACKEND GAP, FIX IN PROGRESS**.
- Phase 4 dispatcher: **CI-VALIDATED ON PR #9 AS 0.4.0 CANDIDATE; HELD OPEN UNTIL 0.3.0 RELEASE**.

## Last completed step

The first UI-triggered `framework-release` run was executed from `main` with version `0.3.0` as run `33147093082`.

The run proved the operator/UI path and release-candidate validation correctly:

```text
Checkout release source                 SUCCESS
Resolve immutable release tag           SUCCESS -> v0.3.0
Prepare manual release source            SUCCESS -> tag did not yet exist
Install and validate release candidate  SUCCESS
  package/tag validation                 SUCCESS
  Ruff                                   SUCCESS
  compile                                SUCCESS
  pip check                              SUCCESS
  pytest                                 37 passed
Build immutable wheel and checksum       FAILURE
```

The failure was not a framework runtime/test failure. The release build uses `pip wheel --no-build-isolation`, while the release job had not explicitly installed the build backend required by `pyproject.toml`:

```text
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"
```

The observed error was:

```text
BackendUnavailable: Cannot import 'setuptools.build_meta'
```

The normal Framework CI wheel job already installs `setuptools>=77` before its no-build-isolation build, so the release job is being aligned with the already-proven CI packaging contract.

Importantly, the failed run stopped before tag creation and before GitHub Release creation. `v0.3.0` therefore remains safe to create from a corrected run; no immutable release artifact needs to be deleted or moved.

Fix branch `fix/release-build-backend` adds the missing explicit `python -m pip install "setuptools>=77"` before the immutable wheel build.

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

Portable checksum hardening was validated in Framework PR #10 and squash-merged to `main`. UI-driven immutable release initiation was validated and merged in PR #11. The first real manual release run then exposed the build-backend installation mismatch described above.

## Phase 4 state

Framework PR #9 implements metadata-driven multi-dataset dispatcher/failure isolation as version `0.4.0`.

Its GitHub-hosted validation runs passed wheel build, Python 3.11, Python 3.13, static checks and **44 tests**. PR #9 remains intentionally open and must not merge until the immutable `v0.3.0` boundary has been frozen from `main`.

## Immutable release state

Immutable GitHub Release `v0.3.0` still does not exist.

The first UI-triggered release run validated 0.3.0 successfully but failed before tag/release creation because the no-build-isolation wheel step lacked an explicit `setuptools>=77` installation. After the fix is CI-validated and merged, rerun `framework-release` from the GitHub Actions page on `main` with version `0.3.0`.

Customer Phase 3 PR #6 performs true released-artifact integration: it downloads `fabric_data_framework-0.3.0-py3-none-any.whl` plus `SHA256SUMS`, verifies SHA-256, installs the released wheel, then runs cross-package tests and release/deployment-plan checks. It remains correctly blocked until the Framework Release exists.

## Current Microsoft Fabric external boundary

No enterprise Fabric workspace, tenant setting, capacity, connection, credential or runtime state has been modified. Real Fabric deployment remains a later adapter/integration step using approved tenant identity and environment bindings.

## Known limitations / blockers

- Release build-backend fix must be CI-validated and merged to `main`.
- Immutable framework `v0.3.0` GitHub Release is still pending.
- Customer exact released-wheel integration is blocked only on that release.
- Phase 4 PR #9 is held open behind the 0.3.0 release boundary.
- No real Fabric item deployment has executed.
- No physical enterprise control-plane store has been exercised.
- Late/out-of-order correction, delete handling, FULL/SNAPSHOT, CDC and recovery orchestration remain future runtime slices.
- No Terraform implementation yet; `fabric-infra` remains intentionally deferred.

## Exact next implementation sequence

1. Validate and merge `fix/release-build-backend`.
2. From GitHub Actions, rerun `framework-release` on `main` with version `0.3.0`; verify tag, Release, wheel and `SHA256SUMS` assets.
3. Re-run Customer PR #6 exact integration and require released-wheel checksum verification, cross-package tests and DEV/UAT/PROD release-plan checks to pass; then merge Customer Phase 3.
4. Rebase/revalidate and merge Framework PR #9 as the `0.4.0` dispatcher slice.
5. Add the tiny Customer multi-dataset dispatcher scenario.
6. Continue with retry/backfill/replay, SNAPSHOT_DIFF, CDC/UPSERT, delete/schema/late-arrival handling and then the first real Fabric adapter.

Do not fake release or Fabric-estate validation.
