# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-28

## 1. Purpose

This document prevents the project from confusing architecture, deterministic reference implementation and real enterprise production evidence.

Evidence levels:

1. **Portable semantic implementation** — framework-owned contract/algorithm independent of Fabric.
2. **Deterministic certification** — unit/contract/reference proof for important invariants.
3. **Real Fabric integration evidence** — executed through approved Fabric Pipeline/Copy/Dataflow/Spark/Lakehouse/Warehouse surfaces with native run correlation.
4. **External enterprise controls** — identity, RBAC, networking, secrets, retention, monitoring/on-call, capacity and governance supplied by the enterprise/platform authority.

Levels 3 and 4 must never be inferred from levels 1 and 2.

## 2. Current overall assessment

Current unreleased 0.4.0 development branch:

```text
Portable semantic implementation     STRONG / materially expanded
Deterministic certification           STRONG for implemented slices
Real Fabric integration evidence      NOT YET PROVEN for this hardening branch
External enterprise controls          EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest coherent code/control-plane evidence before the current docs synchronization:

```text
branch: architecture/production-framework-blueprint
commit: 60d4d1362f504a51b3ecedfcb93c7c6ceb3d4578
GitHub Actions: 33175724889
build-wheel:      SUCCESS
Python 3.11:      SUCCESS
Python 3.13:      SUCCESS
pytest:           106 passed
```

The latest immutable public Framework release remains `v0.3.0`. Do **not** publish `v0.4.0` yet.

## 3. Evidence matrix

| Capability | Portable semantics | Deterministic certification | Real Fabric evidence | Enterprise controls | Assessment |
|---|---|---|---|---|---|
| Typed dataset metadata/effective config | Yes | Yes | N/A | N/A | IMPLEMENTED |
| Runtime override allow-list/hash | Yes | Yes | N/A | Operator authorization external | IMPLEMENTED contract |
| Composite WATERMARK + overlap | Yes | Yes | No current native adapter proof | Source permissions external | IMPLEMENTED portable |
| Bronze lineage envelope | Yes | Yes | No current Fabric landing proof | Storage governance external | IMPLEMENTED portable |
| Row DQ/quarantine accounting | Yes | Yes | No real quarantine-store proof | Access/retention external | IMPLEMENTED portable |
| SCD2 reference semantics | Yes | Yes | No current Fabric target adapter proof | Target access external | IMPLEMENTED portable |
| FULL -> REPLACE guards | Yes | Yes | No Fabric publication/swap proof | Target permissions/recovery external | IMPLEMENTED reference |
| SNAPSHOT -> SNAPSHOT_DIFF/delete guards | Yes | Yes | No Fabric publication proof | Delete governance external | IMPLEMENTED reference |
| Shared ordered current-state primitive | Yes | Yes | No target adapter proof | Target access external | IMPLEMENTED reference |
| SCD1 ordered current-state apply | Yes | Yes | No Fabric target adapter proof | Target permissions external | IMPLEMENTED reference |
| UPSERT ordered current-state apply | Yes | Yes | No Fabric target adapter proof | Target permissions external | IMPLEMENTED reference |
| APPEND identity/collision semantics | No | No | No | External controls later | GAP |
| Independent capture/apply executor policy | Yes | Yes | No real delegated apply run | N/A | IMPLEMENTED contract |
| ExecutionPlan concrete stage splitting | Yes | Yes | No real Fabric backend | N/A | IMPLEMENTED contract |
| Named engine capability profiles | Yes | Yes | Product docs checked; no native run proof | N/A | IMPLEMENTED contract |
| Generic native apply fails closed | Yes | Yes negative tests | No native equivalence run | N/A | IMPLEMENTED safety contract |
| Dataflow Gen2 incremental capture -> framework SCD1/UPSERT plan | Yes | Yes | No real Dataflow run yet | Connection/identity external | IMPLEMENTED contract; Fabric proof pending |
| Copy Job native capture delegation | Contract/profile only | Validation tests | No hardening-branch native run | Source support/identity external | PARTIAL |
| CaptureReceipt | Yes | Yes | No real native receipt ingestion yet | N/A | IMPLEMENTED contract |
| Extension registry/logical names | Yes | Yes | No Fabric runtime extension proof | Package supply chain external/shared | IMPLEMENTED contract |
| Metadata-driven dispatcher/failure isolation | Yes | Yes | No real Fabric Pipeline backend | Capacity policy external | IMPLEMENTED reference |
| Control-plane schema v2 | Yes | Yes on SQLAlchemy/SQLite | No approved persistent store | DB identity/backup external | IMPLEMENTED schema contract only |
| Capture/apply execution policy persisted separately | Yes | Yes | No production store proof | N/A | IMPLEMENTED schema contract |
| Retry attempt lineage | Partial vocabulary/schema only | No end-to-end retry certification | No | Operator policy external | P0 GAP |
| BACKFILL | Contract vocabulary only | No | No | Operator approval external | P0 GAP |
| REPLAY/quarantine replay | Schema concepts only | No end-to-end replay | No | Retention/access external | P0 GAP |
| FULL_REBUILD | Contract vocabulary only | No | No | Approval/recovery external | GAP |
| Unknown target-commit recovery | Design only | No | No | Incident process external | P0 GAP |
| CDC normalization/order/event identity | No complete implementation | No | No | Source CDC enablement external | P0 GAP |
| Snapshot -> CDC bootstrap handoff | No | No | No | Source capability external | P0 GAP |
| Schema evolution compatibility | Schema-change table/design only | No complete certification | No | Governance external | P0 GAP |
| General late/out-of-order policy | Current-state/SCD2 slices only | Partial | No | N/A | PARTIAL |
| Fabric Pipeline adapter | Design only | No | No | Workspace permission external | P0 GAP |
| Fabric Copy Activity adapter | Design/profile only | No native run | No | Connection/gateway external | P0 GAP |
| Fabric Copy Job adapter | Design/profile only | No native run | No | Connector/CDC configuration external | P0 GAP |
| Dataflow Gen2 adapter | Named profile/planner path only | Planner tests | No native run | Connection/gateway external | P0 GAP |
| Spark Job Definition/Environment adapter | Design only | No real SJD run | No | Environment/workspace identity external | P0 GAP |
| Persistent operator query/status surface | No production adapter | Reference lists only | No | Monitoring integration external | GAP |
| Immutable wheel/release path | Yes | GitHub CI/release proven for v0.3.0 | GitHub evidence, not Fabric runtime | Repository governance external | IMPLEMENTED delivery baseline |

## 4. Framework-first semantic guarantee

ADR 0009 establishes:

> Native Fabric features are capability-certified stage delegates. They do not replace framework-owned portable semantics for core mature Data Engineering patterns.

Current implementation now makes the physical stages explicit:

```text
ExecutionPolicy
  capture engine/profile/progress owner
  apply engine/profile

        -> capability validation
        -> immutable concrete ExecutionPlan
```

Canonical lifecycle:

```text
capture / movement
    -> normalize / transform
    -> apply
    -> reconcile
    -> state / audit
```

Example:

```text
Dataflow Gen2 incremental bucket refresh
    -> Bronze/staging
    -> CaptureReceipt
    -> framework SCD1/UPSERT
    -> reconciliation
    -> framework audit/state contract
```

Dataflow's native incremental destination bucket replacement is deliberately not labeled generic SCD1/UPSERT.

Native final-target apply remains unsupported by default. It can only be claimed after a named apply profile explicitly certifies semantic equivalence.

## 5. Current strongest portable guarantees

### Metadata and physical-plan safety

- strict immutable typed metadata;
- capture/apply strategies are independent;
- capture and apply execution engines/profiles are independent;
- effective config has deterministic hash;
- semantic fields are not mutable through arbitrary runtime overrides;
- capability profiles fail closed for unsupported combinations;
- `AUTO` resolves to concrete engines before immutable execution planning;
- capture certification never implies apply certification;
- custom metadata references logical registered extensions rather than arbitrary executable imports.

### Source-boundary correctness

- composite watermark `(watermark, tie_breaker...)` prevents same-timestamp loss for framework-owned incremental selection;
- FULL/SNAPSHOT completeness is explicit evidence rather than inferred from successful iteration;
- native/external capture has a typed `CaptureReceipt` boundary;
- exactly one authority owns physical capture progress.

### Destructive-load protection

FULL replacement includes incomplete/empty/drastic-drop guards before publication.

Snapshot diff includes complete-snapshot requirement, null/duplicate-key protection, quarantine-aware delete blocking, delete-all/delete-fraction guards and reconciliation before publication.

### Current-state/history semantics

Shared current-state primitive now backs both SCD1 and UPSERT and proves:

- composite merge keys;
- ordered event/version/sequence tuple support;
- latest-row selection within a batch;
- exact rerun idempotency;
- stale-row ignore/error policy;
- equal-position conflicting payload failure;
- changed unordered update fail-closed unless authorized;
- duplicate/stale/superseded metrics;
- target-only field preservation for generic UPSERT updates.

SCD2 proves deterministic current/history behavior, one-current-row invariant and bounded conflict/late-arrival handling.

### Failure isolation

Dispatcher reference proves selection, dependency/cycle validation, bounded concurrency, per-dataset exception isolation, dependent `BLOCKED`, unrelated sibling continuation and criticality-aware aggregate status.

### Control-plane semantic/runtime boundary

Schema v2 now separately persists:

```text
execution_policy        capture/movement policy
apply_execution_policy  apply policy
ordering_policy         source ordering semantics
```

while `CaptureReceipt` and run/progress evidence remain environment-local.

## 6. P0 gaps before next public release

The previous two blockers are now closed at reference level:

```text
ordered/idempotent framework UPSERT                 COMPLETE
explicit capture/apply executor separation          COMPLETE
```

Priority remaining gaps:

1. **Recovery** — attempt lineage, retryability, RETRY/BACKFILL/REPLAY/FULL_REBUILD and unknown-commit recovery.
2. **CDC** — normalized I/U/D envelope, event identity/order, duplicate/conflict rules, poison-event handling, checkpoint commit and bootstrap handoff.
3. **Schema evolution** — additive/breaking classification, type compatibility and run/audit disposition.
4. **APPEND** — append-once identity and conflicting duplicate policy, or explicit release-scope deferral.
5. **Real control plane** — supported persistent store/repository, migration behavior and operator queries, or explicitly bounded first-release scope.
6. **Fabric adapters** — Pipeline, Copy Activity, Copy Job, Dataflow Gen2, Spark Job Definition/Environment and native run correlation.
7. **Real hybrid Fabric proof** — at least one `native capture -> CaptureReceipt -> framework apply` DEV execution, preferably Dataflow/Copy + SCD1/UPSERT.

Native final-target apply certification is not a blocker if the release documents framework apply as the default and makes no native-apply guarantee.

## 7. External evidence this repository must not fake

Enterprise/platform responsibilities or joint integration evidence include:

- Fabric capacity/SKU and throttling policy;
- tenant settings;
- workspace/domain creation;
- Entra groups, service principals, workspace identity and RBAC;
- gateway/private endpoint/network configuration;
- secrets/key authority;
- source database CDC enablement/retention;
- production target backup/restore/retention;
- monitoring receiver, alert routing and on-call ownership;
- audit/quarantine retention/privacy classification;
- approvals/change-management where required.

The framework may define required integration evidence but must not claim these controls exist until an approved estate proves them.

## 8. Release gate

The current development line is **not approved for `v0.4.0` publication**.

Before release, re-run this audit against the actual head and ensure:

```text
code implementation
    == deterministic tests
    == canonical docs
    == release manifest/schema version
```

Any unresolved mismatch is a release blocker.
