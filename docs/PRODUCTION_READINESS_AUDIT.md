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
Portable semantic implementation       STRONG / broad core product slice
Deterministic certification             STRONG for implemented slices
Mainstream source onboarding model      IMPLEMENTED reference
Provider adapter contract coverage      Fabric capture + Debezium/Kafka + Delta CDF
Read-only operator diagnostics          IMPLEMENTED reference
Real Fabric/Kafka/Delta execution       NOT YET PROVEN
External enterprise controls            EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest validated `main` implementation:

```text
4b20300c822e16a398342e0cc97da90ee51b035a
GitHub Actions 33238779139
310 tests passed
14-pattern capture catalog + source-controlled onboarding claims + Delta CDF adapter/profile + executable examples
```

Earlier merged hardening baseline:

```text
9b2278822ff4c566051c69180c8ca63b021866e4
main Actions 33225627461
SUCCESS
```

`v0.3.0` remains the latest public release. **Do not publish v0.4.0 yet.**

## Capability assessment

| Capability | Portable/adapter code | Deterministic proof | Real service | Assessment |
|---|---:|---:|---:|---|
| Typed metadata/effective config | Yes | Yes | N/A | IMPLEMENTED |
| 14-pattern capture/source catalog | Yes | Yes | N/A | IMPLEMENTED reference |
| Source-controlled history/delete/Bronze onboarding claims | Yes | Yes | N/A | IMPLEMENTED reference |
| `capture-onboarding-validate --require-all` CI gate | Yes | Yes | N/A | IMPLEMENTED reference |
| Executable checked-in onboarding examples | Yes | Yes | N/A | IMPLEMENTED/CI PROVEN |
| Composite WATERMARK + overlap | Yes | Yes | No | IMPLEMENTED reference |
| Bronze/DQ/quarantine/accounting | Yes | Yes | No prod quarantine store | IMPLEMENTED reference |
| APPEND/FULL->REPLACE/SNAPSHOT_DIFF/UPSERT/SCD1/SCD2 | Yes | Yes | No | IMPLEMENTED reference |
| Shared source-order/event-time taxonomy | Yes | Yes | N/A | IMPLEMENTED reference |
| Retroactive SCD2 history rewrite | No | Fail-closed behavior proven | No | INTENTIONALLY UNSUPPORTED |
| Capture/apply executor separation | Yes | Yes | N/A | IMPLEMENTED contract |
| Capability profiles + progress ownership | Yes | Yes | Real profile proof pending | IMPLEMENTED contract |
| CaptureReceipt | Yes | Yes | No real native receipt | IMPLEMENTED contract |
| Fabric Copy/Activity/Dataflow/Spark capture adapters | Yes | Fake transport | No | ADAPTER CONTRACT ONLY |
| Retry/attempt/unknown-commit recovery | Yes | Yes | No physical drill | IMPLEMENTED reference |
| Quarantine REPLAY / FULL_REBUILD | Yes | Yes | No production target/payload store | IMPLEMENTED reference |
| Canonical CDC + downstream checkpoint | Yes | Yes | No | IMPLEMENTED reference |
| Snapshot/bootstrap -> CDC | Yes | Yes | No real source fence | IMPLEMENTED reference |
| Debezium/Kafka normalization/resume | Yes | Yes | No live broker | ADAPTER/REFERENCE |
| Delta CDF row-change normalization | Yes | Yes | No live Lakehouse CDF read | ADAPTER CONTRACT |
| `SPARK/delta_cdf_v1` profile/registry | Yes | Yes | No live Lakehouse CDF read | IMPLEMENTED contract |
| Schema contract/evolution/evidence | Yes | Yes | No physical target migration | IMPLEMENTED reference |
| Frozen file manifest | Yes | Yes | No storage client | IMPLEMENTED reference |
| API frozen window/pagination | Yes | Yes | No API client | IMPLEMENTED reference |
| Control-plane v2 -> v3 migration | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Typed operator status + JSON CLI | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Durable target-operation idempotency journal | No | No | No | GAP |
| Approved persistent production control plane | Reference only | SQLite tests | No | GAP |
| Fabric Pipeline backend | Design only | No | No | P0 GAP |
| Real Fabric/Kafka/Delta transports | Interfaces/adapters only | No live call | No | P0 GAP |
| Approved DEV hybrid execution | No | No | No | P0 GAP |

## Source-fidelity readiness

The framework has an explicit onboarding layer for the mainstream capture cases that commonly cause production mistakes.

### What is prevented deterministically

- calling a watermark feed full event history;
- claiming hard-delete visibility from a source that exposes no delete signal;
- calling net CDC full row-change history;
- calling daily snapshot history event-grain;
- merging full CDC/CDF events into Bronze while still claiming the append event history was preserved;
- selecting a provider pattern whose coarse `CaptureStrategy` is incompatible;
- using `WATERMARK_LOOKBACK` without an actual overlap window.

### What still depends on external/source evidence

The catalog cannot prove a vendor's API semantics, retention guarantee, file delivery completeness or database CDC configuration. `SOURCE_DEFINED` is deliberately used where the source contract must supply the missing truth.

## Delta Change Data Feed readiness

Current adapter path:

```text
Spark bounded CDF read
  -> DeltaCDFRecord
  -> pair unambiguous update pre/post images
  -> canonical CDCEvent / CDCCheckpoint
  -> framework UPSERT/SCD1/SCD2
  -> reconcile
  -> framework downstream checkpoint commit
```

Current deterministic guarantees:

- `insert`, `delete`, `update_preimage`, `update_postimage` are typed;
- update pre/post images for one key+commit are paired into one canonical UPDATE;
- exact duplicate input is idempotently ignored;
- null/missing keys fail;
- records beyond frozen upper commit fail;
- incomplete upper-bound evidence fails;
- lower committed version supports overlap replay;
- ambiguous multiple same-key logical mutations within one commit fail closed;
- profile is `SPARK/delta_cdf_v1` with `FRAMEWORK` progress ownership.

This does **not** yet prove:

- a real Fabric Lakehouse CDF read;
- CDF enablement/retention in the target workspace;
- authentication/environment binding;
- real version-gap recovery after retention cleanup;
- performance/capacity behavior.

Correct label: `ADAPTER CONTRACT + REFERENCE CHECKPOINT SEMANTICS`, not “Delta CDF production integrated”.

## Strong portable guarantees

### Apply catalog

All six canonical apply strategies have framework-owned reference semantics. APPEND is append-once by explicit identity rather than blind insertion.

### Temporal correctness

Source ordering and event/valid time are separate shared clocks. Strategy code consumes the common comparator while preserving strategy-specific errors/actions.

### Replay-stable source acquisition

WATERMARK/CDC/FULL/SNAPSHOT plus file/API/CDF contracts freeze the source boundary/set needed for deterministic retry/replay.

### Schema safety

Schema changes are checked against a source-controlled versioned contract. Only explicitly certified widening/relaxation is compatible; removal/narrowing/unproven conversion fails closed.

### Recovery and operability

Unknown target mutation is reconciled before retry. Quarantine REPLAY and FULL_REBUILD are explicit audited flows. Typed operator snapshots provide a stable read model across runtime evidence.

## Remaining release-significant gaps

### P0 integration proof

1. actual Fabric/Kafka/Delta transports;
2. Fabric Pipeline backend;
3. approved DEV hybrid execution retaining real native/provider IDs and framework correlation.

### P0/P1 runtime durability

1. durable target-operation idempotency journal/stable operation key;
2. remaining native/provider downstream-failure resume and live Kafka/Delta recovery evidence;
3. selection/certification of a production control-plane store and concurrency/migration governance;
4. authenticated operator mutation workflows if included in release scope.

Additional provider adapters should be added only when supported product scope requires them.

## Control-plane audit

Current reference schema is v3. The capture selection is deliberately a source-controlled onboarding/CI contract and does not add a control-plane v4. If runtime/operator visibility later requires materialization, that should be a deliberate schema decision with migration/evidence rather than an incidental column addition.

## Fabric/provider evidence boundary

Fabric adapters prove request/evidence validation with injected fake transports. Debezium/Kafka and Delta CDF prove provider normalization/reference checkpoint behavior. They do not prove authentication, networking, API versions, polling, Kafka rebalance/commit behavior, Delta retention behavior, capacity or real run IDs.

## External evidence this repo must not fake

Fabric capacity/SKU/throttling, tenant settings, workspace/domain provisioning, Entra/workspace identity/RBAC, gateway/private networking, secret authority, source CDC/CDF enablement/retention, broker/database/API access, backup/restore, monitoring/on-call, privacy/retention and enterprise change controls remain external evidence.

## Release gate

Before the next public release, the exact candidate must satisfy:

```text
code == tests == canonical docs == control-plane/release contract
```

and its product promise must match retained real integration evidence.

Current decision: **release remains blocked. PR #14 is merged as unreleased source-onboarding/provider hardening; the next P0/P1 slice is durable target-operation idempotency.**
