# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-29

## 1. Evidence model

This audit separates four evidence classes:

1. **Portable semantic implementation** — reusable framework contract/algorithm.
2. **Deterministic certification** — executable unit/contract/reference proof.
3. **Real provider/Fabric integration evidence** — approved real service execution with retained correlation.
4. **External enterprise controls** — tenant, Entra, RBAC, networking, gateway, secrets, retention, monitoring, capacity and governance.

Green Python CI proves levels 1/2 only. Adapter-contract tests do not become level 3 until a real provider/service run is retained.

## 2. Current overall assessment

Current unreleased 0.4.0 development line on PR #13:

```text
Portable semantic implementation     STRONG / broad core product slice
Deterministic certification           STRONG for implemented slices
Provider adapter contract coverage    STRONG for Fabric capture + Debezium/Kafka reference
Real Fabric/Kafka execution evidence  NOT YET PROVEN
External enterprise controls          EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest validated implementation evidence:

```text
c326f062ad4e6be5185f17b9e6830946967361ab
GitHub Actions 33224558393
252 tests passed
file/API replay-stable capture guardrails

6eb4ff275ed1aad9092f60f098d2a9272fd06779
GitHub Actions 33223276476
231 tests passed
schema contract/evolution + runtime evidence

2466d6f254b37a1d79a716e8dd95c5dd16d21cf4
GitHub Actions 33222949040
215 tests passed
APPEND + real v2->v3 additive migration proof
```

`v0.3.0` remains the latest public release. **Do not publish v0.4.0 yet.**

## 3. Capability assessment

| Capability | Portable/adapter code | Deterministic proof | Real service | Assessment |
|---|---:|---:|---:|---|
| Typed metadata/effective config | Yes | Yes | N/A | IMPLEMENTED |
| Composite WATERMARK + overlap | Yes | Yes | No | IMPLEMENTED reference |
| Bronze lineage | Yes | Yes | No | IMPLEMENTED reference |
| DQ/quarantine/accounting | Yes | Yes | No prod quarantine store | IMPLEMENTED reference |
| APPEND append-once/replay/conflict semantics | Yes | Yes | No | IMPLEMENTED reference |
| FULL -> REPLACE guards | Yes | Yes | No | IMPLEMENTED reference |
| SNAPSHOT -> SNAPSHOT_DIFF/delete guards | Yes | Yes | No | IMPLEMENTED reference |
| UPSERT/SCD1 current-state correctness | Yes | Yes | No | IMPLEMENTED reference |
| SCD2 bounded history correctness | Yes | Yes | No | IMPLEMENTED reference |
| Capture/apply executor separation | Yes | Yes | N/A | IMPLEMENTED contract |
| Named capability resolver | Yes | Yes | Real profile proof pending | IMPLEMENTED contract |
| CaptureReceipt | Yes | Yes | No real native receipt | IMPLEMENTED contract |
| Fabric Copy/Dataflow/Spark capture adapter boundary | Yes | Fake transport | No | ADAPTER CONTRACT ONLY |
| Retry/attempt/unknown-commit recovery core | Yes | Yes | No physical drill | IMPLEMENTED reference |
| Quarantine REPLAY coordination | Yes | Yes | No governed prod payload store | IMPLEMENTED reference |
| FULL_REBUILD target/state cutover | Yes | Yes | No physical target | IMPLEMENTED reference |
| Canonical CDC event/order/dedupe/window | Yes | Yes | No | IMPLEMENTED reference |
| CDC -> UPSERT/SCD1/SCD2 | Yes | Yes | No | IMPLEMENTED reference |
| Durable CDC apply checkpoint | Yes | SQLite transaction proof | No prod store | IMPLEMENTED reference |
| Snapshot/bootstrap -> CDC | Yes | Yes | No real source fence | IMPLEMENTED reference |
| Debezium/Kafka normalization | Yes | Yes | No live Kafka/Debezium | ADAPTER CONTRACT |
| Kafka retention-aware safe resume | Yes | Yes | No live broker | IMPLEMENTED reference provider recovery |
| Schema contract/fingerprint | Yes | Yes | N/A | IMPLEMENTED reference |
| EXACT/ADDITIVE_ONLY/SAFE_EVOLUTION classification | Yes | Yes | No real target migration | IMPLEMENTED reference |
| Versioned dataset_contract materialization | Yes | Yes | SQLite only | IMPLEMENTED reference |
| Runtime schema_change evidence | Yes | Yes | SQLite only | IMPLEMENTED reference |
| Frozen file manifest/readiness/completeness | Yes | Yes | No storage client | IMPLEMENTED reference |
| API frozen window/cursor/limits/completeness | Yes | Yes | No API client | IMPLEMENTED reference |
| Control-plane v2->v3 additive migration | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Shared cross-strategy temporal taxonomy | No common owner yet | Partial strategy-specific behavior | No | GAP |
| Persistent production control plane | Reference only | SQLite tests | No | GAP |
| Operator query/reprocess surface | Contracts/CLI foundations | Partial | No | GAP |
| Fabric Pipeline backend | Design only | No | No | P0 GAP |
| Real Fabric/Kafka transport | Interfaces/adapters only | No live call | No | P0 GAP |
| Approved DEV hybrid execution | No | No | No | P0 GAP |

## 4. Strongest portable guarantees

### Apply correctness

All six canonical apply strategies now have framework-owned portable behavior. APPEND uses explicit append identity rather than pretending append is an unordered blind insert. Exact replay is idempotent; identity collision with changed business payload fails closed.

### Destructive-load protection

FULL and SNAPSHOT paths require explicit completeness evidence and publication/delete guards. Successful iteration alone is not proof of an authoritative empty source.

### Schema safety

Schema changes are classified against a source-controlled versioned contract. Only explicitly certified widening/relaxation is considered compatible. Removal, narrowing and unproven conversion fail closed. Runtime observation is audited separately from the promotable contract.

### Replay-stable source acquisition

File and API sources now have provider-neutral freeze/evidence contracts:

```text
file discovery -> immutable manifest fingerprint
API bounds/filter -> immutable window fingerprint -> cursor chain
```

Retry/replay cannot silently resolve to a different file version/set or a shifted API window.

### Recovery safety

Unknown target mutation is reconciled before retry:

```text
COMMITTED     => converge success / no duplicate write
NOT_COMMITTED => retry may proceed
UNRESOLVED    => stop
```

Quarantine REPLAY and FULL_REBUILD are explicit audited flows rather than ad hoc reruns.

## 5. Remaining P0/P1 scope

### P0 before release confidence materially increases

1. real Fabric/Kafka transport implementation;
2. Fabric Pipeline backend;
3. at least one approved DEV hybrid execution retaining native/provider IDs and framework correlation;
4. persistent control-plane repository choice or an explicitly bounded release scope proving the supported operator surface;
5. final candidate-head audit/docs/CI.

### P1 correctness/operability hardening

1. shared cross-strategy late/out-of-order taxonomy;
2. remaining Copy/Dataflow/Mirroring/provider-specific downstream-failure resume proofs;
3. durable physical-target idempotency evidence;
4. live Kafka consumer seek/commit coordination;
5. additional CDC provider adapters only where supported product scope requires them;
6. transaction/rebalance/source-epoch policies where required.

Retroactive SCD2 history correction remains intentionally unsupported and must not be inferred from general late-event handling.

## 6. Control-plane audit

Current reference schema is v3:

```text
v1 phase1_initial_control_plane_schema
v2 execution_policy_ordering_capture_receipt_recovery_and_cdc
v3 append_identity_semantics
```

The v3 migration executes a real additive `ALTER TABLE` for an existing v2 `load_policy` rather than relying on SQLAlchemy `create_all()` to alter an existing table.

Promotable schema contract rows are versioned in `dataset_contract`. Runtime observations remain environment-local in `schema_change`.

SQLite proves schema/transaction behavior only; it is not an endorsed production control-plane store.

## 7. Fabric/provider evidence boundary

Current Fabric adapters prove request/evidence validation and fail-closed boundaries using injected fake transports. Debezium/Kafka proves provider envelope normalization and reference resume planning. They do **not** prove authentication, networking, API versions, polling, Kafka rebalance/commit behavior, capacity or real run IDs.

Correct label: `ADAPTER CONTRACT` / `REFERENCE PROVIDER RECOVERY`, not real Fabric/Kafka integration.

## 8. External evidence this repo must not fake

- Fabric capacity/SKU/throttling;
- tenant settings;
- workspace/domain provisioning;
- Entra/workspace identity/RBAC;
- gateway/private networking;
- secrets/key authority;
- source database CDC enablement/retention;
- Kafka broker/connector authentication and retention;
- production backup/restore;
- monitoring/on-call;
- quarantine/audit privacy/retention;
- enterprise approvals/change controls where required.

## 9. Release gate

Before a next public release, the exact release candidate must satisfy:

```text
code == tests == canonical docs == control-plane/release schema contract
```

and the release scope must include real provider/Fabric integration evidence or explicitly narrow the product promise so no unproven integration is implied.

Current decision: **release remains blocked**.
