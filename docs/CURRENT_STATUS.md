# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine core: **COMPLETE**.
- Public-repository GitHub-hosted CI: **VALIDATED ON `ubuntu-latest` AND MERGED**.
- Phase 4 dispatcher: **CI-VALIDATED ON PR #9 AS 0.4.0 CANDIDATE; HELD OPEN UNTIL 0.3.0 RELEASE**.

## Last completed step

Hardened the pending `v0.3.0` release artifact contract on branch `fix/portable-release-checksums` before the first immutable framework release is created.

Framework CI and release workflows now generate `SHA256SUMS` from inside `dist/`:

```text
<sha256>  fabric_data_framework-0.3.0-py3-none-any.whl
```

rather than embedding the producer-local path `dist/<wheel>` in the checksum file. This makes the checksum directly verifiable after a consumer downloads the release assets into any directory.

The active runner remains GitHub-hosted `ubuntu-latest`.

## Existing delivery spine

Framework source version `0.3.0` is on `main` and provides:

```text
fabric-framework validate-tag
fabric-framework control-plane-migrate
fabric-framework metadata-materialize
fabric-framework release-manifest
fabric-framework deployment-plan
fabric-framework deployment-record
```

The tag-triggered release workflow validates the package/tag match, runs isolated static checks and tests, builds the wheel, generates `SHA256SUMS`, refuses release overwrite and creates the GitHub Release from the immutable tag.

## Phase 4 state

Framework PR #9 implements metadata-driven multi-dataset dispatcher/failure isolation as version `0.4.0`. Its GitHub-hosted validation run `33143225157` passed wheel build, Python 3.11, Python 3.13, static checks and **44 tests**.

PR #9 remains intentionally open. It must not merge until the immutable `v0.3.0` boundary has been frozen from `main`.

## Immutable release state

Immutable tag/release `v0.3.0` still does not exist. This is the immediate external/manual release gate because the available GitHub connector does not expose tag creation.

Customer Phase 3 PR #6 must continue to fail its exact-release integration until the real framework release exists. A missing tag/release is not converted into a skipped or false-green gate.

## Current Microsoft Fabric external boundary

No enterprise Fabric workspace, tenant setting, capacity, connection, credential or runtime state has been modified. Real Fabric deployment remains a later adapter/integration step using approved tenant identity and environment bindings.

## Known limitations / blockers

- Portable checksum hardening needs PR CI and merge to `main` before tagging `v0.3.0`.
- Immutable framework `v0.3.0` GitHub Release is still pending.
- Customer exact-release integration is blocked on that release.
- Phase 4 PR #9 is held open behind the 0.3.0 release boundary.
- No real Fabric item deployment has executed.
- No physical enterprise control-plane store has been exercised.
- Late/out-of-order correction, delete handling, FULL/SNAPSHOT, CDC and recovery orchestration remain future runtime slices.
- No Terraform implementation yet; `fabric-infra` remains intentionally deferred.

## Exact next implementation sequence

1. Validate and merge portable checksum hardening to `main`.
2. Create/push immutable framework tag `v0.3.0` from the resulting validated `main`; let the release workflow create the GitHub Release. Do not manually pre-create the Release.
3. Make Customer CI consume and verify the released framework wheel/checksum, then complete Customer Phase 3 PR #6.
4. Rebase/revalidate and merge Framework PR #9 as the `0.4.0` dispatcher slice.
5. Add the tiny Customer multi-dataset dispatcher scenario.
6. Continue with retry/backfill/replay, SNAPSHOT_DIFF, CDC/UPSERT, delete/schema/late-arrival handling and then the first real Fabric adapter.

Do not fake release or Fabric-estate validation.
