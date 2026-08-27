# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

Phase 0 — canonical architecture: **COMPLETE**.

Phase 1 — framework foundation: **COMPLETE**.

Phase 2 — first executable Customer WATERMARK/SCD2 vertical-slice framework capability: **COMPLETE**.

## Last completed step

Extended source package version from `0.1.0` to `0.2.0` with the reusable algorithms/adapters required by the first realistic domain slice:

- environment-local in-memory control-plane repository adapter;
- composite WATERMARK filtering;
- normalized Bronze envelope;
- reusable row validation/quarantine;
- deterministic SCD2;
- reconciliation;
- target/state commit sequencing;
- end-to-end reference executor;
- integration tests with Customer domain fixtures.

## Implemented components

New Phase 2 modules:

- `repository.py`
- `watermark.py`
- `bronze.py`
- `quality.py`
- `scd2.py`
- `reconciliation.py`
- `execution.py`

Existing `runtime.StateCommitGate` was refined so **batch** quarantine blocks state advancement while policy-accounted row-level quarantine can advance state after successful reconciliation. This matches the canonical no-silent-loss/quarantine model.

## Correctness now demonstrated

- `(watermark, tie_breaker)` ordering avoids duplicate-timestamp loss.
- Null watermark/tie-breaker values fail capture ordering rather than being silently quarantined after an unsafe position decision.
- Row-level DQ quarantine is lineage-recorded and included in row accounting.
- SCD2 insert/change/unchanged behaviour maintains one current row per business key.
- Unchanged later source records do not create SCD2 versions.
- Exact reruns are idempotent.
- Late/out-of-order records are explicitly rejected until a supported correction policy is implemented.
- Required reconciliation failure commits neither proposed target rows nor watermark.
- Target is committed before watermark/state; future physical adapters must use idempotent recovery for uncertain cross-store commit outcomes because no distributed transaction is assumed.

## Tests/checks executed

Framework local validation:

- `pytest -q`: **30 passed**.
- Phase 1 24 tests remain green plus new WATERMARK/SCD2/executor tests.
- `python -m compileall`: PASS.
- wheel build: PASS (`fabric_data_framework-0.2.0-py3-none-any.whl`) and new Phase 2 modules verified in wheel contents.

Cross-package Customer integration validation:

- Customer `pytest -q`: **3 passed** against framework `0.2.0` source under test.
- Covers source-controlled metadata loading, initial batch, duplicate watermark timestamps, row quarantine, changed/unchanged SCD2 records, rerun/idempotency and failed-reconciliation/no-state-advance.

## Known limitations

- In-memory repository and target are reference/test adapters, not Fabric persistence implementations.
- Late/out-of-order SCD2 correction policy is not implemented; such records fail explicitly.
- Delete semantics are not yet implemented by the SCD2 engine.
- No FULL/SNAPSHOT/CDC capture runtime yet.
- No UPSERT/SCD1/SNAPSHOT_DIFF runtime yet.
- No Fabric Pipeline/Notebook deployment item yet.
- No GitHub Actions/Azure Pipelines CI workflow or immutable package publishing yet.
- No physical enterprise Fabric control-plane adapter/integration test yet.
- No Terraform.

## Open issues/blockers

No architecture blocker for Phase 3.

External DEV/UAT/PROD deployment cannot be proven without selecting/authorizing an enterprise Fabric deployment mechanism and credentials, but provider-neutral CI/build/release plumbing can be implemented before that external integration.

## Package/version state

Source package version: `0.2.0`.

No immutable published framework package release exists yet; Phase 3 introduces release automation.

## Exact next implementation step

**Phase 3 — enterprise delivery spine, implemented as another coherent slice rather than micro-steps.**

1. Add GitHub Actions PR CI for framework and customer (lint/compile/test/package/metadata validation).
2. Add an immutable framework build/release artifact workflow and version/tag guardrails without publishing mutable branch dependencies.
3. Add Customer dependency validation for exact `fabric-data-framework==0.2.0` (or the released Phase 2 version) and config-bundle hashing.
4. Add CLI/command entry points for control-plane schema migration and semantic metadata materialization so Fabric-native or external deployment tooling calls one contract.
5. Add release/deployment manifest generation containing Git SHA, framework version, config hash/schema version and Fabric item manifest version.
6. Add deployment-history write contract/adapters suitable for later Fabric estate binding.
7. Implement/test provider-neutral environment binding inputs and dry-run deployment planning.
8. Keep DEV/UAT/PROD runtime state explicitly non-promotable.
9. Where credentials/estate access are available, wire one GitHub-driven Fabric deployment path and a Fabric Deployment Pipeline-compatible promotion path; otherwise leave only the external execution edge unverified and record it precisely.

Do not implement Terraform or the entire remaining strategy catalog in Phase 3.
