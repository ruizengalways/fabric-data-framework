# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-29

## 1. Evidence model

This audit deliberately separates:

1. **Portable semantic implementation** — reusable framework contract/algorithm.
2. **Deterministic certification** — executable unit/contract/reference proof.
3. **Real provider/Fabric integration evidence** — approved real service execution with retained correlation.
4. **External enterprise controls** — tenant, Entra, RBAC, networking, gateway, secrets, retention, monitoring, capacity and governance.

A green Python suite proves levels 1/2 only. A typed provider adapter does not become level 3 until an actual provider/service run is retained as evidence.

## 2. Current overall assessment

Current unreleased 0.4.0 development line on PR #13:

```text
Portable semantic implementation     STRONG / materially expanded
Deterministic certification           STRONG for implemented slices
Provider adapter contract coverage    STRONG for Fabric capture + Debezium/Kafka reference
Real Fabric/Kafka execution evidence  NOT YET PROVEN for hardening branch
External enterprise controls          EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest provider CDC evidence before this docs synchronization:

```text
1087ab9231b9cb638a87bc2f78ef0c1b1fe32beb
GitHub Actions 33219601375
179 passed
Debezium/Kafka envelope + retention-aware resume

ecdca38099a4f21c6f40701dc14889b464c20608
GitHub Actions 33219783325
183 passed
Debezium/Kafka capability profile + provider registry
```

Earlier CDC sequence reached 171 tests through canonical CDC, CDC apply, durable checkpoint and snapshot/bootstrap handoff.

`v0.3.0` remains the latest public release. **Do not publish v0.4.0 yet.**

## 3. Capability assessment

| Capability | Portable/adapter code | Deterministic | Real service | Assessment |
|---|---:|---:|---:|---|
| Typed metadata/effective config | Yes | Yes | N/A | IMPLEMENTED |
| Composite WATERMARK + overlap | Yes | Yes | No current service run | IMPLEMENTED portable |
| Bronze lineage | Yes | Yes | No | IMPLEMENTED portable |
| DQ/quarantine/accounting | Yes | Yes | No persistent production quarantine proof | IMPLEMENTED portable |
| FULL -> REPLACE guards | Yes | Yes | No target publication proof | IMPLEMENTED reference |
| SNAPSHOT -> SNAPSHOT_DIFF/delete guards | Yes | Yes | No | IMPLEMENTED reference |
| SCD1 current-state correctness | Yes | Yes | No | IMPLEMENTED reference |
| UPSERT current-state correctness | Yes | Yes | No | IMPLEMENTED reference |
| SCD2 bounded history correctness | Yes | Yes | No | IMPLEMENTED reference |
| Capture/apply executor separation | Yes | Yes | N/A | IMPLEMENTED contract |
| Named engine/profile capability resolver | Yes | Yes | Product-specific real certification pending | IMPLEMENTED contract |
| CaptureReceipt | Yes | Yes | No real native receipt yet | IMPLEMENTED contract |
| Fabric Copy/Dataflow/Spark capture adapter boundary | Yes | Yes fake transport | No | ADAPTER CONTRACT ONLY |
| Recovery failure classification/retry/attempt lineage | Yes | Yes | No | IMPLEMENTED reference core |
| Unknown commit tri-state behavior | Yes | Yes | No physical target drill | IMPLEMENTED reference core |
| Canonical CDC event/order/dedupe/window | Yes | Yes | No | IMPLEMENTED reference |
| CDC -> UPSERT/SCD1 | Yes | Yes | No | IMPLEMENTED reference |
| CDC -> SCD2 separate source-order/valid-time | Yes | Yes | No | IMPLEMENTED reference |
| Durable CDC apply checkpoint + optimistic concurrency | Yes | Yes SQLAlchemy/SQLite | No approved prod store | IMPLEMENTED reference |
| Snapshot/bootstrap -> CDC no-gap/no-double-apply | Yes | Yes | No real source fence | IMPLEMENTED reference |
| Debezium/Kafka c/u/d envelope normalization | Yes | Yes | No live Kafka/Debezium | ADAPTER CONTRACT |
| Debezium tombstone/snapshot-read policy | Yes | Yes | No live Kafka/Debezium | ADAPTER CONTRACT |
| Debezium/Kafka topic/partition/offset canonical order | Yes | Yes | No live Kafka/Debezium | ADAPTER CONTRACT |
| `EXTERNAL_CDC/debezium_kafka_v1` capability profile | Yes | Yes | N/A | IMPLEMENTED contract |
| Explicit CDC provider registry | Yes | Yes | N/A | IMPLEMENTED contract |
| Kafka retention-aware safe resume planning | Yes | Yes | No live broker seek | IMPLEMENTED reference provider recovery |
| Kafka consumer-group/source-cursor commit coordination | No live transport | No | No | GAP |
| Quarantine payload REPLAY | Request contract only | No full replay | No | P0 GAP |
| FULL_REBUILD execution | Authorization only | No reset/rebuild | No | P0 GAP |
| Remaining native-progress recovery | Partial | Debezium safe resume only | No | GAP |
| APPEND identity semantics | No | No | No | GAP |
| General schema evolution | design/table only | No full policy | No | P0 GAP |
| Persistent production control plane | reference only | SQLite tests | No | GAP |
| Operator status/retry/backfill/replay/rebuild surface | runtime contracts only | No supported surface | No | GAP |
| Fabric Pipeline backend | design only | No | No | P0 GAP |
| Real Fabric REST/SDK/CLI transport | interface only | fake transport only | No | P0 GAP |
| Real Kafka/Debezium transport | adapter/parser only | deterministic records only | No | P0 GAP |
| Same-wheel DEV/UAT/PROD proof | delivery contract only | v0.3.0 release path | No | P0 GAP |

## 4. Strongest portable guarantees

### 4.1 Current-state and history correctness

SCD1/UPSERT share a current-state primitive proving composite keys, ordered positions, exact-rerun idempotency, stale policy and equal-position conflict failure. SCD2 preserves one-current-row history invariants.

CDC adds a provider-neutral source-order layer and deliberately keeps source order separate from SCD2 valid-time.

### 4.2 Destructive-load protection

FULL and SNAPSHOT paths require explicit completeness evidence and publication/delete guards. Successful source iteration alone is not treated as proof of an authoritative empty/complete source.

### 4.3 Stage delegation safety

```text
ExecutionPlan
    -> provider request/evidence
    -> adapter validation
    -> canonical framework evidence
    -> remaining semantic stages
```

Provider execution success alone does not prove full dataset success.

### 4.4 Recovery safety

Automatic retry is conservative. Unknown target mutation is reconciled before retry:

```text
COMMITTED     => converge success / no duplicate write
NOT_COMMITTED => retry may proceed
UNRESOLVED    => stop
```

### 4.5 CDC checkpoint ownership

```text
provider/native source cursor
        !=
framework downstream CDC apply checkpoint
```

This prevents the framework from claiming source progress it does not own.

## 5. Debezium/Kafka provider readiness

The built-in reference adapter proves a bounded provider translation contract:

```text
Debezium Kafka record
    -> validate topic/key/window
    -> map c/u/d
    -> ignore tombstone
    -> reject snapshot r by default
    -> canonical topic:partition + offset
    -> provider-neutral CDC semantic core
```

It also proves recovery-range planning from the **framework applied checkpoint**, not from a possibly-ahead consumer-group cursor.

If Kafka retention has already deleted the next unapplied offset, the framework fails with an explicit retention-gap error rather than silently continuing.

What this does **not** prove:

- Kafka authentication/networking;
- actual broker earliest/latest offset APIs;
- consumer seek/poll/commit behavior;
- Debezium connector configuration;
- database CDC retention/enablement;
- rebalances/source epoch behavior;
- a live end-to-end CDC run.

Therefore the correct label is `ADAPTER CONTRACT + REFERENCE PROVIDER RECOVERY`, not “Kafka integration complete”.

## 6. Recovery remaining scope

Recovery core is implemented, but end-to-end strategy recovery remains partial.

Next required proofs:

1. quarantine REPLAY retrieves retained payload through a governed provider boundary;
2. original quarantine evidence remains immutable;
3. replay marker advances only after successful replay target/reconciliation gate;
4. already-replayed/conflicting replay attempts fail safely or converge idempotently;
5. FULL_REBUILD requires explicit destructive authority and resets/rebuilds target/state safely;
6. Copy/Dataflow/Mirroring/other provider source progress gets strategy-specific recovery proof;
7. real physical target idempotency/unknown-outcome drills.

## 7. Fabric adapter evidence boundary

Current Fabric capture adapters are real framework code with injected transport protocols; deterministic tests use fake evidence.

They prove interface and fail-closed correctness boundaries, not authentication, tenant/workspace permission, API-version behavior, polling, gateway, capacity or real run IDs.

At least one approved DEV hybrid execution is required before release confidence increases materially.

## 8. Current P0 work

Immediate hardening sequence:

1. quarantine REPLAY execution + replay lineage;
2. FULL_REBUILD execution/state-reset semantics;
3. remaining native/provider progress recovery;
4. APPEND identity/collision/replay semantics;
5. schema evolution;
6. file/API capture guardrails;
7. persistent operator/control-plane surface;
8. real Fabric/Kafka transports + DEV execution proof.

Additional CDC provider adapters should only be added when supported product scope requires them; the canonical CDC semantic core should remain unchanged.

## 9. External evidence this repo must not fake

- Fabric capacity/SKU and throttling policy;
- tenant settings;
- workspace/domain provisioning;
- Entra groups/service principals/workspace identity/RBAC;
- gateway/private networking;
- secrets/key authority;
- source database CDC enablement/retention;
- Kafka broker/connector authentication and retention policy;
- production backup/restore;
- monitoring/on-call;
- quarantine/audit retention/privacy;
- approvals/change controls where required.

## 10. Release gate

Before a next public release, the exact release head must satisfy:

```text
code == tests == canonical docs == control-plane/release schema contract
```

and the milestone must include real provider/Fabric integration evidence rather than only provider-neutral/fake-transport proof.

Current decision: **release remains blocked**.
