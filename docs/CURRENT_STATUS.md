# Current Status — fabric-data-framework

Last updated: 2026-08-28

## Current phase

Phase 0 — Canonical architecture and repository boundaries: **COMPLETE**.

Phase 1 — Framework foundation: **READY TO START**.

## Last completed step

Extended the canonical architecture with the production metadata-driven runtime/control-plane design, including per-dataset semantic metadata, audited runtime overrides, multi-dataset failure isolation, quarantine, pipeline/dataset/step audit, reconciliation gates, dataset leases and reprocess/replay lineage.

## Current implementation

Documentation-only foundation. No framework runtime package or Fabric execution code has been implemented yet.

The architecture now explicitly supports domains with tens of tables without requiring one bespoke pipeline per table or making the entire batch fail immediately when one independent dataset fails.

## Important decisions made

- Three repositories have distinct Infrastructure Platform, Reusable Data Runtime and Customer Domain ownership.
- Domains consume a versioned framework package; they do not invoke one shared cross-workspace runtime.
- Metadata-driven execution is a first-class framework capability.
- Source-controlled semantic metadata is canonical; deployed metadata snapshots are runtime-readable versions of that configuration.
- Runtime operational overrides are audited and restricted to approved operational knobs; they cannot silently change PROD merge keys, apply strategy, schema contracts or equivalent semantics.
- Capture strategy and apply strategy are independent configuration axes.
- Merge/business keys, watermark/event-time/tie-breaker columns and stable execution policy are declared per dataset.
- A dataset is the default failure boundary; unrelated datasets continue where safe.
- Parent orchestration aggregates dataset outcomes into `SUCCESS`, `PARTIAL_SUCCESS` or `FAILED` after eligible independent work completes.
- Dataset dependencies block only dependent work; unrelated branches continue.
- Control-plane schema/migrations are a framework concern; physical hosting is an infrastructure concern.
- Pipeline, dataset and significant-step audits are durable control-plane state; text logs alone are insufficient.
- Quarantine is first-class and distinct from system/infrastructure failure.
- Production reconciliation accounts for accepted, quarantined/rejected and intentionally filtered records according to policy; no silent row loss.
- Watermark/state advances only after target commit and required reconciliation gates.
- A dataset lease/optimistic concurrency mechanism protects stateful datasets from overlapping writers.
- Retry/backfill/replay/full rebuild are explicit run modes with lineage.
- Framework/domain code resolves Fabric resources through an infrastructure contract and does not hard-code enterprise workspace/resource identities.
- Initial infrastructure implementation is deferred while using a pre-provisioned enterprise Fabric estate.
- Delivery is trunk-based and promotes the same immutable Git SHA through environments.
- Implementation will proceed in coherent, testable capability slices; routine work inside accepted architecture does not pause for approval after every small class/file.

## Files/components implemented

Documentation only:

- `README.md`
- `docs/ECOSYSTEM_BLUEPRINT.md`
- `docs/PROJECT_BLUEPRINT.md`
- `docs/CONTROL_PLANE_DESIGN.md`
- `docs/CURRENT_STATUS.md`
- `docs/adr/0001-three-repository-ownership.md`
- `docs/adr/0002-capture-vs-apply-strategy.md`
- `docs/adr/0003-control-plane-ownership.md`
- `docs/adr/0004-metadata-driven-orchestration-and-failure-isolation.md`
- `docs/runbooks/README.md`

## Tests/checks executed

Architecture/documentation validation:

- re-read canonical ecosystem/framework/customer status before changing design;
- verified metadata-driven Pipeline direction against current Microsoft Fabric Data Factory documentation for parameterized pipelines, Lookup-driven dynamic selection, ForEach bounded parallelism and control-flow dependencies;
- checked the design preserves Git as semantic source of truth while allowing audited operational control-table overrides;
- checked a single dataset failure does not require cancellation of unrelated dataset executions;
- checked critical failures still produce a truthful final failed aggregate for alerting;
- checked quarantine does not hide system errors and cannot advance state for quarantined batches;
- checked audit/reconciliation/state models support retry/replay diagnosis and provenance.

## Test results

PASS — architecture is internally consistent and maps to current Fabric orchestration capabilities. No runtime code exists yet, so no unit/integration test suite has run.

## Known limitations

- No Python package skeleton yet.
- No typed metadata/effective-config implementation yet.
- No control-plane migration implementation yet.
- No dispatcher/dataset executor implementation yet.
- No WATERMARK/SCD2/CDC runtime algorithms yet.
- No CI, package release, Fabric deployment or environment promotion automation yet.
- No Fabric runtime has been exercised.

## Open issues/blockers

No architecture blocker identified for Phase 1.

The physical control-plane store and exact Fabric deployment mechanism are implementation choices to finalize when needed; they must not change the framework contracts. Fabric limits/syntax must be rechecked against current official documentation at implementation time.

## Last known-good release / commit

No framework package release exists yet. Current state is architecture/documentation only.

## Exact next implementation step

**Phase 1 — coherent framework foundation slice.**

Implement substantially more than the earlier micro-step, while staying inside the accepted architecture:

1. create `pyproject.toml`, `src/fabric_data_framework/`, `tests/` and minimal quality/test tooling;
2. implement typed enums for capture/apply strategy, run mode, dataset status, pipeline status and criticality;
3. implement typed dataset/source/target/load/orchestration/DQ/reconciliation metadata models, including business/merge keys, watermark `(column, tie_breaker)`, event-time and execution-group metadata;
4. implement semantic-vs-operational override allow-list validation plus immutable `EffectiveDatasetConfig` resolution/hash;
5. implement the typed infrastructure/environment resolution contract;
6. implement immutable runtime context and correlation/run identifiers;
7. define audit/quarantine/reconciliation contracts for pipeline, dataset and step execution;
8. establish initial control-plane schema/migration definitions for dataset metadata, runtime override, watermark/dataset state/lease, pipeline/dataset/step run, reconciliation, quarantine, reprocess and deployment history at an appropriate first-slice depth;
9. add high-value unit/contract tests for valid/invalid metadata, forbidden overrides, effective-config precedence/hash, state/watermark invariants at contract level, status aggregation policy and audit/quarantine model validation;
10. update Blueprint/ADR/CURRENT_STATUS after the coherent slice is complete.

Do **not** stop for review after each small implementation item above. Complete the coherent foundation slice unless a real architecture conflict or unsafe external action is encountered.

Do **not** yet implement actual WATERMARK extraction, SCD2/CDC algorithms, Fabric item deployment or Terraform in this Phase 1 foundation slice.
