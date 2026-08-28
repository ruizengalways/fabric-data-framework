# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine core: **COMPLETE**.
- Public-repository GitHub-hosted CI: **VALIDATED ON `ubuntu-latest` IN PR #8**.

## Last completed step

The repository is public and Framework CI/release workflows have been moved from the temporary self-hosted Bear runner back to GitHub-hosted `ubuntu-latest` on PR #8 (`chore/github-hosted-runners`).

GitHub-hosted workflow run `33140853145` completed successfully:

```text
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
runner group      GitHub Actions
requested label   ubuntu-latest
```

The Phase 3 delivery spine remains unchanged:

- framework package version `0.3.0`;
- PR/main CI with Python 3.11/3.13 tests, isolated Ruff correctness checks, compile and wheel build;
- tag-triggered immutable framework release workflow;
- deterministic semantic config-bundle hashing;
- immutable `ReleaseManifest` identity;
- environment-local bindings and deployment planning;
- control-plane migration / metadata materialization / deployment-history CLI;
- runtime-state protection during promotion.

Historical Bear runs remain valid evidence, but Bear is no longer part of the active CI design for this public reference repository.

## Implemented Phase 3 commands

```text
fabric-framework validate-tag
fabric-framework control-plane-migrate
fabric-framework metadata-materialize
fabric-framework release-manifest
fabric-framework deployment-plan
fabric-framework deployment-record
```

## Immutable release state

Framework source version `0.3.0` is on `main`, but immutable tag/release `v0.3.0` does not yet exist. The release workflow now targets `ubuntu-latest`.

Customer exact-version integration must remain blocked until `v0.3.0` exists; a missing tag should fail that gate rather than produce a false-green skipped integration.

## Current Microsoft Fabric external boundary

No enterprise Fabric workspace, tenant setting, capacity, connection, credential or runtime state has been modified by repository CI/CD work. Real Fabric deployment remains an adapter/integration step using approved tenant identity and environment bindings.

## Known limitations / blockers

- Immutable framework `v0.3.0` GitHub Release is still pending.
- No real Fabric item deployment has executed.
- No service principal/managed identity deployment identity is configured.
- No physical enterprise control-plane store has been exercised; SQLite/SQLAlchemy is the current contract proof.
- No Fabric Pipeline/Notebook item definition exists yet.
- Multi-dataset dispatcher/failure isolation is pending.
- Late/out-of-order correction and delete handling are incomplete.
- FULL/SNAPSHOT, CDC and remaining apply strategies are pending.
- Backfill/replay runtime orchestration is only partially represented by contracts.
- No Terraform implementation yet; `fabric-infra` remains intentionally deferred.

## Exact next implementation sequence

1. Merge PR #8 after the successful GitHub-hosted CI validation.
2. Publish/prove immutable framework release `v0.3.0` on GitHub-hosted Actions.
3. Complete Customer exact `0.3.0` integration and merge Customer Phase 3 PR #6.
4. Implement metadata-driven multi-dataset dispatcher, dependency blocking, bounded concurrency and aggregate `SUCCESS` / `PARTIAL_SUCCESS` / `FAILED` outcomes.
5. Add a tiny Customer multi-dataset scenario proving failure isolation.
6. Implement recovery orchestration for retry/backfill/replay plus attempt lineage.
7. Add representative FULL/SNAPSHOT -> SNAPSHOT_DIFF and CDC -> UPSERT scenarios.
8. Add schema-evolution/delete/late-arrival policy handling.
9. Build the first real Fabric adapter: Environment/package installation plus Notebook/Pipeline item deployment and smoke execution in an approved DEV workspace.
10. Bind a real environment-local control-plane store and deployment identity when enterprise resources are available.

Do not fake release or Fabric-estate validation, and do not create dozens of synthetic domain tables merely for coverage.
