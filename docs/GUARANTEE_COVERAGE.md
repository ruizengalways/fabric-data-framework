# Guarantee Coverage — fabric-data-framework

Status: Canonical implementation-to-evidence map  
Last updated: 2026-08-29

## Evidence vocabulary

- `REFERENCE` — provider-neutral semantic/contract implementation with deterministic tests.
- `ADAPTER CONTRACT` — provider boundary/evidence conversion tested without claiming a real service run.
- `CI PROVEN` — package/static/test/build workflow succeeded.
- `RELEASE PROVEN` — immutable published artifact/checksum evidence for that release.
- `FABRIC PROVEN` / `PRODUCTION DB PROVEN` / equivalent — retained approved real-service evidence for the exact capability/release.
- `EXTERNAL` — enterprise/platform control this repository must not invent.

## Latest coherent CI baseline

```text
main baseline = ad856d864eb5dec35f3c97ec66ca9e920cfa5e28
PR #41
Actions 33254804867
466 tests
Python 3.11 + 3.13 + static + wheel SUCCESS
```

Latest semantic/evidence milestones:

```text
PR #34 / Actions 33253215030 / 419 tests
  exact 14 cheatsheet semantic presets

PR #35 / Actions 33253394201 / 430 tests
  semantic onboarding + CI gate

PR #37 / Actions 33253581049 / 441 tests
  full-baseline -> watermark bootstrap

PR #39 / Actions 33253817758 / 455 tests
  staged integration evidence merge

PR #41 / Actions 33254804867 / 466 tests
  approved production control-plane certification runner
```

## Core guarantee map

| Guarantee | Canonical owner | Current evidence |
|---|---|---|
| Immutable DatasetConfig/effective config hashing | `config.py` | REFERENCE + CI PROVEN |
| Capture/apply/physical-engine independence | config + ExecutionPlan | REFERENCE + CI PROVEN |
| Exact 14 cheatsheet semantic combinations | `capture/semantic_contracts.py` | REFERENCE + CI PROVEN |
| Legacy `CapturePattern` compatibility projection | semantic contracts | REFERENCE + CI PROVEN |
| Semantic onboarding overclaim guardrails | `capture/onboarding.py` | REFERENCE + CI PROVEN |
| `capture-semantic-onboarding-validate --require-all` | CLI | REFERENCE + CI PROVEN |
| Composite WATERMARK + overlap | `watermark.py` | REFERENCE + CI PROVEN |
| Full-baseline -> WATERMARK fenced bootstrap | `capture/bootstrap_watermark.py` | REFERENCE + CI PROVEN |
| Snapshot -> CDC fenced bootstrap | `capture/bootstrap_cdc.py` | REFERENCE + CI PROVEN |
| APPEND append-once identity/replay/conflict | apply append | REFERENCE + CI PROVEN |
| FULL -> REPLACE | full/replace | REFERENCE + CI PROVEN |
| SNAPSHOT_DIFF | snapshot/apply | REFERENCE + CI PROVEN |
| Ordered/idempotent UPSERT/SCD1 | current-state apply | REFERENCE + CI PROVEN |
| Deterministic SCD2 | SCD2 runtime | REFERENCE + CI PROVEN |
| Source-order vs valid-time taxonomy | temporal quality | REFERENCE + CI PROVEN |
| Retroactive history rewrite requirement fails closed | temporal/SCD2 | REFERENCE fail-closed |
| CDC I/U/D order/dedupe/frozen bounds | `capture/cdc.py` | REFERENCE + CI PROVEN |
| CDC -> UPSERT/SCD1/SCD2 | CDC apply modules | REFERENCE + CI PROVEN |
| Durable downstream CDC checkpoint | control-plane IO | REFERENCE + CI PROVEN |
| Replay-stable file manifest | `capture/files.py` | REFERENCE + CI PROVEN |
| API frozen window/cursor/completeness guards | `capture/api.py` | REFERENCE + CI PROVEN |
| Debezium/Kafka normalization/order | CDC adapter | ADAPTER CONTRACT + CI PROVEN |
| Kafka retention-aware resume planning | CDC provider recovery | REFERENCE + CI PROVEN |
| Delta CDF pre/post normalization | Delta adapter | ADAPTER CONTRACT + CI PROVEN |
| Delta CDF bounded commit-version recovery | Delta adapter | REFERENCE + CI PROVEN |
| Typed CaptureReceipt / single progress authority | contracts/capabilities | REFERENCE + CI PROVEN |
| Fabric capture request/evidence boundary | Fabric adapters | ADAPTER CONTRACT + CI PROVEN |
| Copy Job REST transport | Fabric Copy adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Spark Job Definition REST transport | Fabric Spark adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Fabric Data Pipeline backend | Pipeline backend | IMPLEMENTED + CI PROVEN BACKEND |
| Provider `Completed` insufficient for semantic success | adapters/backend | REFERENCE + CI PROVEN |
| Target-operation durable CAS journal | target operations + IO | IMPLEMENTED + CI PROVEN REFERENCE |
| UNKNOWN target outcome tri-state reconciliation | recovery | IMPLEMENTED + CI PROVEN REFERENCE |
| Fabric Warehouse same-transaction marker proof | Warehouse recovery | IMPLEMENTED + CI PROVEN PROVIDER COMMIT CONTRACT |
| SQLAlchemy relational runtime repository | relational repository | IMPLEMENTED + CI PROVEN RELATIONAL RUNTIME |
| Control-plane backend conformance certification | certification module | IMPLEMENTED + CI PROVEN CONTRACT |
| Approved DEV evidence spec/manifest/hash | integration evidence | IMPLEMENTED + CI PROVEN EVIDENCE HARNESS CONTRACT |
| Secret-bearing retained evidence rejection | integration evidence | IMPLEMENTED + CI PROVEN GUARDRAIL |
| Exact-release approved-run preflight | integration runner | IMPLEMENTED + CI PROVEN APPROVED-RUN PREFLIGHT CONTRACT |
| Read-only Fabric item smoke runner | integration checks/runner | IMPLEMENTED + CI PROVEN READ-ONLY RUNNER CONTRACT |
| Staged partial manifest merge | `integration_evidence_merge.py` | IMPLEMENTED + CI PROVEN EVIDENCE MERGE CONTRACT |
| Merge conflict does not silently arbitrate reruns | evidence merge | REFERENCE + CI PROVEN |
| Failed/conflicting merge does not clobber output | CLI router | REFERENCE + CI PROVEN |
| Approved production control-plane runner | `approved_control_plane_runner.py` | IMPLEMENTED + CI PROVEN APPROVED CONTROL-PLANE CERTIFICATION RUNNER CONTRACT |
| Runtime DB URL remains outside retained config/report/manifest | approved control-plane runner | REFERENCE + CI PROVEN GUARDRAIL |
| Explicit control-plane conformance-write authorization | approved control-plane runner/CLI | REFERENCE + CI PROVEN GUARDRAIL |
| Unsafe driver/report text cannot enter retained control-plane evidence | retained evidence safety + runner | REFERENCE + CI PROVEN GUARDRAIL |
| v0.3.0 immutable wheel/checksum | historical release | RELEASE PROVEN for v0.3.0 |

## Capture/history truth guarantees

```text
Current-state watermark / lookback
  history <= OBSERVED_CHANGES
  hard delete visibility = NONE unless another delete signal exists

Watermark + soft delete
  delete correctness depends on tombstone retention/extraction reliability

Net CDC
  history <= BATCH_GRAIN
  collapsed intermediate changes cannot be reconstructed

Recurring complete snapshots
  history <= SNAPSHOT_GRAIN
  changes between snapshots remain unknowable

Full ordered CDC / log / Debezium / Delta CDF
  FULL_EVENT may be claimed only for captured changes under proven ordering/completeness/retention

API / file delivery
  history/delete remain SOURCE_DEFINED until the payload contract proves stronger semantics
```

An SCD2 target never upgrades source fidelity.

## Progress and commit invariants

```text
provider/native source cursor
        !=
framework downstream semantic checkpoint
```

```text
provider success
        !=
framework target commit + reconciliation + state success
```

```text
unknown target commit
  -> reconcile
  -> COMMITTED / NOT_COMMITTED / UNRESOLVED
  -> never blind retry from ambiguity
```

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

Approved control-plane execution adds:

```text
source control stores env-var NAME, not DB URL value
selected evidence check must be CONTROL_PLANE_CERTIFICATION
production-eligible profile required
complete external control references required
conformance writes require explicit authorization
runner never silently migrates schema
raw DB/driver exception text is not retained
report text is safety-checked before write
```

## Required guarantees/evidence not yet complete

| Required proof | Current state | Next proof |
|---|---|---|
| Real enterprise Fabric identity/token path | runner contract only | approved DEV identity run |
| Real workspace/item authorization | read-only runner ready | retained live item smoke |
| Real Fabric SQL DB / Azure SQL runtime | approved runner ready | exact-release production-certified PASS + enterprise refs |
| Real Data Pipeline execution | backend CI only | retained DEV run + framework/native correlation |
| Real Copy Job capture | transport CI only | retained DEV job + post-run observation |
| Real Spark Job Definition capture | transport CI only | retained DEV job + observation |
| Real Fabric Warehouse commit/ambiguous failure | provider contract only | real transaction + lost-ack/network drill |
| Production-approved marker absence proof | absent | provider/session-specific certifier evidence |
| Live Kafka consumer coordination | reference adapter/resume only | live broker proof if release scope includes Kafka |
| Live Delta CDF bounded read/retention | adapter contract only | live Lakehouse proof if release scope includes Delta |
| Retroactive SCD2 rewrite | intentionally unsupported | explicit rewrite policy only if product scope requires it |
| Capacity/gateway/throttling/IAM/DR/monitoring/governance | EXTERNAL | retained enterprise controls |
| Complete exact-release DEV evidence bundle | not yet retained | staged real checks + merge + `--require-certified` |

## Release rule

`0.4.0` remains blocked until:

```text
exact candidate code/tests/docs agree
approved real DEV item/auth evidence is retained
selected real control-plane backend is certified
representative Fabric provider paths are retained with correlation
Warehouse ambiguous-commit drill is complete
required external enterprise controls are referenced
final merged IntegrationEvidenceManifest passes --require-certified
```

Never upgrade CI/reference evidence to a real-service evidence label without retained approved execution evidence for that exact capability and release hash.

## Update rule

Every new guarantee must have:

```text
canonical implementation owner
executable test/proof
explicit evidence level
updated gap statement
synchronized CURRENT_STATUS / readiness / owning runbook docs
```
