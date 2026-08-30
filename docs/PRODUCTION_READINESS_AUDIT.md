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
current code baseline = b9187d93015d921614147831da1336b2d91f3e22  (PR #53 merge)
latest code CI        = Actions 33284190041
full test baseline    = 534
```

**Release decision: blocked.** The blocker is retained approved real execution/certification and enterprise controls, not another broad provider abstraction.

## Current assessment

```text
Portable semantic implementation                         STRONG / broad reusable slice
Deterministic CI                                         STRONG for implemented slices
Exact 14 cheatsheet semantic patterns                    IMPLEMENTED + CI PROVEN reference
Bootstrap / apply / CDC semantics                        IMPLEMENTED + CI PROVEN reference
Target-operation CAS + provider-native recovery          IMPLEMENTED + CI PROVEN reference
SQLAlchemy relational control plane                      IMPLEMENTED + CI PROVEN runtime
Fabric Pipeline / Copy / Spark transports                IMPLEMENTED + CI PROVEN contracts
Fabric Warehouse same-transaction commit proof           IMPLEMENTED + CI PROVEN provider contract
Approved evidence harness / merge / runners              IMPLEMENTED + CI PROVEN contracts
Approved Warehouse ambiguous-COMMIT fault drill          IMPLEMENTED + CI PROVEN runner contract
Warehouse session-termination absence certifier          IMPLEMENTED + CI PROVEN provider contract
Approved session-termination recovery wiring             IMPLEMENTED + CI PROVEN runner contract
Real approved DEV Fabric execution                       NOT YET PROVEN
Real production SQL backend                              NOT YET PROVEN
Real ambiguous-COMMIT/network-driver drill               NOT YET PROVEN
Production-approved marker-absence recovery              NOT YET PROVEN
External enterprise controls                             EXTERNAL / NOT YET RETAINED
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
PR #51  Actions 33283668067 / 525 tests  session-termination absence certifier
PR #53  Actions 33284190041 / 534 tests  approved session-termination recovery wiring
```

## Capture/history readiness

All fourteen cheatsheet semantic rows are first-class at semantic/onboarding level. SCD2 never upgrades source fidelity. Full-event claims still require provider ordering/completeness/retention evidence. Snapshot -> CDC and full-baseline -> WATERMARK bootstrap contracts are deterministic reference guarantees only until provider boundaries are proven.

## Approved provider readiness

### Pipeline

`integration-pipeline-run` requires item-read PASS + production control-plane certification PASS. Provider `Completed` is insufficient; the exact durable framework child outcome must be `SUCCEEDED`.

```text
IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT
```

### Copy Job / Spark

`integration-capture-run` requires exact-release identity and verified observation -> native evidence -> `CaptureReceipt`. Spark WATERMARK/CDC evidence requires a frozen upper bound.

```text
IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT
```

### Warehouse normal commit/recovery

```text
matching marker -> COMMITTED
marker absent   -> UNRESOLVED
marker absent + independently certified no-late-commit proof -> NOT_COMMITTED
```

PR #47 proves same-transaction target+marker recovery and simulated framework ACK loss. It does not prove a real network/driver fault.

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
```

### Warehouse real-fault evidence

PR #49 separates the stronger claim. PASS requires an actual execution exception, verified same fault identity, `COMMITTED -> SUCCEEDED -> SKIP_SUCCEEDED`. Normal return can never PASS.

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT
```

CI commit-then-raise doubles remain contract evidence only.

## Session-termination recovery readiness

### Provider absence contract — PR #51

Safe `NOT_COMMITTED` evidence requires:

```text
exact connection_id + session_id captured on target connection
same exact session still observable
open_transaction_count > 0
independent Admin KILL exact session
exact connection/session disappears
post-termination marker read succeeds
marker remains absent
```

Session disappearance alone is not rollback proof. Marker appearing in the termination race forbids `NOT_COMMITTED`. Query Insights is secondary only.

```text
IMPLEMENTED + CI PROVEN FABRIC WAREHOUSE SESSION-TERMINATION ABSENCE CERTIFIER CONTRACT
```

### Approved recovery wiring — PR #53

PR #53 makes this optional recovery available inside the approved ambiguous-COMMIT runner under additional gates.

Configuration/authorization separation:

```text
warehouse_database_url_env_var       -> ordinary Warehouse target path
warehouse_admin_database_url_env_var -> Admin session-control path
```

The env-var names must differ. Source control retains names only. The run must also explicitly set:

```text
enable_session_termination_recovery=true
--allow-warehouse-session-termination
```

Fault-injection authorization never implies Admin session-termination permission.

The Admin credential value is not read merely because recovery is configured. It is read only after:

```text
actual execution exception
exact session binding captured
fault disarm succeeded
fault verification succeeded
fault identity matched
initial marker probe UNRESOLVED
journal UNKNOWN
```

If marker proof is already `COMMITTED`, the Admin credential is never read and Admin authority is never constructed.

Safe non-commit outcome:

```text
verified unresolved fault
 -> exact-session termination proof
 -> UNKNOWN -> NOT_COMMITTED
 -> retry_eligible=true
 -> no automatic re-claim/re-execution
 -> FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL remains FAIL
```

This FAIL is correct. The fault-drill check proves a **committed** ambiguous fault. `NOT_COMMITTED` recovery proves a different operational outcome.

If session termination remains unresolved, one final plain marker probe may recognize positive `COMMITTED` evidence that appeared during the race; it cannot infer absence.

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE SESSION-TERMINATION RECOVERY CONTRACT
```

This still does not justify `PRODUCTION-APPROVED MARKER-ABSENCE RECOVERY` or `FABRIC WAREHOUSE PROVEN`.

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

The session-termination recovery branch is opt-in behavior of `integration-warehouse-fault-drill-run`, not a separate evidence kind. It does not turn a `NOT_COMMITTED` operational recovery into a PASS for the committed-fault evidence check.

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
live exact Warehouse session binding with selected driver
live separately controlled Admin identity / DMV / KILL / rollback proof
production-approved marker-absence recovery
live Kafka / Delta CDF if in release scope
capacity/SKU/throttling/gateway behavior
backup/restore/HA/DR/monitoring/retention/governance controls
complete certified exact-release evidence bundle
```

## Next order

When approved real inputs are available:

1. set exact DEV candidate release hash and real item UUIDs;
2. run real item smoke;
3. run real production control-plane certification;
4. strict-merge prerequisites;
5. run approved Pipeline;
6. run approved Copy/Spark capture;
7. run approved Warehouse target+marker recovery;
8. if required, run a provider-specific real ambiguous-COMMIT fault drill;
9. if that real fault remains unresolved and the release requires the branch, exercise exact-session termination recovery under a separately controlled Admin identity;
10. strict-merge all required evidence and pass `--require-certified`;
11. prove Kafka/Delta only if in public scope;
12. perform exact-candidate release audit.

If live inputs are unavailable, do not build another generic Warehouse recovery abstraction. The next useful work is exact-candidate evidence preparation or a provider-specific live fault injector only when the selected enterprise mechanism is known.

## Release gate

`0.4.0` may be considered only when exact candidate code/tests/docs and retained approved evidence agree.

```text
CI PROVEN != FABRIC PROVEN
CI PROVEN != PRODUCTION DB PROVEN
CI fault-drill contract != real ambiguous-COMMIT proof
CI session-recovery contract != production-approved Admin/KILL proof
provider contract != approved live service evidence
```
