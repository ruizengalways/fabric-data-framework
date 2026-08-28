# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine core: **COMPLETE; `v0.3.0` TAG/RELEASE PENDING ONLY**.
- Public-repository GitHub-hosted CI: **VALIDATED ON `ubuntu-latest`**.
- Phase 4 dispatcher: **CI-VALIDATED ON PR #9 AS 0.4.0 CANDIDATE; HELD OPEN UNTIL 0.3.0 RELEASE**.

## Last completed step

Portable release-checksum hardening was validated in Framework PR #10 and squash-merged to `main` as commit `4ddeb6b1945041806f4cd0ae0a046288b2e9ccd5`.

The merge-triggered Framework CI run `33143440320` completed successfully:

```text
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
runner            GitHub-hosted ubuntu-latest
```

Framework CI and release workflows generate `SHA256SUMS` from inside `dist/`:

```text
<sha256>  fabric_data_framework-0.3.0-py3-none-any.whl
```

rather than embedding the producer-local path `dist/<wheel>`. The checksum can therefore be verified directly after consumers download release assets into another directory.

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

The tag-triggered release workflow validates package/tag identity, runs isolated static checks and tests, builds the immutable wheel, generates portable `SHA256SUMS`, refuses release overwrite and creates the GitHub Release from the pushed tag.

## Phase 4 state

Framework PR #9 implements metadata-driven multi-dataset dispatcher/failure isolation as version `0.4.0`.

Its GitHub-hosted validation runs passed wheel build, Python 3.11, Python 3.13, static checks and **44 tests**. PR #9 remains intentionally open and must not merge until the immutable `v0.3.0` boundary has been frozen from `main`.

## Immutable release state

The 0.3.0 source/release workflow is ready, but immutable tag/release `v0.3.0` still does not exist.

This is now the only Phase 3 delivery gate that cannot be completed through the available GitHub connector because it does not expose tag creation. The tag must be created from the current validated `main`; the workflow must then create the Release. Do not manually pre-create the GitHub Release.

Customer Phase 3 PR #6 now performs true released-artifact integration: it downloads `fabric_data_framework-0.3.0-py3-none-any.whl` plus `SHA256SUMS`, verifies SHA-256, installs the released wheel, then runs cross-package tests and release/deployment-plan checks. Customer run `33143386148` currently fails truthfully with HTTP 404 at the release download because `v0.3.0` has not been published.

## Current Microsoft Fabric external boundary

No enterprise Fabric workspace, tenant setting, capacity, connection, credential or runtime state has been modified. Real Fabric deployment remains a later adapter/integration step using approved tenant identity and environment bindings.

## Known limitations / blockers

- Immutable framework `v0.3.0` tag/GitHub Release is pending.
- Customer exact released-wheel integration is blocked only on that release.
- Phase 4 PR #9 is held open behind the 0.3.0 release boundary.
- No real Fabric item deployment has executed.
- No physical enterprise control-plane store has been exercised.
- Late/out-of-order correction, delete handling, FULL/SNAPSHOT, CDC and recovery orchestration remain future runtime slices.
- No Terraform implementation yet; `fabric-infra` remains intentionally deferred.

## Exact next implementation sequence

1. Create/push immutable framework tag `v0.3.0` from the current validated `main`; let GitHub Actions create the wheel + `SHA256SUMS` Release. Do not manually pre-create the Release.
2. Re-run Customer PR #6 exact integration and require released-wheel checksum verification, cross-package tests and DEV/UAT/PROD release-plan checks to pass; then merge Customer Phase 3.
3. Rebase/revalidate and merge Framework PR #9 as the `0.4.0` dispatcher slice.
4. Add the tiny Customer multi-dataset dispatcher scenario.
5. Continue with retry/backfill/replay, SNAPSHOT_DIFF, CDC/UPSERT, delete/schema/late-arrival handling and then the first real Fabric adapter.

Do not fake release or Fabric-estate validation.
