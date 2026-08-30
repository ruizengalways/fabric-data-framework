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
code baseline = 4dfa5e22fd8eab67406ced8af954f2d81ad18321  (PR #51 merge)
PR #51 head   = 514de16a84c4756d9511fe773e0912c0acf607be
Actions       = 33283668067
525 tests
Python 3.11 + 3.13 + static + wheel SUCCESS
```

Recent milestones:

```text
PR #34 / 419  exact 14 cheatsheet semantic presets
PR #35 / 430  semantic onboarding + CI gate
PR #37 / 441  full-baseline -> WATERMARK bootstrap
PR #39 / 455  staged integration evidence merge
PR #41 / 466  approved production control-plane certification runner
PR #43 / 477  approved Fabric Pipeline runner
PR #45 / 490  approved Copy Job + Spark capture runner
PR #47 / 501  approved Warehouse commit/recovery runner
PR #49 / 513  approved Warehouse ambiguous-COMMIT fault-drill runner
PR #51 / 525  Warehouse session-termination absence certifier contract
```

## Core guarantee map

| Guarantee | Canonical owner | Current evidence |
|---|---|---|
| Immutable DatasetConfig/effective config hashing | `config.py` | REFERENCE + CI PROVEN |
| Exact 14 cheatsheet semantic combinations | capture semantic contracts | REFERENCE + CI PROVEN |
| Semantic onboarding overclaim guardrails | capture onboarding | REFERENCE + CI PROVEN |
| Full-baseline -> WATERMARK fenced bootstrap | capture bootstrap | REFERENCE + CI PROVEN |
| Snapshot -> CDC fenced bootstrap | capture bootstrap | REFERENCE + CI PROVEN |
| APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF | apply/runtime | REFERENCE + CI PROVEN |
| CDC order/dedupe/checkpoint | CDC modules | REFERENCE + CI PROVEN |
| Debezium/Kafka recovery | CDC adapter | ADAPTER/RECOVERY CONTRACT + CI PROVEN |
| Delta CDF bounded recovery | Delta adapter | ADAPTER/RECOVERY CONTRACT + CI PROVEN |
| Typed CaptureReceipt / single progress authority | contracts/capabilities | REFERENCE + CI PROVEN |
| Copy Job REST transport | Fabric Copy adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Spark Job Definition transport | Fabric Spark adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Fabric Data Pipeline backend | Pipeline backend | IMPLEMENTED + CI PROVEN BACKEND |
| Provider Completed insufficient for semantic success | Pipeline/capture adapters | REFERENCE + CI PROVEN |
| Durable target-operation CAS journal | target operations + IO | IMPLEMENTED + CI PROVEN REFERENCE |
| UNKNOWN tri-state reconciliation | recovery | IMPLEMENTED + CI PROVEN REFERENCE |
| Fabric Warehouse same-transaction marker proof | Warehouse recovery | IMPLEMENTED + CI PROVEN PROVIDER COMMIT CONTRACT |
| SQLAlchemy relational runtime | relational repository | IMPLEMENTED + CI PROVEN RELATIONAL RUNTIME |
| Approved evidence spec/manifest/hash | integration evidence | IMPLEMENTED + CI PROVEN EVIDENCE HARNESS CONTRACT |
| Strict staged evidence merge | integration evidence merge | IMPLEMENTED + CI PROVEN EVIDENCE MERGE CONTRACT |
| Read-only Fabric item smoke | integration runner | IMPLEMENTED + CI PROVEN READ-ONLY RUNNER CONTRACT |
| Approved control-plane certification | approved control-plane runner | IMPLEMENTED + CI PROVEN APPROVED CONTROL-PLANE CERTIFICATION RUNNER CONTRACT |
| Pipeline PASS requires exact durable child outcome | approved Pipeline runner | IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT |
| Capture PASS requires observation -> native evidence -> CaptureReceipt | approved capture runner | IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT |
| Framework owns Warehouse transaction + commit marker | approved Warehouse runner | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT |
| Matching marker reconciles UNKNOWN -> SUCCEEDED | Warehouse runner + target probe | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT |
| Marker absence alone remains UNRESOLVED | target probe | REFERENCE + CI PROVEN fail-closed |
| Provider/driver errors retained by type only | approved runners + target probe | REFERENCE + CI PROVEN secret-safety guardrail |
| Simulated framework ACK loss is not real network fault proof | Warehouse evidence model | EXPLICIT EVIDENCE BOUNDARY |
| Real-fault drill is a separate evidence kind | integration evidence + fault runner | IMPLEMENTED + CI PROVEN EVIDENCE SEPARATION |
| Fault drill requires normal Warehouse PASS prerequisite | approved fault runner | REFERENCE + CI PROVEN GUARDRAIL |
| Fault injection requires exact fingerprinted artifact + separate authorization | fault runner + ReleaseManifest | REFERENCE + CI PROVEN GUARDRAIL |
| Fault drill PASS requires actual observed execution exception | approved fault runner | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT |
| Normal transaction return cannot PASS real-fault drill | approved fault runner | REFERENCE + CI PROVEN false-positive guard |
| Fault identity must match arm/verification | approved fault runner | REFERENCE + CI PROVEN fail-closed |
| Fault drill absent marker remains UNKNOWN/UNRESOLVED | approved fault runner | REFERENCE + CI PROVEN fail-closed |
| Fault injector cannot manufacture NOT_COMMITTED | fault contract | EXPLICIT EVIDENCE BOUNDARY |
| CI commit-then-raise double is not live fault proof | fault evidence model | EXPLICIT EVIDENCE BOUNDARY |
| Exact Warehouse session identity is connection_id + session_id | session absence module | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Session binding capture occurs on exact target connection | session absence module | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Session ID alone is insufficient for absence proof | session absence module | REFERENCE + CI PROVEN fail-closed |
| Session already gone before inspection remains unresolved | session absence certifier | REFERENCE + CI PROVEN fail-closed |
| Absence proof requires open_transaction_count > 0 | session absence certifier | REFERENCE + CI PROVEN fail-closed |
| Admin authority DMV lookup filters exact connection + session | SQLAlchemy session authority | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Session termination uses explicit `KILL <validated session_id>` under AUTOCOMMIT | SQLAlchemy session authority | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| KILL / DMV / post-check errors retain exception type only | session absence certifier | REFERENCE + CI PROVEN secret-safety guardrail |
| Exact session must disappear after termination | session absence certifier | REFERENCE + CI PROVEN fail-closed |
| Post-termination marker must be re-read | session absence certifier | IMPLEMENTED + CI PROVEN race guard |
| Marker appearing during termination forbids NOT_COMMITTED | session absence certifier | REFERENCE + CI PROVEN race guard |
| Query Insights is not immediate absence proof | Warehouse recovery evidence model | EXPLICIT EVIDENCE BOUNDARY |
| Session-termination certifier is not yet an approved runner | evidence model | EXPLICIT EVIDENCE BOUNDARY |
| v0.3.0 immutable wheel/checksum | historical release | RELEASE PROVEN for v0.3.0 |

## Warehouse commit/recovery invariants

```text
provider/native source cursor != framework downstream semantic checkpoint
provider Completed != framework semantic success
unknown target commit -> reconcile -> COMMITTED / NOT_COMMITTED / UNRESOLVED
```

Primary Warehouse truth:

```text
matching same-transaction marker -> COMMITTED
marker absent                     -> UNRESOLVED
```

PR #51 adds one narrow independent no-late-commit branch:

```text
marker initially absent
+ exact connection/session retained
+ exact live session observed with open_transaction_count > 0
+ independent Admin KILL succeeds
+ exact connection/session disappears
+ post-KILL marker re-read remains absent
= safe_to_retry=true may support NOT_COMMITTED
```

This does not change the default: without all of those facts, marker absence stays `UNRESOLVED`.

If the marker appears after termination, commit may have won the race and `NOT_COMMITTED` is forbidden.

## Evidence accumulation invariants

```text
exact spec/environment/domain/framework/release required
NOT_RUN = no evidence for that stage
substantive PASS/FAIL/EXTERNAL_REQUIRED retained unchanged
identical substantive duplicate may collapse
different rerun evidence = conflict
no timestamp/status precedence
source partial manifests remain retained
```

Approved provider stages additionally require explicit authorization and provider-specific semantic evidence before PASS.

## Required real proof not yet complete

| Required proof | Current state | Next proof |
|---|---|---|
| Enterprise Fabric identity/token | runner contracts only | approved DEV identity run |
| Workspace/item authorization | read-only runner ready | retained live item smoke |
| Fabric SQL DB / Azure SQL certification | approved runner ready | exact-release PASS + enterprise refs |
| Data Pipeline | approved runner ready | retained live native + durable framework outcome |
| Copy Job | approved runner ready | live job + observer + verified receipt |
| Spark Job Definition | approved runner ready | bounded live job + observer + verified receipt |
| Fabric Warehouse commit/recovery | approved runner ready | real target+marker transaction + recovery PASS |
| Real ambiguous Warehouse COMMIT fault | approved fault runner ready | live provider-specific injector + retained drill PASS |
| Exact Warehouse session binding | provider contract only | live selected-driver proof |
| Admin DMV/KILL rollback chain | provider contract only | separately authorized approved live run |
| Production-approved marker absence proof | CI contract only | approved runner wiring + live exact-release evidence |
| Live Kafka coordination | adapter contract only | live broker proof if in release scope |
| Live Delta CDF | adapter contract only | live Lakehouse proof if in release scope |
| Capacity/IAM/network/DR/monitoring/governance | EXTERNAL | retained enterprise controls |
| Complete exact-release evidence bundle | not retained | staged real checks + merge + `--require-certified` |

## Next implementation boundary

If live inputs remain unavailable, the next reusable slice is not another absence algorithm. It is approved wiring for the existing PR #51 contract:

```text
separate source-controlled Admin DB URL env-var NAME
separate Admin engine / identity
separate explicit session-termination authorization
exact session capture before target mutation
invoke certifier only after actual ambiguous execution exception
do not make KILL default
do not reuse normal mutation/fault authorization as Admin termination permission
```

A fault drill can legitimately FAIL its `COMMITTED` ambiguity claim while session-termination recovery safely moves operational state to `NOT_COMMITTED`. Evidence status and recovery state are different concepts.

## Release rule

`0.4.0` remains blocked until exact candidate code/tests/docs agree and required real evidence is retained.

```text
CI PROVEN != FABRIC PROVEN
CI PROVEN != PRODUCTION DB PROVEN
CI fault contract != real network/driver fault proof
CI absence certifier != production-approved absence proof
```

## Update rule

Every new guarantee must have a canonical implementation owner, executable proof, explicit evidence level, gap update and synchronized current-status/readiness/runbook documentation.
