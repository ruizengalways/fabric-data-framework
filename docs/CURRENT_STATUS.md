# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine: **COMPLETE AND RELEASED AS `v0.3.0`**.
- Phase 4 — metadata-driven multi-dataset dispatcher/failure isolation: **MERGED TO `main` AS 0.4.0; IMMUTABLE `v0.4.0` RELEASE PENDING**.
- Public-repository GitHub-hosted CI: **VALIDATED ON `ubuntu-latest`**.
- UI-driven immutable release path: **VALIDATED IN PRODUCTION USE**.

## Last completed step

Framework PR #9 was reconstructed on the released 0.3.0 baseline, revalidated, and squash-merged to `main` as commit `aaf346ba048f20d113208de566c648b0da58e373`.

Rebased PR CI run `33158138943` and merge-triggered `main` run `33158188037` both passed:

```text
build-wheel       SUCCESS
test-python-3.11  SUCCESS
test-python-3.13  SUCCESS
```

Framework source version on `main` is now `0.4.0`.

## Released baseline

Framework `v0.3.0` remains the latest immutable GitHub Release. Release run `33156000907` published:

```text
fabric_data_framework-0.3.0-py3-none-any.whl
SHA256SUMS
```

Customer exact released-wheel integration passed against those assets, and Customer Phase 3 PR #6 was squash-merged as commit `32f6cabc093541270b271ae37754ba8fe1e9544b`.

## Phase 4 dispatcher

The merged 0.4.0 dispatcher provides:

```text
pipeline request
  -> list deployed datasets
  -> resolve effective configs
  -> filter enabled / execution group / explicit request
  -> validate dependencies and cycles
  -> bounded parallel ready-set execution
  -> isolate dataset executor failures
  -> block only failed-dependent branches
  -> continue unrelated siblings
  -> aggregate SUCCESS / PARTIAL_SUCCESS / FAILED
```

Implemented contracts include:

- metadata-driven dataset selection;
- execution-group filtering;
- explicit requested-dataset validation;
- dependency validation and cycle detection;
- bounded concurrency honoring dataset orchestration limits;
- dataset-level exception isolation;
- dependent `BLOCKED` outcomes without cancelling unrelated datasets;
- criticality-aware pipeline aggregation;
- pipeline/dataset lineage IDs;
- thread-safe in-memory control-plane support and pipeline-run upsert.

The framework test suite now contains **44 tests** covering the dispatcher plus prior runtime/delivery contracts.

## Current release boundary

`main` contains 0.4.0 source, but immutable GitHub Release `v0.4.0` does not yet exist.

Before Customer consumes the dispatcher, publish `v0.4.0` through the same proven UI release path:

```text
GitHub -> fabric-data-framework -> Actions -> framework-release -> Run workflow
Use workflow from: main
version: 0.4.0
```

Customer must then exact-pin/install the published 0.4.0 wheel rather than consuming framework `main`.

## Current external boundary

No enterprise Fabric workspace, tenant setting, capacity, connection, credential or runtime state has been modified. Real Fabric deployment remains a later adapter/integration step using approved tenant identity and environment bindings.

## Known limitations / blockers

- Immutable Framework `v0.4.0` release is pending.
- Customer multi-dataset dispatcher scenario must wait for the published 0.4.0 artifact.
- Retry/backfill/replay attempt orchestration is not implemented yet.
- FULL/SNAPSHOT -> SNAPSHOT_DIFF and CDC -> UPSERT representative executors are not implemented yet.
- Delete, schema-evolution and general late/out-of-order correction policies remain future slices.
- No real Fabric item deployment has executed.
- No physical enterprise control-plane store has been exercised.
- No Terraform implementation yet; `fabric-infra` remains intentionally deferred.

## Exact next implementation sequence

1. Publish/prove immutable Framework `v0.4.0` from the GitHub Actions UI.
2. Upgrade Customer exact framework pin/integration to 0.4.0 and add a tiny multi-dataset graph proving `SUCCESS`, `PARTIAL_SUCCESS`, dependency blocking and unrelated sibling continuation.
3. Implement retry/backfill/replay and attempt lineage.
4. Add representative SNAPSHOT_DIFF and CDC/UPSERT executors.
5. Implement delete/late-arrival/schema-evolution correctness policies.
6. Add the first real Fabric Environment + Notebook + Pipeline adapter and DEV smoke run.
7. Add a real persistent control-plane adapter and operational query surface.
8. Defer `fabric-infra` Terraform until the data-platform runtime is proven in the company Fabric estate.

Do not fake release or Fabric-estate validation.
