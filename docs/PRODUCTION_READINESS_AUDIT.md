# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-29

## Evidence model

This audit separates four evidence classes:

1. portable semantic implementation;
2. deterministic CI/reference certification;
3. real provider/Fabric integration evidence;
4. external enterprise controls.

Green Python CI proves levels 1/2 only. Adapter-contract tests do not become real service evidence until an approved provider run is retained.

## Current assessment

```text
Portable semantic implementation     STRONG / broad core product slice
Deterministic certification           STRONG for implemented slices
Provider adapter contract coverage    STRONG for Fabric capture + Debezium/Kafka reference
Read-only operator diagnostics        IMPLEMENTED reference
Real Fabric/Kafka execution evidence  NOT YET PROVEN
External enterprise controls          EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest validated implementation:

```text
ae1eb99ab5fa9d7add5a62dda2d7448b6200d240
GitHub Actions 33225341709
268 tests passed
operator snapshot + control-plane-status CLI

1ee22d5828a5f53a3f9050722bdb5b7f7b28de43
GitHub Actions 33225064570
261 tests passed
shared temporal taxonomy wired through current-state/CDC/SCD2
```

`v0.3.0` remains the latest public release. **Do not publish v0.4.0 yet.**

## Capability assessment

| Capability | Portable/adapter code | Deterministic proof | Real service | Assessment |
|---|---:|---:|---:|---|
| Typed metadata/effective config | Yes | Yes | N/A | IMPLEMENTED |
| Composite WATERMARK + overlap | Yes | Yes | No | IMPLEMENTED reference |
| Bronze/DQ/quarantine/accounting | Yes | Yes | No prod quarantine store | IMPLEMENTED reference |
| APPEND | Yes | Yes | No | IMPLEMENTED reference |
| FULL -> REPLACE | Yes | Yes | No | IMPLEMENTED reference |
| SNAPSHOT_DIFF | Yes | Yes | No | IMPLEMENTED reference |
| UPSERT/SCD1/SCD2 | Yes | Yes | No | IMPLEMENTED reference |
| Shared source-order/event-time taxonomy | Yes | Yes | N/A | IMPLEMENTED reference |
| Retroactive SCD2 history rewrite | No | Fail-closed behavior proven | No | INTENTIONALLY UNSUPPORTED |
| Capture/apply executor separation | Yes | Yes | N/A | IMPLEMENTED contract |
| Capability profiles + progress ownership | Yes | Yes | Real profile proof pending | IMPLEMENTED contract |
| CaptureReceipt | Yes | Yes | No real native receipt | IMPLEMENTED contract |
| Fabric Copy/Activity/Dataflow/Spark capture adapters | Yes | Fake transport | No | ADAPTER CONTRACT ONLY |
| Retry/attempt/unknown-commit recovery | Yes | Yes | No physical drill | IMPLEMENTED reference |
| Quarantine REPLAY | Yes | Yes | No prod payload store | IMPLEMENTED reference |
| FULL_REBUILD | Yes | Yes | No physical target | IMPLEMENTED reference |
| Canonical CDC + downstream checkpoint | Yes | Yes | No | IMPLEMENTED reference |
| Snapshot/bootstrap -> CDC | Yes | Yes | No real source fence | IMPLEMENTED reference |
| Debezium/Kafka normalization/resume | Yes | Yes | No live broker | ADAPTER/REFERENCE |
| Schema contract/evolution/evidence | Yes | Yes | No physical target migration | IMPLEMENTED reference |
| Frozen file manifest | Yes | Yes | No storage client | IMPLEMENTED reference |
| API frozen window/pagination | Yes | Yes | No API client | IMPLEMENTED reference |
| Control-plane v2 -> v3 migration | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Typed operator status aggregation | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Operator JSON CLI | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Durable target-operation idempotency journal | No | No | No | GAP |
| Approved persistent production control plane | Reference only | SQLite tests | No | GAP |
| Fabric Pipeline backend | Design only | No | No | P0 GAP |
| Real Fabric/Kafka transports | Interfaces/adapters only | No live call | No | P0 GAP |
| Approved DEV hybrid execution | No | No | No | P0 GAP |

## Strong portable guarantees

### Apply catalog

All six canonical apply strategies have framework-owned reference semantics. APPEND is append-once by explicit identity rather than blind insertion.

### Temporal correctness

Source ordering and event/valid time are now separate shared clocks. `STALE/EQUAL/NEWER` source order is not conflated with `EARLIER/EQUAL/LATER/UNKNOWN` event time. Strategy code consumes the common comparator while preserving strategy-specific errors/actions.

### Replay-stable source acquisition

WATERMARK/CDC/FULL/SNAPSHOT plus file/API contracts freeze the source boundary/set needed for deterministic retry/replay. A changed file version/set or API logical window fails rather than silently changing replay semantics.

### Schema safety

Schema changes are checked against a source-controlled versioned contract. Only explicitly certified widening/relaxation is compatible; removal/narrowing/unproven conversion fails closed.

### Recovery and operability

Unknown target mutation is reconciled before retry. Quarantine REPLAY and FULL_REBUILD are explicit audited flows. The operator snapshot now gives a stable read model across runs, lineage, capture correlation, progress, reconciliation, quarantine, schema and active reprocess intent.

## Remaining release-significant gaps

### P0 integration proof

1. actual Fabric/Kafka transports;
2. Fabric Pipeline backend;
3. approved DEV hybrid execution retaining real native/provider IDs and framework correlation.

### P0/P1 runtime durability

1. durable target-operation idempotency journal/stable operation key;
2. remaining native/provider downstream-failure resume and real Kafka cursor coordination;
3. selection/certification of a production control-plane store and concurrency/migration governance;
4. authenticated operator mutation workflows if included in release scope.

Additional CDC provider adapters should be added only when supported product scope requires them.

## Control-plane audit

Current reference schema is v3:

```text
v1 phase1_initial_control_plane_schema
v2 execution_policy_ordering_capture_receipt_recovery_and_cdc
v3 append_identity_semantics
```

v3 executes a real additive `ALTER TABLE` for an existing v2 `load_policy`.

The read-only operator layer is intentionally above SQLAlchemy Engine and returns typed models rather than raw table rows. That API can survive a future production repository implementation, but current SQLite tests do not certify the final production database technology.

## Fabric/provider evidence boundary

Fabric adapters prove request/evidence validation with injected fake transports. Debezium/Kafka proves provider normalization and reference resume planning. They do not prove authentication, networking, API versions, polling, Kafka rebalance/commit behavior, capacity or real run IDs.

Correct label: `ADAPTER CONTRACT` / `REFERENCE PROVIDER RECOVERY`, not real Fabric/Kafka integration.

## External evidence this repo must not fake

Fabric capacity/SKU/throttling, tenant settings, workspace/domain provisioning, Entra/workspace identity/RBAC, gateway/private networking, secret authority, source CDC enablement/retention, broker/database access, backup/restore, monitoring/on-call, privacy/retention and enterprise change controls remain external evidence.

## Release gate

Before the next public release, the exact candidate must satisfy:

```text
code == tests == canonical docs == control-plane/release contract
```

and its product promise must match retained real integration evidence.

Current decision: **release remains blocked; PR #13 may merge as unreleased mainline hardening once final CI/docs are green.**
