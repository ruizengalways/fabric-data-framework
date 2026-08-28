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
CDC portable correctness              STRONG reference core
Real Fabric execution evidence        NOT YET PROVEN for hardening branch
External enterprise controls          EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest coherent CDC evidence:

```text
ccf0fc8950efb1f4d338cadcaf83aac5fd49a7b9 / 33215409341 / 153 passed
canonical CDC + CDC -> UPSERT/SCD1

ed6c13d4fcabe165ef86be2e547d794e15e5375c / 33215708004 / 159 passed
CDC -> SCD2

c41fbd00bb3d3c6bc71e20f958c4ec14106ac33c / 33216133811 / 165 passed
durable CDC checkpoint + optimistic concurrency

465a2c1e9ddf25b0ace2293f578c2c5bb3a653ae / 33216281126 / 171 passed
snapshot/bootstrap -> CDC no-gap/no-double-apply handoff
```

Earlier evidence:

```text
b831d465c2f03117c323a0cbd90e22bbf081417c / 33178765403 / 123 passed
Fabric capture adapter contract

a5da06294dfba0c5ae756dcc1d8814931feebec7 / 33179754372 / 139 passed
Recovery core + hardening
```

`v0.3.0` remains latest public release. **Do not publish v0.4.0 yet.**

## 3. Capability assessment

| Capability | Portable | Deterministic | Real Fabric | Assessment |
|---|---:|---:|---:|---|
| Typed metadata/effective config | Yes | Yes | N/A | IMPLEMENTED |
| Composite WATERMARK + overlap | Yes | Yes | No current adapter run | IMPLEMENTED portable |
| Bronze lineage | Yes | Yes | No | IMPLEMENTED portable |
| DQ/quarantine/accounting | Yes | Yes | No persistent Fabric quarantine proof | IMPLEMENTED portable |
| FULL -> REPLACE guards | Yes | Yes | No target publication proof | IMPLEMENTED reference |
| SNAPSHOT -> SNAPSHOT_DIFF/delete guards | Yes | Yes | No | IMPLEMENTED reference |
| SCD1 current-state correctness | Yes | Yes | No | IMPLEMENTED reference |
| UPSERT current-state correctness | Yes | Yes | No | IMPLEMENTED reference |
| SCD2 bounded history correctness | Yes | Yes | No | IMPLEMENTED reference |
| Capture/apply executor separation | Yes | Yes | N/A | IMPLEMENTED contract |
| Named engine/profile capability resolver | Yes | Yes | product-specific certification pending | IMPLEMENTED contract |
| CaptureReceipt | Yes | Yes | no real native receipt yet | IMPLEMENTED contract |
| Dataflow incremental -> framework SCD1/UPSERT plan | Yes | Yes | no real Dataflow execution | IMPLEMENTED planner contract |
| Copy Job/Copy Activity/Dataflow/Spark capture adapter | Yes | Yes fake transport | No | ADAPTER CONTRACT ONLY |
| Native FAILED/CANCELLED/UNKNOWN fail-closed | Yes | Yes | No | IMPLEMENTED adapter contract |
| Bounded source-range evidence match | Yes | Yes | No | IMPLEMENTED adapter contract |
| Metadata dispatcher/failure isolation | Yes | Yes | no Fabric Pipeline backend | IMPLEMENTED reference |
| Recovery failure classification/retry | Yes | Yes | No | IMPLEMENTED reference core |
| Attempt/reprocess lineage | Yes | Yes | no production DB | IMPLEMENTED reference/schema proof |
| Unknown commit tri-state behavior | Yes | Yes | no physical target drill | IMPLEMENTED reference core |
| Canonical CDC I/U/D event envelope | Yes | Yes | No | IMPLEMENTED reference |
| CDC identity/dedupe/conflict/order | Yes | Yes | No | IMPLEMENTED reference |
| CDC frozen upper/completeness boundary | Yes | Yes | No | IMPLEMENTED reference |
| CDC -> UPSERT/SCD1 | Yes | Yes | No | IMPLEMENTED reference |
| CDC -> SCD2 | Yes | Yes | No | IMPLEMENTED reference |
| CDC source-order vs valid-time separation | Yes | Yes | No | IMPLEMENTED reference |
| Retroactive SCD2 correction | Fail-closed only | Yes | No | PARTIAL by design |
| Durable CDC downstream apply checkpoint | Yes | Yes SQLite | No approved store | IMPLEMENTED schema/transaction reference |
| CDC checkpoint optimistic concurrency | Yes | Yes | No | IMPLEMENTED reference |
| Snapshot/bootstrap -> CDC fenced handoff | Yes | Yes | No | IMPLEMENTED reference |
| Bootstrap repartition/key movement | Fail-closed | Yes | No | NOT YET SUPPORTED |
| Provider CDC envelopes/capability profiles | Core only | No selected built-in mappings yet | No | P0 GAP |
| Provider offset commit/resume after apply failure | Core state model only | No | No | P0 GAP |
| CDC poison-event quarantine/replay | Partial | No end-to-end proof | No | GAP |
| Quarantine payload REPLAY | request contract | No full replay | No | GAP |
| FULL_REBUILD execution | request authorization | No | No | GAP |
| APPEND identity semantics | No | No | No | GAP |
| File manifest freeze | No | No | No | GAP |
| API pagination/window guardrails | No | No | No | GAP |
| General schema evolution | design/table only | No full policy | No | P0 GAP |
| Persistent production control plane | reference only | SQLite tests | No | GAP |
| Operator surface | runtime contracts only | No supported CLI/API | No | GAP |
| Fabric Pipeline backend | design only | No | No | P0 GAP |
| Real Fabric transports | interface only | fake transport only | No | P0 GAP |
| Same-wheel Fabric DEV/UAT/PROD proof | delivery contract only | release proof v0.3.0 | No | P0 GAP |

## 4. Strong portable guarantees

### 4.1 Current-state correctness

SCD1/UPSERT have deterministic batch ordering/idempotency and a separate CDC current-state path with canonical source-position metadata, stale suppression, delete policy and equal-position conflict detection.

### 4.2 Destructive-load protection

FULL and SNAPSHOT paths require explicit completeness/evidence and destructive-operation guards. A successful activity/iterator is not treated as proof of an authoritative empty source.

### 4.3 Stage delegation safety

```text
ExecutionPlan
    -> provider request
    -> native evidence
    -> validate
    -> CaptureReceipt
    -> remaining framework semantics
```

Fabric adapter contracts reject unsuccessful/unknown native status and evidence mismatches.

### 4.4 Recovery safety

```text
write outcome uncertain
    -> reconcile first
         COMMITTED     => success/no duplicate write
         NOT_COMMITTED => retry may proceed
         UNRESOLVED    => stop
```

Automatic retry requires explicit retryable classification.

### 4.5 CDC correctness

Canonical CDC no longer depends on a provider envelope:

- source partition + integer position tuple;
- exact event identity;
- duplicate idempotency/conflict detection;
- frozen upper checkpoint + completeness proof;
- committed-overlap suppression;
- ambiguous ordering fails closed;
- independent target semantics: UPSERT/SCD1/SCD2;
- target/reconciliation-gated downstream checkpoint;
- optimistic checkpoint concurrency;
- snapshot fence handoff with no-gap/no-double-apply proof.

Canonical detail: `docs/CDC_DESIGN.md`.

## 5. What CDC does and does not prove

The current CDC core proves semantic behavior after a provider has supplied canonical positions/events.

It does **not** yet prove:

- a particular Debezium/database/Fabric envelope mapping;
- source connector retention/offset commit behavior;
- transaction atomicity semantics for every provider;
- partition rebalancing/source incarnation transitions;
- actual Copy Job/native CDC behavior;
- real throughput/backpressure;
- poison-event operational replay;
- real Fabric authentication/networking/runtime behavior.

Therefore the correct assessment is `IMPLEMENTED portable CDC core / PARTIAL provider integration`.

## 6. What Recovery does and does not prove

Recovery core is implemented: attempt lineage, bounded retry, request intent/lifecycle and unknown-commit tri-state.

It does not yet prove every physical strategy can reproduce original input. Remaining work includes native/external source resume, quarantine payload retrieval, FULL_REBUILD execution, persistent transactional repository and target commit drills.

## 7. Fabric adapter evidence boundary

Current Copy Job/Copy Activity/Dataflow/Spark adapters are real framework code around an injected transport protocol, but tests use deterministic fake evidence.

They do **not** prove authentication, API version behavior, gateway behavior, throttling, polling/runtime failures, workspace permissions or actual Fabric run IDs.

At least one approved DEV hybrid execution remains a major release gate.

## 8. Current P0 work

CDC semantic core and bootstrap are complete at reference level. Immediate hardening priorities now are:

1. selected provider CDC envelope adapters/capability profiles;
2. provider-specific source-offset resume/commit recovery semantics;
3. quarantine REPLAY and FULL_REBUILD execution;
4. APPEND identity/collision semantics;
5. file/API capture guardrails;
6. general schema-evolution policy;
7. persistent operator/control-plane surface;
8. real Fabric backend/transport proof.

## 9. External evidence this repo must not fake

- Fabric capacity/SKU/throttling;
- tenant settings;
- workspace/domain provisioning;
- Entra groups/service principals/workspace identity/RBAC;
- gateway/private networking;
- secrets/key authority;
- source CDC enablement/retention;
- production backup/restore;
- monitoring/on-call;
- quarantine/audit retention/privacy;
- required approvals/change control.

## 10. Release gate

Before the next public release, the exact release head must satisfy:

```text
code == tests == canonical docs == control-plane/release schema contract
```

and the agreed milestone must include real Fabric integration evidence, not only provider-neutral/fake-transport proof.

Current decision: **release remains blocked**.
