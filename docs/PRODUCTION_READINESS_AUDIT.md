# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit  
Last updated: 2026-08-30

## Evidence model

Keep these levels separate:

```text
1. portable semantic/runtime implementation
2. deterministic CI/reference proof
3. retained real provider/Fabric/database execution evidence
4. external enterprise controls
```

Green CI proves levels 1/2 only. Executable HTTP/SQL/evidence code is not live provider evidence until approved service runs are retained for the exact environment and release hash.

## Current release state

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
current code baseline = 4dfa5e22fd8eab67406ced8af954f2d81ad18321  (PR #51 merge)
latest code CI        = Actions 33283668067
full test baseline    = 525
```

**Release decision: blocked.** The blocker is retained approved real execution/certification and enterprise controls, not another broad provider-neutral abstraction.

## Current assessment

```text
Portable semantic implementation                       STRONG / broad reusable slice
Deterministic CI                                       STRONG for implemented slices
Exact 14 cheatsheet semantic patterns                  IMPLEMENTED + CI PROVEN reference
Bootstrap / apply / CDC semantics                      IMPLEMENTED + CI PROVEN reference
Target-operation CAS + provider-native recovery        IMPLEMENTED + CI PROVEN reference
SQLAlchemy relational control plane                    IMPLEMENTED + CI PROVEN runtime
Fabric Pipeline / Copy / Spark transports              IMPLEMENTED + CI PROVEN contracts
Fabric Warehouse same-transaction commit proof         IMPLEMENTED + CI PROVEN provider contract
Approved evidence harness / merge / runners            IMPLEMENTED + CI PROVEN contracts
Approved Warehouse ambiguous-COMMIT fault drill        IMPLEMENTED + CI PROVEN runner contract
Warehouse session-termination absence certifier        IMPLEMENTED + CI PROVEN provider contract
Real approved DEV Fabric execution                     NOT YET PROVEN
Real production SQL backend                            NOT YET PROVEN
Real ambiguous-COMMIT/network-driver drill             NOT YET PROVEN
Production-approved marker-absence certifier           NOT YET PROVEN
External enterprise controls                           EXTERNAL / NOT YET RETAINED
```

## Latest hardening milestones

```text
PR #32  Actions 33251177339 / 407 tests  approved preflight + item smoke
PR #34  Actions 33253215030 / 419 tests  exact 14 semantic presets
PR #35  Actions 33253394201 / 430 tests  semantic onboarding + CLI
PR #37  Actions 33253581049 / 441 tests  full-baseline -> WATERMARK bootstrap
PR #39  Actions 33253817758 / 455 tests  strict staged evidence merge
PR #41  Actions 33254804867 / 466 tests  approved control-plane certification runner
PR #43  Actions 33255472348 / 477 tests  approved Pipeline runner
PR #45  Actions 33279105627 / 490 tests  approved Copy/Spark capture runner
PR #47  Actions 33279727906 / 501 tests  approved Warehouse commit/recovery runner
PR #49  Actions 33282725576 / 513 tests  approved ambiguous-COMMIT fault drill
PR #51  Actions 33283668067 / 525 tests  session-termination absence certifier contract
```

## Capture/history readiness

All fourteen cheatsheet semantic rows are first-class at semantic/onboarding level. SCD2 never upgrades source fidelity. Full-event claims still require provider ordering/completeness/retention evidence; watermark/current-state patterns remain observed-change fidelity only.

Provider-neutral deterministic bootstrap contracts exist for snapshot -> CDC and full baseline -> WATERMARK. A generic timestamp is not automatically a safe watermark handoff.

## Approved provider readiness

### Pipeline

`integration-pipeline-run` requires item-read PASS + production control-plane certification PASS. Fabric `Completed` is insufficient; the exact durable framework child outcome must be `SUCCEEDED`.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT
```

### Copy Job / Spark

`integration-capture-run` requires exact-release identity and verified post-run observation -> native evidence -> `CaptureReceipt`. Spark WATERMARK/CDC evidence requires a frozen upper bound.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT
```

### Warehouse commit/recovery

Primary commit truth remains:

```text
matching marker -> COMMITTED
marker absent   -> UNRESOLVED
marker absent + independently certified no-late-commit proof -> NOT_COMMITTED
```

PR #47 proves deterministic same-transaction recovery, including simulated framework ACK loss after a successful commit. This is not evidence of a real network/driver fault.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
```

### Warehouse ambiguous-COMMIT drill

PR #49 separates the stronger real-fault claim. PASS requires an actual execution exception plus independent same-fault verification and `COMMITTED -> SUCCEEDED -> SKIP_SUCCEEDED`. Normal return can never PASS. Marker absence remains unresolved.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT
```

CI commit-then-raise doubles are contract evidence only, not proof that Fabric/network/driver actually failed.

## Warehouse session-termination absence readiness

PR #51 implements a Fabric-specific path for proving that an absent marker cannot arrive later. The contract requires exact provider session identity, not a generic query-history lookup:

```text
capture exact connection_id + session_id on target transaction connection
  -> ambiguous execution exception
  -> independent Admin authority observes exact connection/session
  -> open_transaction_count > 0
  -> KILL exact session
  -> exact connection/session no longer observable
  -> read marker again
  -> marker still absent
  -> safe_to_retry=true may support NOT_COMMITTED
```

The following deliberately remain unresolved:

```text
session already disappeared before inspection
no observable open transaction
connection/session identity mismatch
DMV / KILL / post-termination observation failure
session remains observable after KILL
post-KILL marker read failure
marker appears during termination race
```

If the marker appears during termination, commit may have won the race; `NOT_COMMITTED` is forbidden.

The implementation uses both provider `connection_id` and numeric `session_id`; numeric session ID alone is insufficient. Provider/driver failures retain exception type only. Query Insights is secondary correlation only because completed history is eventually visible rather than an immediate no-late-commit guarantee.

Correct label:

```text
IMPLEMENTED + CI PROVEN FABRIC WAREHOUSE SESSION-TERMINATION ABSENCE CERTIFIER CONTRACT
```

Current limitation: this is a provider contract, **not yet an approved runner**. Real use still needs a separately controlled Admin-capable Warehouse connection, explicit session-termination authorization, live validation of the selected driver/session identity path, and retained exact-release proof.

Therefore it is not yet correct to claim `PRODUCTION-APPROVED MARKER-ABSENCE CERTIFIER` or `FABRIC WAREHOUSE PROVEN`.

## Approved evidence sequencing

Implemented CLI stages:

```text
integration-run-preflight
integration-item-smoke-run
integration-control-plane-certify-run
integration-evidence-merge
integration-pipeline-run
integration-capture-run
integration-warehouse-run
integration-warehouse-fault-drill-run
integration-evidence-validate
```

Intended order:

```text
item read PASS
 -> control-plane certification PASS
 -> strict prerequisite merge
 -> Pipeline
 -> Copy/Spark capture
 -> Warehouse commit/recovery
 -> optional real ambiguous-COMMIT fault drill
 -> optional session-termination NOT_COMMITTED recovery drill
 -> exact-release certified evidence bundle
```

The last session-termination stage is not yet wired as an approved CLI surface.

## Real approved-environment gaps

```text
enterprise Entra token acquisition
real workspace/item authorization
real Fabric SQL Database / Azure SQL Database certification PASS
real approved Pipeline execution
real Copy Job + approved observation
real bounded Spark + approved observation
real Fabric Warehouse target+marker transaction
provider-specific live Warehouse COMMIT fault injector
retained real ambiguous Warehouse COMMIT fault-drill PASS
live exact Warehouse connection/session capture
live Admin DMV/KILL/rollback proof
approved runner wiring for session termination with separate Admin credential and authorization
production-approved marker-absence certifier
live Kafka / Delta CDF if release scope includes them
capacity/SKU/throttling/gateway behavior
backup/restore/HA/DR/monitoring/retention/governance controls
complete certified exact-release evidence bundle
```

## Next reusable slice

If live enterprise inputs remain unavailable, next reusable work is **approved session-termination recovery wiring**, not another absence algorithm:

```text
source-controlled Admin DB env-var NAME only
separate Admin engine/credential
separate explicit --allow-warehouse-session-termination authorization
capture exact session binding before target mutation
invoke absence certifier only after an actual ambiguous execution exception
never make KILL default
never reuse ordinary Warehouse/fault authorization as Admin termination permission
```

Operationally, a real fault drill may FAIL its committed-ambiguity claim while session termination safely reconciles the journal to `NOT_COMMITTED`; those are different evidence questions and must remain separate.

## Release gate

`0.4.0` may be considered only when exact candidate code/tests/docs and retained approved evidence agree.

```text
CI PROVEN != FABRIC PROVEN
CI PROVEN != PRODUCTION DB PROVEN
CI fault-drill contract != real ambiguous-COMMIT proof
CI absence-certifier contract != production-approved marker-absence proof
provider contract != approved live service evidence
```
