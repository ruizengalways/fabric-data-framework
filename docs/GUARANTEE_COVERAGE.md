# Guarantee Coverage — fabric-data-framework

Status: Canonical implementation-to-evidence map  
Last updated: 2026-08-30

## Evidence vocabulary

- `REFERENCE` — provider-neutral semantic/contract implementation with deterministic tests.
- `ADAPTER CONTRACT` — provider boundary/evidence conversion tested without claiming a real service run.
- `CI PROVEN` — package/static/test/build workflow succeeded.
- `RELEASE PROVEN` — immutable published artifact/checksum evidence for that release.
- `FABRIC PROVEN` / `PRODUCTION DB PROVEN` / equivalent — retained approved real-service evidence for the exact capability/release.
- `EXTERNAL` — enterprise/platform control this repository must not invent.

## Latest coherent CI baseline

```text
code baseline = 264c7547b4e70d24f258bdc3962af83d972e967d  (PR #49 merge)
PR #49 head   = 37e3a67208ea0b060a68ca8668695a0416adaeeb
Actions       = 33282725576
513 tests
Python 3.11 + 3.13 + static + wheel SUCCESS
```

Recent milestones:

```text
PR #34 / 419 tests  exact 14 cheatsheet semantic presets
PR #35 / 430 tests  semantic onboarding + CI gate
PR #37 / 441 tests  full-baseline -> watermark bootstrap
PR #39 / 455 tests  staged integration evidence merge
PR #41 / 466 tests  approved production control-plane certification runner
PR #43 / 477 tests  approved Fabric Pipeline evidence runner
PR #45 / 490 tests  approved Copy Job + Spark capture runner
PR #47 / 501 tests  approved Warehouse commit/recovery runner
PR #49 / 513 tests  approved Warehouse ambiguous-COMMIT fault-drill runner
```

## Core guarantee map

| Guarantee | Canonical owner | Current evidence |
|---|---|---|
| Immutable DatasetConfig/effective config hashing | `config.py` | REFERENCE + CI PROVEN |
| Capture/apply/physical-engine independence | config + ExecutionPlan | REFERENCE + CI PROVEN |
| Exact 14 cheatsheet semantic combinations | `capture/semantic_contracts.py` | REFERENCE + CI PROVEN |
| Semantic onboarding overclaim guardrails | `capture/onboarding.py` | REFERENCE + CI PROVEN |
| Composite WATERMARK + lookback | `watermark.py` | REFERENCE + CI PROVEN |
| Full-baseline -> WATERMARK fenced bootstrap | `capture/bootstrap_watermark.py` | REFERENCE + CI PROVEN |
| Snapshot -> CDC fenced bootstrap | `capture/bootstrap_cdc.py` | REFERENCE + CI PROVEN |
| APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF | apply/runtime modules | REFERENCE + CI PROVEN |
| CDC order/dedupe/checkpoint | CDC modules | REFERENCE + CI PROVEN |
| Debezium/Kafka normalization + recovery | CDC adapter | ADAPTER/RECOVERY CONTRACT + CI PROVEN |
| Delta CDF normalization + bounded recovery | Delta adapter | ADAPTER/RECOVERY CONTRACT + CI PROVEN |
| Replay-stable file manifest | `capture/files.py` | REFERENCE + CI PROVEN |
| API frozen window/cursor guards | `capture/api.py` | REFERENCE + CI PROVEN |
| Typed CaptureReceipt / single progress authority | contracts/capabilities | REFERENCE + CI PROVEN |
| Copy Job REST transport | Fabric Copy adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Spark Job Definition REST transport | Fabric Spark adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Fabric Data Pipeline backend | Pipeline backend | IMPLEMENTED + CI PROVEN BACKEND |
| Provider Completed insufficient for semantic success | Pipeline/capture adapters | REFERENCE + CI PROVEN |
| Target-operation durable CAS journal | target operations + IO | IMPLEMENTED + CI PROVEN REFERENCE |
| UNKNOWN target outcome tri-state reconciliation | recovery | IMPLEMENTED + CI PROVEN REFERENCE |
| Fabric Warehouse same-transaction marker proof | Warehouse recovery | IMPLEMENTED + CI PROVEN PROVIDER COMMIT CONTRACT |
| SQLAlchemy relational runtime repository | relational repository | IMPLEMENTED + CI PROVEN RELATIONAL RUNTIME |
| Control-plane backend conformance certification | certification module | IMPLEMENTED + CI PROVEN CONTRACT |
| Approved evidence spec/manifest/hash | integration evidence | IMPLEMENTED + CI PROVEN EVIDENCE HARNESS CONTRACT |
| Secret-bearing retained evidence rejection | integration evidence | IMPLEMENTED + CI PROVEN GUARDRAIL |
| Exact-release approved-run preflight | integration runner | IMPLEMENTED + CI PROVEN PREFLIGHT CONTRACT |
| Read-only Fabric item smoke runner | integration checks/runner | IMPLEMENTED + CI PROVEN READ-ONLY RUNNER CONTRACT |
| Staged partial manifest merge | integration evidence merge | IMPLEMENTED + CI PROVEN EVIDENCE MERGE CONTRACT |
| Contradictory rerun evidence fails closed | evidence merge | REFERENCE + CI PROVEN |
| Approved control-plane runner | approved control-plane runner | IMPLEMENTED + CI PROVEN APPROVED CONTROL-PLANE CERTIFICATION RUNNER CONTRACT |
| Pipeline PASS requires exact durable child outcome | approved Pipeline runner + backend | IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT |
| Provider Completed + missing child outcome -> FAIL | Pipeline runner/backend | REFERENCE + CI PROVEN fail-closed |
| Approved capture requires item+control-plane PASS prerequisites | approved capture runner | REFERENCE + CI PROVEN GUARDRAIL |
| Approved capture refuses automatic rerun after substantive evidence | approved capture runner | REFERENCE + CI PROVEN GUARDRAIL |
| Approved capture exact release/config-bundle validation | approved capture runner | REFERENCE + CI PROVEN |
| Approved capture extension artifact fingerprint required | approved capture runner + ReleaseManifest | REFERENCE + CI PROVEN provenance guardrail |
| Controlled capture observer entry point | extensions + approved capture runner | IMPLEMENTED + CI PROVEN BOUNDED EXTENSION CONTRACT |
| Controlled Spark executionData entry point | extensions + approved capture runner | IMPLEMENTED + CI PROVEN BOUNDED EXTENSION CONTRACT |
| Copy Job native progress rejects framework bounds/parameters | approved capture runner + transport | REFERENCE + CI PROVEN fail-closed |
| Spark WATERMARK/CDC evidence requires frozen upper bound | approved capture runner | REFERENCE + CI PROVEN fail-closed |
| Combined Spark apply/finalize unit cannot masquerade as capture-only proof | approved capture runner | REFERENCE + CI PROVEN fail-closed |
| Capture PASS requires verified observation -> native evidence -> CaptureReceipt | approved capture runner + FabricCaptureAdapter | IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT |
| Provider Completed + observer/receipt mismatch -> FAIL | approved capture runner | REFERENCE + CI PROVEN fail-closed |
| Safe capture report excludes arbitrary provider/observer diagnostics | approved capture runner | REFERENCE + CI PROVEN GUARDRAIL |
| Warehouse approved run requires item+control-plane PASS prerequisites | approved Warehouse runner | REFERENCE + CI PROVEN GUARDRAIL |
| Warehouse selected check must still be NOT_RUN | approved Warehouse runner | REFERENCE + CI PROVEN GUARDRAIL |
| Warehouse exact release/config-bundle validation | approved Warehouse runner | REFERENCE + CI PROVEN |
| Warehouse mutation extension artifact fingerprint required | approved Warehouse runner + ReleaseManifest | REFERENCE + CI PROVEN provenance guardrail |
| Controlled Warehouse mutation entry point | extensions + approved Warehouse runner | IMPLEMENTED + CI PROVEN BOUNDED EXTENSION CONTRACT |
| Framework owns Warehouse transaction + commit marker | approved Warehouse runner + marker store | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT |
| Matching target marker reconciles UNKNOWN -> SUCCEEDED | approved Warehouse runner + target probe | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT |
| Marker absence remains UNRESOLVED | target probe + approved Warehouse runner | REFERENCE + CI PROVEN fail-closed |
| Marker absence alone never authorizes retry | target operation recovery | REFERENCE + CI PROVEN fail-closed |
| Provider/driver exception retained by type only | target probe + approved Warehouse runner | REFERENCE + CI PROVEN secret-safety guardrail |
| Warehouse secondary-correlation exception retains type only | Warehouse target probe | REFERENCE + CI PROVEN secret-safety guardrail |
| Successful deterministic run proves simulated framework ACK-loss recovery | approved Warehouse runner | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT |
| Simulated ACK loss is not claimed as real network/driver COMMIT disconnect | approved Warehouse evidence model | EXPLICIT EVIDENCE BOUNDARY |
| Real-fault drill is a separate evidence kind | integration evidence + fault runner | IMPLEMENTED + CI PROVEN EVIDENCE SEPARATION |
| Fault drill requires normal Warehouse PASS prerequisite | approved fault runner | REFERENCE + CI PROVEN GUARDRAIL |
| Mutation + fault injector artifacts must be exact-release fingerprinted | approved fault runner + ReleaseManifest | REFERENCE + CI PROVEN provenance guardrail |
| Fault injection requires separate explicit authorization | approved fault runner + CLI | REFERENCE + CI PROVEN GUARDRAIL |
| Controlled Warehouse COMMIT fault-injector entry point | extensions + recovery fault contract | IMPLEMENTED + CI PROVEN BOUNDED EXTENSION CONTRACT |
| Fault injector arm/verify identity must correlate | approved fault runner | REFERENCE + CI PROVEN fail-closed |
| Fault drill PASS requires observed execution exception | approved fault runner | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT |
| Normal transaction return can never PASS real-fault drill | approved fault runner | REFERENCE + CI PROVEN false-positive guard |
| Injector `triggered=true` without observed exception cannot PASS | approved fault runner | REFERENCE + CI PROVEN false-positive guard |
| Fault drill matching marker reconciles UNKNOWN -> SUCCEEDED -> SKIP | approved fault runner + target probe | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT |
| Fault drill exception + absent marker remains UNKNOWN/UNRESOLVED | approved fault runner | REFERENCE + CI PROVEN fail-closed |
| Fault injector cannot convert marker absence into NOT_COMMITTED | approved fault contract | EXPLICIT EVIDENCE BOUNDARY |
| CI commit-then-raise double is not real network/driver fault proof | approved fault evidence model | EXPLICIT EVIDENCE BOUNDARY |
| v0.3.0 immutable wheel/checksum | historical release | RELEASE PROVEN for v0.3.0 |

## Capture/history truth ceilings

```text
Current-state watermark / lookback
  history <= OBSERVED_CHANGES
  hard delete visibility = NONE unless another source signal exists

Watermark + soft delete
  delete correctness depends on tombstone retention/extraction reliability

Net CDC
  history <= BATCH_GRAIN
  collapsed intermediate changes cannot be reconstructed

Recurring complete snapshots
  history <= SNAPSHOT_GRAIN

Full ordered CDC / log / Debezium / Delta CDF
  FULL_EVENT only for captured changes under proven ordering/completeness/retention

API / file delivery
  history/delete remain SOURCE_DEFINED until the payload contract proves stronger semantics
```

An SCD2 target never upgrades source fidelity.

## Progress / commit invariants

```text
provider/native source cursor != framework downstream semantic checkpoint
provider Completed != framework semantic success
unknown target commit -> reconcile -> COMMITTED / NOT_COMMITTED / UNRESOLVED
```

Capture specifically:

```text
Fabric Completed
  + provider/item-specific observation
  + verified FabricNativeRunEvidence
  + verified CaptureReceipt
  + exact workspace/item/job/root correlation
  = eligible for approved Copy/Spark PASS
```

Warehouse specifically:

```text
matching same-transaction marker -> COMMITTED
marker absent -> UNRESOLVED
marker absent + independently certified no-late-commit absence proof -> NOT_COMMITTED
```

Approved Warehouse deterministic recovery path:

```text
target+marker commit returns
  -> simulate framework ACK loss
  -> UNKNOWN
  -> marker probe COMMITTED
  -> SUCCEEDED
  -> later SKIP_SUCCEEDED
```

That path proves framework recovery behavior, not occurrence of a real driver/network COMMIT disconnect.

Approved ambiguous-COMMIT fault-drill path:

```text
normal Warehouse evidence already PASS
  -> arm provider-specific fault with durable identity
  -> execute_atomic actually raises
  -> disarm before probe
  -> verify intended fault triggered + identity matches
  -> marker probe COMMITTED
  -> journal SUCCEEDED
  -> later SKIP_SUCCEEDED
  -> eligible for fault-drill PASS
```

A normal return is always fault-drill FAIL. An absent marker remains UNRESOLVED unless an independent absence certifier supplies a separate no-late-commit proof.

## Evidence accumulation invariants

```text
exact spec/environment/domain/framework/release required
NOT_RUN = no evidence for that stage
substantive PASS/FAIL/EXTERNAL_REQUIRED is retained unchanged
identical substantive duplicate may collapse
different rerun evidence = conflict
no timestamp/status precedence
source partial manifests remain retained
```

Approved provider stages add:

```text
item PASS prerequisite
production control-plane PASS prerequisite
selected mutating check still NOT_RUN
exact release/config identity before execution
explicit mutation/fault authorization
provider-specific semantic evidence before PASS
```

## Required real proof not yet complete

| Required proof | Current state | Next proof |
|---|---|---|
| Enterprise Fabric identity/token | runner contracts only | approved DEV identity run |
| Workspace/item authorization | read-only runner ready | retained live item smoke |
| Fabric SQL DB / Azure SQL production certification | approved runner ready | exact-release PASS + enterprise refs |
| Data Pipeline | approved runner ready | retained live run + native/durable framework correlation |
| Copy Job | approved runner ready | retained live job + approved observer + verified receipt |
| Spark Job Definition | approved runner ready | retained bounded live job + approved observer + verified receipt |
| Fabric Warehouse commit/recovery | approved runner ready | retained real target+marker transaction and recovery PASS |
| Real ambiguous Warehouse COMMIT disconnect | approved fault-drill runner ready | provider-specific live injector + retained exact-release approved fault-drill PASS |
| Production-approved marker absence proof | absent | provider/session-specific no-late-commit certifier evidence |
| Live Kafka coordination | reference adapter/resume only | live broker proof if release scope includes Kafka |
| Live Delta CDF bounded read/retention | adapter contract only | live Lakehouse proof if release scope includes Delta |
| Capacity/gateway/throttling/IAM/DR/monitoring/governance | EXTERNAL | retained enterprise controls |
| Complete exact-release evidence bundle | not retained | staged real checks + merge + `--require-certified` |

## Release rule

`0.4.0` remains blocked until exact candidate code/tests/docs agree and the required real evidence is retained. Never upgrade CI/reference evidence to a live-service label without exact-release approved execution proof.

## Update rule

Every new guarantee must have a canonical implementation owner, executable proof, explicit evidence level, gap update and synchronized current-status/readiness/runbook documentation.
