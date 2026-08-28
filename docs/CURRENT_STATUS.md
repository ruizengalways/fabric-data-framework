# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

- Phase 0 — canonical architecture: **COMPLETE**.
- Phase 1 — framework foundation: **COMPLETE**.
- Phase 2 — first executable Customer WATERMARK/SCD2 vertical slice: **COMPLETE**.
- Phase 3 — enterprise delivery spine: **COMPLETE AND RELEASED AS `v0.3.0`**.
- Public-repository GitHub-hosted CI: **VALIDATED ON `ubuntu-latest`**.
- UI-driven immutable release path: **VALIDATED IN PRODUCTION USE**.
- Phase 4 — metadata-driven multi-dataset dispatcher/failure isolation: **0.4.0 CANDIDATE BEING REBASED/REVALIDATED ON PR #9**.

## Last completed step

Framework `v0.3.0` was successfully published by GitHub Actions run `33156000907` from `main`.

Published release assets:

```text
fabric_data_framework-0.3.0-py3-none-any.whl
SHA256SUMS
```

GitHub records the wheel digest as:

```text
sha256:37a4734e48e5a43240035c19174924231f565ca2fedb30484e691bc19c2cafc0
```

Customer PR #6 then reran exact released-artifact integration. It downloaded the `v0.3.0` wheel and checksum, verified SHA-256, installed the released framework, ran cross-package tests, and validated release-manifest plus DEV/UAT/PROD deployment plans. Final Customer CI run `33157883463` passed both jobs, and Customer PR #6 was squash-merged as commit `32f6cabc093541270b271ae37754ba8fe1e9544b`.

The 0.3.0 immutable release boundary is therefore frozen and proven end to end.

## Existing delivery spine

Framework `v0.3.0` provides:

```text
fabric-framework validate-tag
fabric-framework control-plane-migrate
fabric-framework metadata-materialize
fabric-framework release-manifest
fabric-framework deployment-plan
fabric-framework deployment-record
```

Release workflow capabilities include:

- GitHub Actions UI initiation via `workflow_dispatch`;
- manual release restricted to `main`;
- package/tag identity validation;
- Ruff, compile, dependency and pytest gates;
- explicit build-backend installation;
- immutable wheel build;
- portable `SHA256SUMS` generation and verification;
- annotated tag creation only after validation/build succeeds;
- GitHub Release creation;
- recovery when a tag exists without a Release;
- refusal to overwrite an existing Release or move an existing tag.

## Phase 4 dispatcher candidate

Framework PR #9 contains version `0.4.0` and implements the generic metadata-driven dispatcher above dataset executors:

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

The original Phase 4 branch was opened before later 0.3.0 release-workflow hardening, so it is being reconstructed on current `main` rather than merging stale release/docs state. Its earlier GitHub-hosted validation passed wheel build, Python 3.11, Python 3.13 and **44 tests**.

## Current external boundary

No enterprise Fabric workspace, tenant setting, capacity, connection, credential or runtime state has been modified. Real Fabric deployment remains a later adapter/integration step using approved tenant identity and environment bindings.

## Known limitations / blockers

- Phase 4 must complete rebased CI before merge.
- No tiny Customer multi-dataset dispatcher scenario yet.
- Retry/backfill/replay attempt orchestration is not implemented yet.
- FULL/SNAPSHOT -> SNAPSHOT_DIFF and CDC -> UPSERT representative executors are not implemented yet.
- Delete, schema-evolution and general late/out-of-order correction policies remain future slices.
- No real Fabric item deployment has executed.
- No physical enterprise control-plane store has been exercised.
- No Terraform implementation yet; `fabric-infra` remains intentionally deferred.

## Exact next implementation sequence

1. Rebase/revalidate and merge Framework PR #9 as the `0.4.0` dispatcher slice.
2. Add a tiny Customer multi-dataset graph proving `SUCCESS`, `PARTIAL_SUCCESS`, dependency blocking and unrelated sibling continuation.
3. Implement retry/backfill/replay and attempt lineage.
4. Add representative SNAPSHOT_DIFF and CDC/UPSERT executors.
5. Implement delete/late-arrival/schema-evolution correctness policies.
6. Add the first real Fabric Environment + Notebook + Pipeline adapter and DEV smoke run.
7. Add a real persistent control-plane adapter and operational query surface.
8. Defer `fabric-infra` Terraform until the data-platform runtime is proven in the company Fabric estate.

Do not fake release or Fabric-estate validation.
