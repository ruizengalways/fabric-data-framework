# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-28

## 1. Purpose

This document prevents the project from confusing a good design, a deterministic reference implementation and real enterprise production evidence.

`fabric-data-framework` is intended to become a stable reusable wheel for enterprise Microsoft Fabric Data Engineering. A capability is not called production-ready simply because a Python class, ADR or Fabric item exists.

For every material capability, distinguish four evidence levels:

1. **Portable semantic implementation** — framework-owned contract/algorithm exists independent of Fabric.
2. **Deterministic certification** — unit/contract/reference execution proves important success/failure invariants.
3. **Real Fabric integration evidence** — the capability has run through approved Fabric Pipeline/Copy/Dataflow/Spark/Lakehouse/Warehouse surfaces with retained native run correlation.
4. **External enterprise controls** — tenant settings, Entra identity, RBAC, networking, gateway/private access, secrets, retention, monitoring/on-call, capacity and governance are supplied and proven by the enterprise/platform authority.

Levels 3 and 4 must never be inferred from levels 1 and 2.

## 2. Current overall assessment

Current unreleased 0.4.0 development branch:

```text
Portable semantic implementation     STRONG / materially expanded
Deterministic certification           STRONG for implemented slices
Real Fabric integration evidence      NOT YET PROVEN for this hardening branch
External enterprise controls          EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest validated implementation evidence before the final documentation audit:

```text
branch: architecture/production-framework-blueprint
commit: 82bf3d97e6e08e9620bacdd1de25a14a2f7d489c
GitHub Actions: 33172961692
build-wheel:      SUCCESS
Python 3.11:      SUCCESS
Python 3.13:      SUCCESS
pytest:           91 passed
```

The latest immutable public Framework release remains `v0.3.0`. Do **not** publish `v0.4.0` yet.

## 3. Evidence matrix

| Capability | Portable semantics | Deterministic certification | Real Fabric evidence | Enterprise controls | Assessment |
|---|---|---|---|---|---|
| Typed dataset metadata/effective config | Yes | Yes | N/A | N/A | IMPLEMENTED |
| Runtime override allow-list/hash | Yes | Yes | N/A | Operator authorization external | IMPLEMENTED contract |
| Composite WATERMARK + overlap | Yes | Yes | Prior domain reference only; no current native adapter proof | Source permissions external | IMPLEMENTED portable; Fabric adapter pending |
| Bronze lineage envelope | Yes | Yes | No current Fabric landing proof | Storage governance external | IMPLEMENTED portable |
| Row DQ/quarantine accounting | Yes | Yes | No real Fabric quarantine store proof | Access/retention external | IMPLEMENTED portable |
| SCD2 reference semantics | Yes | Yes | No current Fabric target adapter proof | Target access external | IMPLEMENTED portable |
| FULL -> REPLACE guards | Yes | Yes | No Fabric publication/swap proof | Target permissions/recovery external | IMPLEMENTED reference |
| SNAPSHOT -> SNAPSHOT_DIFF/delete guards | Yes | Yes | No Fabric publication proof | Delete governance external | IMPLEMENTED reference |
| SCD1 ordered current-state apply | Yes | Yes | No Fabric target adapter proof | Target permissions external | IMPLEMENTED reference |
| UPSERT current-state apply | No | No | No | External controls later | P0 GAP |
| APPEND identity/collision semantics | No | No | No | External controls later | GAP |
| ExecutionPlan / stage splitting | Yes | Yes | No real Fabric backend | N/A | IMPLEMENTED contract |
| Named engine capability profiles | Yes | Yes | Product docs checked; no native run proof | N/A | IMPLEMENTED contract |
| Dataflow Gen2 incremental capture -> framework SCD1 plan | Yes | Yes at planner/reference level | No real Dataflow run yet | Connection/identity external | IMPLEMENTED contract; Fabric proof pending |
| Copy Job native capture delegation | Contract/profile only | Validation tests | No hardening-branch native run | Source support/identity external | PARTIAL |
| CaptureReceipt | Yes | Yes | No real native receipt ingestion yet | N/A | IMPLEMENTED contract |
| Extension registry/logical names | Yes | Yes | No Fabric runtime entry-point proof | Package supply chain external/shared | IMPLEMENTED contract |
| Metadata-driven dispatcher/failure isolation | Yes | Yes | No real Fabric pipeline backend | Capacity policy external | IMPLEMENTED reference |
| Control-plane schema v2 | Yes | Yes on SQLAlchemy/SQLite | No approved persistent Fabric/relational store | DB identity/backup external | IMPLEMENTED schema contract only |
| Retry attempt lineage | Partial run-mode vocabulary only | No end-to-end retry certification | No | Operator policy external | P0 GAP |
| BACKFILL | Contract vocabulary only | No | No | Operator approval external | P0 GAP |
| REPLAY/quarantine replay | Schema concepts only | No end-to-end replay | No | Retention/access external | P0 GAP |
| FULL_REBUILD | Contract vocabulary only | No | No | Approval/recovery external | GAP |
| Unknown target-commit recovery | Design only | No | No | Incident process external | P0 GAP |
| CDC normalization/order/event identity | No complete implementation | No | No | Source CDC enablement external | P0 GAP |
| Snapshot -> CDC bootstrap handoff | No | No | No | Source capability external | P0 GAP |
| Schema evolution compatibility | Schema-change table/design only | No complete certification | No | Governance external | P0 GAP |
| General late/out-of-order policy | SCD1/SCD2 slices only | Partial | No | N/A | PARTIAL |
| Fabric Pipeline adapter | Design only | No | No | Workspace permission external | P0 GAP |
| Fabric Copy Activity adapter | Design/profile only | No native run | No | Connection/gateway external | P0 GAP |
| Fabric Copy Job adapter | Design/profile only | No native run | No | Connector/CDC configuration external | P0 GAP |
| Dataflow Gen2 adapter | Named profile/planner path only | Planner tests | No native run | Connection/gateway external | P0 GAP |
| Spark Job Definition/Environment adapter | Design only | No real SJD run | No | Environment/workspace identity external | P0 GAP |
| Persistent operator query/status surface | No production adapter | Reference lists only | No | Monitoring integration external | GAP |
| Immutable wheel/release path | Yes | GitHub CI/release proven for v0.3.0 | GitHub evidence, not Fabric runtime | Repository governance external | IMPLEMENTED delivery baseline |

## 4. Framework-first semantic guarantee

Accepted ADR 0009 establishes:

> Native Fabric features are capability-certified stage delegates. They do not replace the requirement for framework-owned portable semantics for core mature Data Engineering patterns.

Canonical lifecycle:

```text
capture / movement
    -> normalize / transform
    -> apply
    -> reconcile
    -> state / audit
```

A different executor may own each stage.

Example:

```text
Dataflow Gen2 incremental bucket refresh
    -> Bronze/staging
    -> CaptureReceipt
    -> framework SCD1
    -> reconciliation
    -> framework audit/state contract
```

This is intentionally supported even though Dataflow Gen2's native incremental destination behavior is bucket replacement rather than generic SCD1.

Native apply delegation is future work and must require an explicit certified capability profile for semantic equivalence.

## 5. Current strongest portable guarantees

### 5.1 Metadata and execution safety

- strict Pydantic metadata (`extra=forbid`, immutable models);
- capture/apply strategies are separate axes;
- merge/business/watermark requirements validated before execution;
- effective config has deterministic hash;
- semantic fields are not mutable through arbitrary runtime overrides;
- capability profiles fail closed for unsupported engine/semantic combinations;
- custom metadata references logical registered extension names rather than arbitrary executable import expressions.

### 5.2 Source-boundary correctness

- composite watermark `(watermark, tie_breaker...)` prevents same-timestamp loss in framework-owned incremental selection;
- FULL/SNAPSHOT completeness is explicit evidence rather than inferred from a successful iterator;
- native/external captures have a typed `CaptureReceipt` boundary;
- exactly one authority owns physical capture progress.

### 5.3 Destructive-load protection

FULL replacement includes guards against incomplete/empty/drastically smaller candidates before live publication.

Snapshot diff includes:

- complete-snapshot requirement before absence can mean deletion;
- null/duplicate merge-key protection;
- quarantine-aware delete blocking;
- delete-all and delete-fraction guardrails;
- reconciliation before publication.

### 5.4 Current-state/history semantics

SCD1 reference implementation now proves:

- composite merge keys;
- ordered event/version/sequence tuple support;
- latest-row selection within a batch;
- exact rerun idempotency;
- stale-row ignore/error policy;
- equal-position conflicting payload failure;
- separate duplicate, stale and superseded metrics;
- fail-closed changed update without ordering unless explicitly authorized.

SCD2 reference implementation proves deterministic current/history behavior, one-current-row invariant and conflict/late-arrival handling for its certified scope.

### 5.5 Failure isolation

Dispatcher reference behavior proves:

- enabled/group/request selection;
- dependency validation/cycle detection;
- bounded concurrency;
- per-dataset exception isolation;
- dependent `BLOCKED` behavior;
- unrelated sibling continuation;
- criticality-aware `SUCCESS/PARTIAL_SUCCESS/FAILED` aggregation.

## 6. P0 gaps before the next public release

Do not release solely because the current reference suite is green.

Priority gaps:

1. **UPSERT** — ordered/idempotent current-state merge with duplicate/equal-position/stale semantics aligned with SCD1 foundations.
2. **Explicit apply executor/delegation** — capture/movement engine and apply executor must be separate planning decisions; native final apply only with certified equivalence.
3. **Recovery** — attempt lineage, retryability, RETRY/BACKFILL/REPLAY/FULL_REBUILD and unknown-commit recovery.
4. **CDC** — normalized I/U/D envelope, event identity/order, duplicate/conflict rules, poison-event handling, checkpoint commit and bootstrap-to-CDC handoff.
5. **Schema evolution** — additive/breaking classification, type compatibility and run/audit disposition.
6. **APPEND** — append-once identity and conflicting duplicate policy.
7. **Real control plane** — persistent supported store/repository, migration behavior and operator queries.
8. **Fabric adapters** — Pipeline, Copy Activity, Copy Job, Dataflow Gen2, Spark Job Definition/Environment and native run correlation.
9. **Real hybrid Fabric proof** — at least one `native capture -> CaptureReceipt -> framework apply` DEV execution, preferably Dataflow Gen2/Copy + SCD1/UPSERT.

## 7. External evidence that this repository must not fake

The following remain enterprise/platform responsibilities or joint integration evidence:

- Fabric capacity/SKU and throttling policy;
- tenant settings;
- workspace/domain creation;
- Entra groups, service principals, workspace identity and RBAC;
- gateway/private endpoint/network configuration;
- secrets/key authority;
- source database CDC enablement/retention;
- production target backup/restore and retention;
- monitoring receiver, alert routing and on-call ownership;
- audit/quarantine retention/privacy classification;
- approvals/change-management controls where required.

The framework may define integration contracts and required evidence but must not claim these controls exist until an approved estate proves them.

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
