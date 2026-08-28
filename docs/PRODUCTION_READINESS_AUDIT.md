# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-29

## 1. Evidence model

This audit deliberately separates:

1. **Portable semantic implementation** — reusable framework contract/algorithm.
2. **Deterministic certification** — executable unit/contract/reference proof.
3. **Real Fabric integration evidence** — approved Fabric item/API execution with retained native run correlation.
4. **External enterprise controls** — tenant, Entra, RBAC, networking, gateway, secrets, retention, monitoring, capacity and governance.

A green Python suite proves levels 1/2 only. A typed Fabric adapter does not become level 3 until an actual Fabric run is retained as evidence.

## 2. Current overall assessment

Current unreleased 0.4.0 development line on PR #13:

```text
Portable semantic implementation     STRONG / materially expanded
Deterministic certification           STRONG for implemented slices
Fabric adapter contract coverage      STRONG reference boundary
Real Fabric execution evidence        NOT YET PROVEN for hardening branch
External enterprise controls          EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest green hardening evidence:

```text
commit: a5da06294dfba0c5ae756dcc1d8814931feebec7
GitHub Actions: 33179754372
build-wheel:      SUCCESS
Python 3.11:      SUCCESS
Python 3.13:      SUCCESS
pytest:           139 passed
```

Earlier coherent evidence in the same slice:

```text
b831d465c2f03117c323a0cbd90e22bbf081417c
run 33178765403
123 passed
Fabric capture adapter contract

333d62ed5b06787026ec7f25481f37bed6c44ea1
run 33179523583
137 passed
Recovery relational evidence
```

`v0.3.0` remains the latest public release. **Do not publish v0.4.0 yet.**

## 3. Capability assessment

| Capability | Portable | Deterministic | Real Fabric | Assessment |
|---|---:|---:|---:|---|
| Typed metadata/effective config | Yes | Yes | N/A | IMPLEMENTED |
| Runtime override allow-list/hash | Yes | Yes | N/A | IMPLEMENTED |
| Composite WATERMARK + overlap | Yes | Yes | No current adapter run | IMPLEMENTED portable |
| Bronze lineage | Yes | Yes | No | IMPLEMENTED portable |
| DQ/quarantine/accounting | Yes | Yes | No persistent Fabric quarantine proof | IMPLEMENTED portable |
| FULL -> REPLACE guards | Yes | Yes | No target publication proof | IMPLEMENTED reference |
| SNAPSHOT -> SNAPSHOT_DIFF/delete guards | Yes | Yes | No | IMPLEMENTED reference |
| SCD1 current-state correctness | Yes | Yes | No | IMPLEMENTED reference |
| UPSERT current-state correctness | Yes | Yes | No | IMPLEMENTED reference |
| SCD2 bounded history correctness | Yes | Yes | No | IMPLEMENTED reference |
| Capture/apply executor separation | Yes | Yes | N/A | IMPLEMENTED contract |
| Named engine/profile capability resolver | Yes | Yes | Product-specific real certification pending | IMPLEMENTED contract |
| CaptureReceipt | Yes | Yes | No real native receipt yet | IMPLEMENTED contract |
| Dataflow incremental -> framework SCD1/UPSERT plan | Yes | Yes | No real Dataflow execution | IMPLEMENTED planner contract |
| FabricCaptureRequest/native-run evidence | Yes | Yes | No | IMPLEMENTED adapter contract |
| Copy Job capture adapter | Yes | Yes fake transport | No | ADAPTER CONTRACT ONLY |
| Copy Activity capture adapter | Yes | Yes fake transport | No | ADAPTER CONTRACT ONLY |
| Dataflow Gen2 capture adapter | Yes | Yes fake transport | No | ADAPTER CONTRACT ONLY |
| Spark capture adapter | Yes | Yes fake transport | No | ADAPTER CONTRACT ONLY |
| Native FAILED/CANCELLED/UNKNOWN fail-closed | Yes | Yes | No | IMPLEMENTED adapter contract |
| Bounded source-range evidence match | Yes | Yes | No | IMPLEMENTED adapter contract |
| Metadata dispatcher/failure isolation | Yes | Yes | No Fabric Pipeline backend | IMPLEMENTED reference |
| Recovery failure classification/retry | Yes | Yes | No | IMPLEMENTED reference core |
| Attempt lineage | Yes | Yes | No persistent production DB | IMPLEMENTED reference/schema proof |
| Reprocess request validation/lifecycle | Yes | Yes | No operator surface | IMPLEMENTED reference contract |
| Unknown commit COMMITTED/NOT_COMMITTED/UNRESOLVED behavior | Yes | Yes | No physical target drill | IMPLEMENTED reference core |
| Relational reprocess/attempt evidence | Yes | Yes SQLAlchemy/SQLite | No approved prod store | IMPLEMENTED schema proof |
| Quarantine payload replay | Partial contract only | No full replay | No | GAP |
| FULL_REBUILD execution | Request authorization only | No reset/rebuild execution | No | GAP |
| Native-progress recovery | Generic concepts only | No provider proof | No | GAP |
| CDC normalization/event identity/order | No | No | No | P0 GAP |
| CDC checkpoint commit | No | No | No | P0 GAP |
| Bootstrap -> CDC handoff | No | No | No | P0 GAP |
| APPEND identity semantics | No | No | No | GAP |
| General schema evolution | design/table only | No full policy | No | P0 GAP |
| Persistent production control plane | reference only | SQLite tests | No | GAP |
| Operator status/retry/backfill/replay/rebuild surface | runtime contracts only | No supported surface | No | GAP |
| Fabric Pipeline backend | design only | No | No | P0 GAP |
| Real Fabric REST/SDK/CLI transport | interface only | fake transport only | No | P0 GAP |
| Same-wheel Fabric DEV/UAT/PROD proof | delivery contract only | GitHub release proof v0.3.0 | No | P0 GAP |

## 4. Strongest portable guarantees

### 4.1 Current-state correctness

SCD1 and UPSERT share a canonical current-state primitive proving:

- composite keys;
- ordering by event/version/sequence positions;
- batch latest-record selection;
- exact-rerun idempotency;
- stale policy;
- equal-position conflict failure;
- fail-closed unordered changed update unless explicitly authorized.

### 4.2 Destructive-load protection

FULL and SNAPSHOT paths do not infer successful authoritative source state merely from an iterator/activity completing. Completeness, deletion and publication guards are explicit.

### 4.3 Stage delegation safety

The semantic plan and provider adapter are separate.

```text
ExecutionPlan
    -> provider request
    -> native run evidence
    -> validate evidence
    -> CaptureReceipt
    -> remaining framework semantics
```

The Fabric adapter contract refuses to create a success receipt for unsuccessful/unknown native status, wrong landing, wrong execution kind, wrong snapshot identity or wrong framework-owned source range.

### 4.4 Recovery safety

Automatic retry is opt-in via explicit transient failure classification. Unknown/unclassified exceptions do not retry automatically.

The most important invariant is now executable:

```text
write outcome uncertain
    -> reconcile first
         COMMITTED     => success/no duplicate write
         NOT_COMMITTED => retry may proceed
         UNRESOLVED    => stop
```

This is materially safer than generic retry-on-exception behavior.

## 5. What Recovery does and does not prove

Recovery **core** is implemented and deterministic:

- attempt lineage;
- retry/backoff/exhaustion;
- reprocess request intent/lifecycle;
- unknown commit tri-state resolution;
- environment-local persistence schema.

It does **not** yet prove every physical strategy can reproduce its original source input. Remaining production work includes:

- retained source window/checkpoint per capture family;
- native-progress service replay/resume behavior;
- quarantine payload retrieval and replay;
- FULL_REBUILD physical reset/rebuild;
- persistent transactional repository;
- physical target idempotency/commit-outcome drills.

Therefore the correct assessment is `IMPLEMENTED reference core / PARTIAL end-to-end recovery`, not either “not implemented” or “fully production ready”.

## 6. Fabric adapter evidence boundary

Current Copy Job/Copy Activity/Dataflow/Spark adapters are real framework code, but their transport is an injected protocol and tests use deterministic fake evidence.

They prove interface and correctness boundaries. They do **not** prove:

- authentication;
- tenant/workspace permission;
- API version behavior;
- polling/runtime failure modes;
- gateway/source connection behavior;
- capacity/throttling;
- actual run IDs from Microsoft Fabric.

At least one real approved DEV hybrid execution is required before release confidence increases materially.

## 7. Current P0 work

The next hard correctness area is CDC:

1. canonical I/U/D event envelope;
2. source event identity/order;
3. duplicate/conflicting duplicate rules;
4. poison/invalid event disposition;
5. bounded checkpoint upper coordinate;
6. checkpoint commit after downstream apply + reconciliation;
7. separate certification for `CDC -> UPSERT`, `CDC -> SCD1`, `CDC -> SCD2`;
8. snapshot/bootstrap -> CDC no-gap/no-double-apply handoff.

After CDC, close strategy-specific recovery, schema evolution, APPEND/persistent operator gaps, then execute a real Fabric hybrid proof.

## 8. External evidence this repo must not fake

- Fabric capacity/SKU and throttling policy;
- tenant settings;
- workspace/domain provisioning;
- Entra groups/service principals/workspace identity/RBAC;
- gateway/private networking;
- secrets/key authority;
- source database CDC enablement/retention;
- production backup/restore;
- monitoring receiver/on-call;
- quarantine/audit retention/privacy;
- approvals/change controls where required.

## 9. Release gate

Before a next public release, the exact release head must satisfy:

```text
code == tests == canonical docs == control-plane/release schema contract
```

and the milestone must include real Fabric integration evidence rather than only provider-neutral/fake-transport proof.

Current decision: **release remains blocked**.
