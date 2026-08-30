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
code baseline = b9187d93015d921614147831da1336b2d91f3e22  (PR #53 merge)
PR #53 head   = d98ca2c9ab48708d13adc88fbe772f232d53f166
Actions       = 33284190041
534 tests
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
PR #53 / 534  approved Warehouse session-termination recovery contract
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
| Copy Job REST transport | Fabric Copy adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Spark Job Definition transport | Fabric Spark adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Fabric Data Pipeline backend | Pipeline backend | IMPLEMENTED + CI PROVEN BACKEND |
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
| Marker absence alone remains UNRESOLVED | target probe | REFERENCE + CI PROVEN fail-closed |
| Simulated framework ACK loss is not real network fault proof | Warehouse evidence model | EXPLICIT EVIDENCE BOUNDARY |
| Real-fault drill is separate evidence kind | integration evidence + fault runner | IMPLEMENTED + CI PROVEN EVIDENCE SEPARATION |
| Fault drill requires actual execution exception | approved fault runner | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT |
| Normal transaction return cannot PASS real-fault drill | approved fault runner | REFERENCE + CI PROVEN false-positive guard |
| Fault identity must match arm/verification | approved fault runner | REFERENCE + CI PROVEN fail-closed |
| Fault injector cannot manufacture NOT_COMMITTED | fault evidence model | EXPLICIT EVIDENCE BOUNDARY |
| Exact Warehouse session identity = connection_id + session_id | session absence module | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Session ID alone is insufficient | session absence module | REFERENCE + CI PROVEN fail-closed |
| Absence proof requires open_transaction_count > 0 | session absence certifier | REFERENCE + CI PROVEN fail-closed |
| Admin DMV lookup filters exact connection + session | SQLAlchemy session authority | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Session termination uses Admin `KILL <validated session_id>` under AUTOCOMMIT | SQLAlchemy session authority | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Exact session must disappear after termination | session absence certifier | REFERENCE + CI PROVEN fail-closed |
| Post-termination marker must be re-read | session absence certifier | IMPLEMENTED + CI PROVEN race guard |
| Marker appearing during termination forbids NOT_COMMITTED | session absence certifier | REFERENCE + CI PROVEN race guard |
| Query Insights is not immediate absence proof | Warehouse evidence model | EXPLICIT EVIDENCE BOUNDARY |
| Separate Admin DB env-var name from ordinary Warehouse path | approved runner config | IMPLEMENTED + CI PROVEN least-privilege guardrail |
| Ordinary and Admin Warehouse env-var names must differ | approved runner config | REFERENCE + CI PROVEN fail-closed |
| Session termination requires run-config opt-in | approved fault runner | IMPLEMENTED + CI PROVEN guardrail |
| Session termination requires separate CLI/runtime authorization | approved fault runner + CLI | IMPLEMENTED + CI PROVEN guardrail |
| Fault-injection authorization never implies KILL permission | approved fault runner + CLI | EXPLICIT AUTHORIZATION BOUNDARY + CI PROVEN |
| Admin credential value not read on COMMITTED path | approved fault runner | IMPLEMENTED + CI PROVEN least-secret-access guardrail |
| Admin credential value read only for verified UNRESOLVED exact-session branch | approved fault runner | IMPLEMENTED + CI PROVEN least-secret-access guardrail |
| Safe absence reconciles UNKNOWN -> NOT_COMMITTED | approved fault runner + absence certifier | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE SESSION-TERMINATION RECOVERY CONTRACT |
| NOT_COMMITTED sets retry eligibility but runner does not auto-reexecute | approved fault runner | IMPLEMENTED + CI PROVEN fail-closed recovery guardrail |
| NOT_COMMITTED recovery cannot PASS committed-fault evidence check | approved fault runner | EXPLICIT EVIDENCE SEPARATION + CI PROVEN |
| Final post-termination plain probe can only recognize positive COMMITTED evidence | approved fault runner | IMPLEMENTED + CI PROVEN race guard |
| Provider/Admin exceptions retained by type only | approved runners + recovery | REFERENCE + CI PROVEN secret-safety guardrail |
| v0.3.0 immutable wheel/checksum | historical release | RELEASE PROVEN for v0.3.0 |

## Warehouse recovery truth table

```text
matching marker
  -> COMMITTED
  -> SUCCEEDED

marker absent, no independent proof
  -> UNRESOLVED
  -> UNKNOWN
  -> no retry

marker absent
+ exact retained connection/session
+ observable open transaction
+ separately authorized Admin KILL
+ exact session disappears
+ post-KILL marker still absent
  -> NOT_COMMITTED
  -> retry eligible
  -> no automatic retry by evidence runner
```

Evidence semantics stay separate:

```text
FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL PASS
    means actual fault + operation COMMITTED + recovered to SUCCEEDED

SAFE_NOT_COMMITTED_AFTER_SESSION_TERMINATION
    means actual verified fault + safe rollback/non-commit proof
    and therefore the committed-fault check remains FAIL
```

## Secret and authorization invariants

```text
source control stores env-var names only
ordinary Warehouse credential != Admin Warehouse credential name
fault injection authorization != session termination authorization
Admin URL value is read only after verified UNRESOLVED exact-session ambiguity
COMMITTED path never reads Admin URL value
raw provider/driver/Admin exception messages are not retained
```

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
| Exact Warehouse session binding | approved wiring ready | live selected-driver proof |
| Admin DMV/KILL rollback chain | approved wiring ready | separately authorized live Admin proof |
| Production-approved marker absence recovery | CI contract only | retained exact-release live recovery evidence |
| Live Kafka coordination | adapter contract only | live broker proof if in release scope |
| Live Delta CDF | adapter contract only | live Lakehouse proof if in release scope |
| Capacity/IAM/network/DR/monitoring/governance | EXTERNAL | retained enterprise controls |
| Complete exact-release evidence bundle | not retained | staged real checks + merge + `--require-certified` |

## Next boundary

The reusable Warehouse recovery surface is now sufficiently broad at CI-contract level. If live inputs are unavailable, do not add another generic recovery mechanism. Next work should prepare exact-candidate evidence inputs or implement a provider-specific live fault injector only once the actual enterprise environment/fault mechanism is known.

## Release rule

`0.4.0` remains blocked until exact candidate code/tests/docs agree and required real evidence is retained.

```text
CI PROVEN != FABRIC PROVEN
CI PROVEN != PRODUCTION DB PROVEN
CI fault contract != real network/driver fault proof
CI session-termination recovery != production-approved Admin/KILL proof
```

## Update rule

Every new guarantee must have a canonical implementation owner, executable proof, explicit evidence level, gap update and synchronized current-status/readiness/runbook documentation.
