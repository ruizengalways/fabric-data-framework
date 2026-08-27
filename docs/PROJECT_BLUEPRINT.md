# fabric-data-framework — Project Blueprint

Status: Canonical
Last updated: 2026-08-28

## 1. Goal

Build a production-grade reusable Microsoft Fabric data-engineering runtime package consumed by domain repositories through explicit immutable versions.

The framework standardizes stable cross-domain behaviour while domain transformations and business rules remain explicit in domain repositories.

## 2. Design principles

1. Share versioned code, not a cross-domain shared runtime.
2. Metadata drives stable behaviour; business logic remains code.
3. Capture and apply strategies are independent axes.
4. Git semantic configuration, deployed snapshots, operational overrides and runtime state are separate concerns.
5. Dataset is the default failure/isolation boundary.
6. Quarantine, reconciliation, audit and recovery are execution semantics, not afterthoughts.
7. Stateful progress advances only after required target/reconciliation gates.
8. DEV/UAT/PROD promote the same immutable release identity while runtime state remains environment-local.
9. Correctness is proved with small deterministic scenarios before strategy breadth or infrastructure scale.

## 3. Implemented package shape

```text
src/fabric_data_framework/
  config.py            typed semantic metadata + operational overrides
  infrastructure.py    logical Fabric resource resolution contract
  runtime.py           run context, statuses and state/watermark gates
  operations.py        audit, row accounting, quarantine and reconciliation contracts
  control_plane.py     logical relational control-plane schema
  deployment.py        provider-neutral release/deployment provenance
  repository.py        control-plane repository protocol + in-memory reference adapter
  watermark.py         composite incremental selection
  bronze.py            normalized Bronze envelope
  quality.py           reusable row validation/quarantine primitives
  scd2.py              deterministic SCD2 reference engine + in-memory target
  reconciliation.py    SCD2/reference completion gates
  execution.py         reference WATERMARK -> Bronze -> DQ -> SCD2 executor
```

The in-memory adapters are deliberate test/reference implementations, not the chosen enterprise Fabric physical store.

## 4. Metadata contract

`DatasetConfig` declares source/target identity, capture/apply strategy, business/merge keys, WATERMARK semantics, event time, tracked columns, execution group/criticality/dependencies and DQ/reconciliation policies.

Runtime overrides remain allow-listed operational values only. Semantic changes such as merge keys or apply strategy require source-controlled deployment.

## 5. WATERMARK semantics

For `WATERMARK`, the framework orders source records by:

```text
(watermark_column, tie_breaker...)
```

and selects positions strictly greater than the committed position. This prevents data loss when multiple records share the same timestamp.

An optional overlap window re-reads a bounded datetime range and relies on idempotent target behaviour. Null watermark or tie-breaker values are rejected before mutation because their source position is not safely orderable.

## 6. Bronze contract

Captured rows are wrapped with normalized metadata including pipeline/dataset run IDs, source identity, ingestion timestamp, source commit time/sequence, operation and schema version. Domain/provider-specific envelopes do not leak into downstream strategy code.

## 7. Data quality and quarantine

Reusable `RowRule` execution separates accepted and quarantined Bronze records. Row-level quarantine is a handled outcome that can still permit state advancement when reconciliation accounts for it and policy allows it.

Batch-level quarantine remains a state-commit blocker. System/permission/code failures are failures, not quarantine.

## 8. SCD2 invariants

The reference SCD2 engine enforces:

- business key required;
- tracked-column hash determines change/no-change;
- unchanged tracked attributes do not create a new version;
- changed attributes close the current version and open one new current version;
- at most one current row per business key;
- exact rerun of an already-applied version is idempotent;
- a conflicting different row at the exact current effective timestamp fails explicitly;
- late/out-of-order event earlier than the current version fails explicitly until a later policy is implemented.

Delete policy and general late-arrival correction are intentionally not solved in this slice.

## 9. Reference dataset execution sequence

```text
resolve deployed config
  -> read committed watermark
  -> composite WATERMARK selection
  -> normalized Bronze records
  -> domain-supplied DQ rules
  -> row quarantine + lineage
  -> domain mapper
  -> calculate proposed SCD2 state
  -> reconcile row accounting + SCD2 invariant
  -> commit target
  -> commit watermark/state
  -> durable dataset/step audit
```

Target and watermark are only mutated after required reconciliation passes. Physical systems may not provide a distributed transaction between target and control store, so later physical adapters must use idempotency/reconciliation to recover if target commit succeeds but state/audit commit becomes uncertain.

## 10. Control-plane and environment model

The Phase 1 logical 19-table control-plane schema remains canonical. Phase 2 adds repository APIs needed by the vertical slice without selecting Warehouse vs Lakehouse/Delta as the final store.

Each environment has independent state. CI/CD promotes schema/semantic definitions, never DEV watermarks/run history/overrides/quarantine state into UAT/PROD.

## 11. Testing strategy and current evidence

Framework unit/contract/integration tests now cover:

- Phase 1 metadata/override/control-plane/deployment contracts;
- duplicate timestamp/tie-breaker WATERMARK selection;
- no-new-row watermark preservation;
- SCD2 insert/change/unchanged/idempotent rerun;
- explicit late-arrival rejection;
- row-level quarantine with watermark advancement after accounting/reconciliation;
- reconciliation failure preserving target and committed watermark.

Customer repository adds the cross-package domain integration scenario.

## 12. Versioning

`0.1.0` established framework contracts. `0.2.0` adds the first executable capture/Bronze/DQ/SCD2/reconciliation vertical slice. Neither has yet been published as an immutable package release; Phase 3 introduces the delivery spine.

## 13. Roadmap status

### Phase 0 — COMPLETE
Architecture, ownership and recoverable docs.

### Phase 1 — COMPLETE
Typed metadata/control-plane/runtime/deployment foundations.

### Phase 2 — COMPLETE
Reusable primitives required for one `crm.customer` WATERMARK -> Bronze -> validation/quarantine -> SCD2 -> reconciliation -> state-commit vertical slice, proven with Customer cross-package integration tests.

### Phase 3 — NEXT: enterprise delivery spine
Implement provider-neutral CI/CD around the contracts already established:

- PR CI for Framework and Customer;
- framework wheel build/test/release versioning;
- Customer exact framework dependency validation;
- immutable release/config manifest and hashes;
- control-plane migration/materialization command surface;
- at least one GitHub-driven deployment path and one Fabric-native promotion-compatible path;
- environment binding and deployment-history recording;
- DEV/UAT/PROD smoke/approval gates where credentials/estate access permit.

### Later phases
Complete capture/apply strategy breadth, runtime hardening/multi-dataset orchestration, streaming and Terraform infrastructure automation.

## 14. Documentation obligation

Every coherent implementation slice updates `docs/CURRENT_STATUS.md`; architecture changes update this blueprint/ADRs. Routine work inside accepted architecture does not stop for approval after every small file.
