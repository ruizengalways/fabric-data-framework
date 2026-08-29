# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-29

## Evidence model

This audit separates four evidence classes:

1. portable semantic implementation;
2. deterministic CI/reference certification;
3. real provider/Fabric integration evidence;
4. external enterprise controls.

Green Python CI proves levels 1/2 only. Adapter/reference tests do not become real service evidence until an approved provider execution is retained.

## Current assessment

```text
Portable semantic implementation       STRONG / broad core product slice
Deterministic certification             STRONG for implemented slices
Mainstream source onboarding model      IMPLEMENTED reference
Provider adapter contract coverage      Fabric capture + Debezium/Kafka + Delta CDF
Durable target-operation journal        IMPLEMENTED / CI PROVEN reference
Provider-native recovery contracts      IMPLEMENTED / CI PROVEN reference
Read-only operator diagnostics          IMPLEMENTED reference
Production control-plane certification  NOT YET PROVEN
Real Fabric/Kafka/Delta execution       NOT YET PROVEN
External enterprise controls            EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest validated merged implementation:

```text
fd6d5039a5852e32d823b178970816ff292472a2
PR #19 validation: GitHub Actions 33240884208
322 tests passed
Python 3.11 + 3.13 + wheel/static checks green
Kafka cursor coordination + Delta CDF retention-safe resume + target commit-probe contract
```

Earlier durability baseline:

```text
83a27d9350a6018abc272e9afebdef5d660de519
PR #17 validation: GitHub Actions 33240559434
315 tests passed
stable target-operation identity + control-plane v4 CAS journal
```

Earlier capture/onboarding baseline:

```text
4b20300c822e16a398342e0cc97da90ee51b035a
GitHub Actions 33238779139
310 tests passed
14-pattern capture catalog + onboarding claims + Delta CDF adapter/profile
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
| APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF | Yes | Yes | No | IMPLEMENTED reference |
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
| Kafka consumer-group cursor coordination | Yes | Yes | No live broker seek/commit | IMPLEMENTED/CI PROVEN reference |
| Kafka retention-gap detection | Yes | Yes | No live retention drill | IMPLEMENTED/CI PROVEN reference |
| Delta CDF row-change normalization | Yes | Yes | No live Lakehouse CDF read | ADAPTER CONTRACT |
| Delta CDF retention-safe resume planning | Yes | Yes | No live retention drill | IMPLEMENTED/CI PROVEN reference |
| `SPARK/delta_cdf_v1` profile/registry | Yes | Yes | No live Lakehouse CDF read | IMPLEMENTED contract |
| Frozen file manifest | Yes | Yes | No storage client | IMPLEMENTED reference |
| API frozen window/pagination | Yes | Yes | No API client | IMPLEMENTED reference |
| Schema contract/evolution/evidence | Yes | Yes | No physical target migration | IMPLEMENTED reference |
| Control-plane v4 schema/migrations | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Typed operator status + JSON CLI | Yes | Yes | SQLite/reference | IMPLEMENTED reference |
| Durable target-operation semantic key | Yes | Yes | No target-native proof | IMPLEMENTED/CI PROVEN reference |
| Durable target-operation CAS current state | Yes | Yes | SQLite/reference only | IMPLEMENTED/CI PROVEN reference |
| Append-only target-operation event journal | Yes | Yes | SQLite/reference only | IMPLEMENTED/CI PROVEN reference |
| Unknown target outcome blocks blind retry | Yes | Yes | No real provider drill | IMPLEMENTED/CI PROVEN reference |
| Provider-neutral target commit-probe contract | Yes | Yes | No real provider lookup | IMPLEMENTED/CI PROVEN reference |
| Provider probe failure remains `UNRESOLVED` | Yes | Yes | No live failure drill | IMPLEMENTED/CI PROVEN reference |
| Retry only after durable `NOT_COMMITTED` proof | Yes | Yes | No real provider probe | IMPLEMENTED/CI PROVEN reference |
| Approved persistent production control plane | Reference only | SQLite tests | No | P0/P1 GAP |
| Fabric Pipeline backend | Design only | No | No | P0 GAP |
| Real Fabric/Kafka/Delta transports | Interfaces/adapters only | No live call | No | P0 GAP |
| Approved DEV hybrid execution | No | No | No | P0 GAP |

## Source-fidelity readiness

The framework prevents deterministic metadata/semantic overclaims such as:

- calling a watermark feed full event history;
- claiming hard-delete visibility without a delete signal;
- calling net CDC full row-change history;
- calling daily snapshot history event-grain;
- merging full CDC/CDF events into Bronze while still claiming append event history is preserved;
- selecting a provider pattern incompatible with the coarse capture strategy;
- using `WATERMARK_LOOKBACK` without an overlap window.

It cannot prove a vendor API's semantics, file completeness, source CDC configuration or retention guarantee. `SOURCE_DEFINED` remains explicit where external evidence is required.

## Delta CDF readiness

Current reference path:

```text
framework lower version
  -> provider earliest/latest availability evidence
  -> retention-safe bounded resume plan
  -> Spark bounded CDF read
  -> DeltaCDFRecord
  -> canonical CDCEvent / CDCCheckpoint
  -> framework UPSERT/SCD1/SCD2
  -> target-operation journal + reconciliation
  -> framework downstream checkpoint commit
```

Deterministic guarantees now include:

- typed CDF I/D/update-pre/update-post normalization;
- exact duplicate input idempotency;
- frozen upper version enforcement;
- complete-through-upper requirement;
- fail-closed ambiguous within-commit same-key ordering;
- `lower + 1` next-required version semantics;
- `earliest_available > next_required` retention-gap failure;
- empty CDF rows are not misclassified as retention loss without provider availability evidence.

Still not proven: live Fabric Lakehouse CDF reads, actual CDF enablement/retention, authentication/environment binding, provider availability-discovery API, real retention cleanup drill and capacity/performance.

Correct label: `ADAPTER CONTRACT + CI-PROVEN REFERENCE RECOVERY`, not production integrated Delta CDF.

## Kafka / Debezium recovery readiness

Framework checkpoint remains the semantic source of truth; consumer-group offset is transport state only.

Deterministically proven behavior:

```text
framework next required > group cursor  -> group BEHIND -> explicit seek forward
framework next required < group cursor  -> group AHEAD  -> explicit rewind
same                                  -> ALIGNED -> no seek
no group cursor                       -> MISSING -> explicit initialization/seek
```

Provider group commit offsets use Kafka next-to-consume semantics and are exposed separately as values that may be committed **after** target/reconciliation/framework checkpoint success.

Retention safety remains fail closed: if Kafka's earliest available offset is beyond the next unapplied offset, recovery refuses to skip the missing event.

Still not proven: live broker calls, group ownership, rebalance handling, transactional/consumer configuration, authentication/networking and real retention drill.

Correct label: `REFERENCE CURSOR COORDINATION`, not live Kafka integration.

## Target-operation / commit-probe readiness

Canonical runbooks:

```text
docs/TARGET_OPERATION_IDEMPOTENCY.md
docs/PROVIDER_NATIVE_RECOVERY.md
```

The operation journal remains the durable semantic gate. PR #19 adds a provider-neutral read-only `TargetCommitProbe` layer above it.

Probe resolution mapping:

```text
COMMITTED     -> SUCCEEDED
NOT_COMMITTED -> NOT_COMMITTED
UNRESOLVED    -> UNKNOWN
probe raises  -> UNKNOWN + retained error detail
```

Only the next CAS claim after durable `NOT_COMMITTED` may reopen target execution. Provider lookup failure cannot be interpreted as non-commit.

Still not proven: Fabric Warehouse statement/transaction lookup, Delta atomic marker, Spark/native correlation or another real provider mechanism that can prove the exact operation outcome.

Correct label: `IMPLEMENTED + CI PROVEN REFERENCE`, not exactly-once Fabric writes.

## Strong portable guarantees

### Apply and temporal semantics

All six canonical apply strategies have framework-owned reference behavior. APPEND is append-once by explicit identity. Source ordering and event/valid time are separate shared clocks.

### Replay-stable acquisition

WATERMARK/CDC/FULL/SNAPSHOT plus file/API/CDF contracts freeze the source boundary/set needed for deterministic retry/replay.

### Schema safety

Schema changes are checked against source-controlled versioned contracts. Only explicitly certified widening/relaxation is compatible; removal/narrowing/unproven conversion fails closed.

### Recovery and operability

Unknown target mutation is reconciled before retry. The durable operation journal persists semantic identity/outcome state. Kafka/Delta resume contracts prevent external provider progress from silently skipping framework-unapplied data. Quarantine REPLAY and FULL_REBUILD remain explicit audited flows. Typed operator snapshots provide a stable read model.

## Remaining release-significant gaps

### P0/P1 control plane

1. define/select a production control-plane repository implementation;
2. certify its transaction, compare-and-swap, migration and operator-read semantics against the existing reference contracts;
3. retain concurrency/failover evidence; SQLite remains reference-only.

### P0 integration proof

1. actual Fabric/Kafka/Delta transports;
2. Fabric Pipeline backend;
3. provider-specific position discovery and target commit probes wired to live services;
4. approved DEV hybrid execution retaining real native/provider IDs and framework correlation;
5. failure drills for ambiguous target outcome, Kafka cursor drift/retention and Delta CDF retention gap.

Authenticated operator mutation workflows remain optional release-scope work unless required by the product promise.

## Control-plane audit

Current reference schema is v4:

```text
v1 initial control-plane schema
v2 execution policy / ordering / capture receipt / recovery / CDC
v3 append identity semantics
v4 durable target-operation journal
```

Capture selection remains source-controlled onboarding/CI truth rather than runtime state.

Before production release, a persistent control-plane repository must be certified against the same CAS, migration, transaction and operator contracts. SQLite remains the deterministic reference store, not a production deployment claim.

## Fabric/provider evidence boundary

Fabric adapters currently prove request/evidence validation with fake transports. Debezium/Kafka and Delta CDF prove normalization/reference resume semantics. Provider recovery contracts prove safe planning/reconciliation behavior. None prove authentication, networking, API versions, live Kafka rebalance/commit behavior, live Delta retention behavior, capacity, real native run IDs or target-native ambiguous-commit resolution.

## External evidence this repo must not fake

Fabric capacity/SKU/throttling, tenant settings, workspace/domain provisioning, Entra/workspace identity/RBAC, gateway/private networking, secret authority, source CDC/CDF enablement/retention, broker/database/API access, backup/restore, monitoring/on-call, privacy/retention and enterprise change controls remain external evidence.

## Release gate

Before the next public release, the exact candidate must satisfy:

```text
code == tests == canonical docs == control-plane/release contract
```

and its product promise must match retained real integration evidence.

Current decision: **release remains blocked. PR #19 closes the portable/reference provider-recovery contract gap. The next implementation slice is production control-plane repository certification, followed by actual transports/Pipeline backend and retained DEV provider evidence.**
