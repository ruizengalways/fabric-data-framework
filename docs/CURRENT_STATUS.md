# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine core: **COMPLETE; `v0.3.0` RELEASE PENDING ONLY**.
- Public-repository GitHub-hosted CI: **VALIDATED ON `ubuntu-latest`**.
- UI-driven framework release initiation: **IMPLEMENTED AND CI-VALIDATED ON PR #11; MERGE PENDING**.
- Phase 4 dispatcher: **CI-VALIDATED ON PR #9 AS 0.4.0 CANDIDATE; HELD OPEN UNTIL 0.3.0 RELEASE**.

## Last completed step

Framework PR #11 (`ci/ui-driven-framework-release`) adds a GitHub-page release path in addition to the existing tag-push trigger.

PR validation run `33146153188` completed successfully:

```text
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
runner            GitHub-hosted ubuntu-latest
```

Preferred operator flow after PR #11 is merged:

```text
GitHub -> fabric-data-framework -> Actions -> framework-release -> Run workflow
select branch: main
version: 0.3.0
```

The workflow resolves `v0.3.0`, validates package/tag identity, runs isolated Ruff checks, compile, dependency checks and tests, builds the wheel, generates and verifies portable `SHA256SUMS`, creates the annotated tag only after validation when needed, and creates the GitHub Release from that immutable tag.

The manual path is restricted to `main`. It refuses to overwrite an existing Release and never moves an existing tag. If a previous release attempt created the tag but failed before creating the Release, a rerun detects that condition, checks out the existing immutable tag, revalidates/rebuilds it and can complete the missing Release safely.

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

Portable checksum hardening was validated in Framework PR #10 and squash-merged to `main`. Current main CI is green on GitHub-hosted Python 3.11/3.13 plus wheel build.

## Phase 4 state

Framework PR #9 implements metadata-driven multi-dataset dispatcher/failure isolation as version `0.4.0`.

Its GitHub-hosted validation runs passed wheel build, Python 3.11, Python 3.13, static checks and **44 tests**. PR #9 remains intentionally open and must not merge until the immutable `v0.3.0` boundary has been frozen from `main`.

## Immutable release state

Immutable GitHub Release `v0.3.0` still does not exist. After PR #11 merges, no local terminal command is required: the release can be initiated from the GitHub Actions page against `main` with version `0.3.0`.

Customer Phase 3 PR #6 performs true released-artifact integration: it downloads `fabric_data_framework-0.3.0-py3-none-any.whl` plus `SHA256SUMS`, verifies SHA-256, installs the released wheel, then runs cross-package tests and release/deployment-plan checks. Customer run `33143386148` currently fails truthfully with HTTP 404 at the release download because `v0.3.0` has not been published.

## Current Microsoft Fabric external boundary

No enterprise Fabric workspace, tenant setting, capacity, connection, credential or runtime state has been modified. Real Fabric deployment remains a later adapter/integration step using approved tenant identity and environment bindings.

## Known limitations / blockers

- UI-driven release workflow PR #11 still requires merge before `Run workflow` is available from the default branch.
- Immutable framework `v0.3.0` GitHub Release is pending.
- Customer exact released-wheel integration is blocked only on that release.
- Phase 4 PR #9 is held open behind the 0.3.0 release boundary.
- No real Fabric item deployment has executed.
- No physical enterprise control-plane store has been exercised.
- Late/out-of-order correction, delete handling, FULL/SNAPSHOT, CDC and recovery orchestration remain future runtime slices.
- No Terraform implementation yet; `fabric-infra` remains intentionally deferred.

## Exact next implementation sequence

1. Merge PR #11 after the final docs-only CI rerun remains green.
2. From GitHub Actions, run `framework-release` on `main` with version `0.3.0`; verify tag, Release, wheel and `SHA256SUMS` assets.
3. Re-run Customer PR #6 exact integration and require released-wheel checksum verification, cross-package tests and DEV/UAT/PROD release-plan checks to pass; then merge Customer Phase 3.
4. Rebase/revalidate and merge Framework PR #9 as the `0.4.0` dispatcher slice.
5. Add the tiny Customer multi-dataset dispatcher scenario.
6. Continue with retry/backfill/replay, SNAPSHOT_DIFF, CDC/UPSERT, delete/schema/late-arrival handling and then the first real Fabric adapter.

Do not fake release or Fabric-estate validation.
