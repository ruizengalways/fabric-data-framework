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
main baseline = 395736a3a400480da5876a43591961c478426314
PR #43
Actions 33255472348
477 tests
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
```

## Core guarantee map

| Guarantee | Canonical owner | Current evidence |
|---|---|---|
| Immutable DatasetConfig/effective config hashing | `config.py` | REFERENCE + CI PROVEN |
| Capture/apply/physical-engine independence | config + ExecutionPlan | REFERENCE + CI PROVEN |
| Exact 14 cheatsheet semantic combinations | `capture/semantic_contracts.py` | REFERENCE + CI PROVEN |
| Legacy CapturePattern compatibility projection | semantic contracts | REFERENCE + CI PROVEN |
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
| Merge failure does not clobber output | CLI router | REFERENCE + CI PROVEN |
| Approved production control-plane runner | approved control-plane runner | IMPLEMENTED + CI PROVEN APPROVED CONTROL-PLANE CERTIFICATION RUNNER CONTRACT |
| Runtime DB URL remains outside retained control-plane evidence | approved control-plane runner | REFERENCE + CI PROVEN GUARDRAIL |
| Approved Pipeline requires item+control-plane PASS prerequisites | approved Pipeline runner | REFERENCE + CI PROVEN GUARDRAIL |
| Approved Pipeline refuses automatic rerun after substantive evidence | approved Pipeline runner | REFERENCE + CI PROVEN GUARDRAIL |
| Approved Pipeline exact release manifest/config bundle validation | approved Pipeline runner | REFERENCE + CI PROVEN |
| Approved Pipeline creates parent audit before remote child | approved Pipeline runner | REFERENCE + CI PROVEN relational handoff |
| Pipeline PASS requires exact durable child DatasetDispatchOutcome | approved Pipeline runner + backend | IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT |
| Provider Completed with missing durable child outcome -> FAIL | Pipeline runner/backend | REFERENCE + CI PROVEN fail-closed |
| Credential-like Pipeline provider exception audit text is redacted | Pipeline backend | REFERENCE + CI PROVEN GUARDRAIL |
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
  history/delete remain SOURCE_DEFINED until payload contract proves stronger semantics
```

An SCD2 target never upgrades source fidelity.

## Progress / commit invariants

```text
provider/native source cursor != framework downstream semantic checkpoint
provider Completed != framework semantic success
unknown target commit -> reconcile -> COMMITTED / NOT_COMMITTED / UNRESOLVED
```

Pipeline specifically:

```text
Fabric Completed
  + exact durable DatasetDispatchOutcome(dataset_run_id)
  + terminal SUCCEEDED
  = eligible for approved Pipeline PASS
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

Approved Pipeline adds:

```text
prerequisite item PASS
prerequisite production control-plane PASS
selected Pipeline check must still be NOT_RUN
release manifest/config bundle identity before execution
production-eligible relational profile
Fabric token + control-plane DB runtime-only values
explicit Pipeline authorization
parent PipelineRunAudit before child execution
exact durable child outcome before PASS
```

## Required real proof not yet complete

| Required proof | Current state | Next proof |
|---|---|---|
| Enterprise Fabric identity/token | runner contracts only | approved DEV identity run |
| Workspace/item authorization | read-only runner ready | retained live item smoke |
| Fabric SQL DB / Azure SQL production certification | approved runner ready | exact-release PASS + enterprise refs |
| Data Pipeline | approved runner ready | retained live run + native and durable framework correlation |
| Copy Job | transport + evidence builder ready | approved capture runner + retained live job/observation |
| Spark Job Definition | transport + evidence builder ready | approved capture runner + retained live job/observation |
| Fabric Warehouse commit/ambiguous failure | provider contract only | real transaction + lost-ack/network drill |
| Production-approved marker absence proof | absent | provider/session-specific certifier evidence |
| Live Kafka coordination | reference adapter/resume only | live broker proof if release scope includes Kafka |
| Live Delta CDF bounded read/retention | adapter contract only | live Lakehouse proof if release scope includes Delta |
| Retroactive SCD2 rewrite | intentionally unsupported | explicit rewrite policy only if product scope requires it |
| Capacity/gateway/throttling/IAM/DR/monitoring/governance | EXTERNAL | retained enterprise controls |
| Complete exact-release evidence bundle | not retained | staged real checks + merge + `--require-certified` |

## Release rule

`0.4.0` remains blocked until exact candidate code/tests/docs agree and the required real evidence is retained. Never upgrade CI/reference evidence to a live-service label without exact-release approved execution proof.

## Update rule

Every new guarantee must have a canonical implementation owner, executable proof, explicit evidence level, gap update and synchronized current-status/readiness/runbook documentation.
