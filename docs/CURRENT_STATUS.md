# Current Status — fabric-data-framework

Status: Canonical recovery checkpoint  
Last updated: 2026-08-30

## Release gate

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
latest code baseline = b9187d93015d921614147831da1336b2d91f3e22  (PR #53 merge)
latest full code CI   = Actions 33284190041
full test baseline   = 534
```

**Do not publish `0.4.0` yet.** Exact-release approved real-environment evidence and external enterprise controls remain incomplete.

## Release-significant merged sequence

```text
PR #17  durable target-operation journal / control-plane v4
PR #19  provider-native downstream recovery
PR #21  production control-plane backend certification contract
PR #22  Fabric REST Job Scheduler + Data Pipeline backend
PR #24  SQLAlchemy relational runtime repository
PR #26  concrete Copy Job + Spark Job Definition REST transports
PR #28  Fabric Warehouse same-transaction target commit proof
PR #30  approved DEV integration evidence harness
PR #32  approved-run preflight + read-only item smoke                    407 tests
PR #34  orthogonal cheatsheet semantics + exact 14 presets              419
PR #35  semantic onboarding validation + CLI                            430
PR #37  full-baseline -> WATERMARK bootstrap                            441
PR #39  strict staged integration evidence merge                        455
PR #41  approved production control-plane certification runner          466
PR #43  approved Fabric Pipeline evidence runner                        477
PR #45  approved Copy Job + Spark capture evidence runner               490
PR #47  approved Fabric Warehouse commit/recovery runner                501
PR #49  approved Warehouse ambiguous-COMMIT fault-drill runner          513
PR #51  Fabric Warehouse session-termination absence certifier contract 525
PR #53  approved Warehouse session-termination recovery wiring          534
```

Latest code CI: Actions `33284190041`, Python 3.11 / 3.13 / static / wheel all SUCCESS.

## Governing invariants

```text
capture fidelity <= truthful history fidelity
provider/native cursor != framework downstream semantic checkpoint
provider Completed != framework semantic success
unknown target commit outcome never permits blind re-execution
source-controlled approved-run config stores env-var names, never secret values
mutating approved checks require explicit authorization
contradictory staged reruns are never silently arbitrated
marker absence alone never proves NOT_COMMITTED
simulated framework ACK loss != real driver/network COMMIT disconnect evidence
normal Warehouse transaction return cannot prove the real-fault drill
fault injector != marker-absence certifier
session disappearance alone != rollback proof
fault-drill PASS != NOT_COMMITTED recovery
Admin session termination authorization != fault injection authorization
```

## Semantic / provider coverage

At semantic-contract + onboarding-validation level, all fourteen cheatsheet patterns are first-class and tested. Provider/runtime surfaces include Fabric Pipeline, Copy Job, Spark Job Definition, Warehouse commit proof, SQLAlchemy control plane, Kafka/Debezium and Delta CDF recovery contracts. Passing deterministic tests does not prove a live provider.

Canonical semantic detail: `CHEATSHEET_PATTERN_ALIGNMENT.md`.

## Target-operation recovery

```text
new               -> EXECUTE
SUCCEEDED         -> SKIP_SUCCEEDED
IN_PROGRESS retry -> RECONCILE_REQUIRED
UNKNOWN retry     -> RECONCILE_REQUIRED
NOT_COMMITTED     -> future intentional claim may reopen -> EXECUTE
```

Warehouse primary commit truth:

```text
matching same-transaction marker -> COMMITTED
marker absent                     -> UNRESOLVED
marker absent + independently certified no-late-commit proof -> NOT_COMMITTED
```

### PR #47 — approved Warehouse commit/recovery

Normal deterministic proof:

```text
EXECUTE
 -> target mutation + marker commit
 -> deliberately simulate framework ACK loss
 -> UNKNOWN
 -> marker COMMITTED
 -> SUCCEEDED
 -> later SKIP_SUCCEEDED
```

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
```

### PR #49 — approved ambiguous-COMMIT fault drill

Separate evidence kind:

```text
FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL
```

PASS requires an actual provider/driver exception, verified same fault identity, marker `COMMITTED`, journal `SUCCEEDED`, and later `SKIP_SUCCEEDED`. A normal return can never PASS.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT
```

### PR #51 — session-termination absence certifier

A narrow Fabric-specific no-late-commit proof exists. Safe absence requires:

```text
exact target connection_id + session_id captured before mutation
same exact session observable after ambiguity
open_transaction_count > 0
Admin KILL exact session
same exact connection/session disappears
post-termination marker re-read succeeds
marker remains absent
```

Any uncertainty stays unresolved. Marker appearing during termination forbids `NOT_COMMITTED`.

Correct label:

```text
IMPLEMENTED + CI PROVEN FABRIC WAREHOUSE SESSION-TERMINATION ABSENCE CERTIFIER CONTRACT
```

### PR #53 — approved session-termination recovery wiring

PR #53 integrates PR #51 into `integration-warehouse-fault-drill-run` as an **optional operational recovery path**, without changing the fault-drill PASS meaning.

Source-controlled `ApprovedIntegrationRunnerConfig` now supports:

```text
warehouse_admin_database_url_env_var
```

Rules:

```text
ordinary Warehouse DB env-var name != Admin Warehouse DB env-var name
run config must set enable_session_termination_recovery=true
CLI/runtime must separately set --allow-warehouse-session-termination
--allow-warehouse-fault-injection never grants KILL permission
```

Admin URL value is lazily read only after all of these are known:

```text
execute_atomic actually raised
exact session binding captured
fault disarm succeeded
fault verify succeeded
fault identity matched
initial plain marker probe = UNRESOLVED
journal remains UNKNOWN
```

For the positive commit path:

```text
marker COMMITTED
 -> Admin URL value is not read
 -> Admin authority is not constructed
 -> existing COMMITTED -> SUCCEEDED -> SKIP_SUCCEEDED PASS semantics remain unchanged
```

For safe rollback:

```text
verified unresolved fault
 -> independently authorized exact-session termination certifier
 -> exact session killed / disappears
 -> post-KILL marker remains absent
 -> UNKNOWN -> NOT_COMMITTED
 -> retry_eligible=true
 -> runner does not auto-claim or auto-reexecute
 -> fault-drill check remains FAIL
```

That FAIL is correct: `FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL` proves committed ambiguity recovery. `NOT_COMMITTED` is a different operational recovery conclusion.

If the certifier remains unresolved, the runner performs one final **plain positive marker probe**. It may recognize a marker that appeared during the race; it can never infer absence by itself.

Correct PR #53 label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE SESSION-TERMINATION RECOVERY CONTRACT
```

No real Fabric/Admin/KILL or production-approved marker-absence claim exists yet.

Canonical detail:

```text
APPROVED_WAREHOUSE_FAULT_DRILL.md
FABRIC_WAREHOUSE_SESSION_ABSENCE_CERTIFIER.md
```

## Approved evidence system

Canonical runbooks:

```text
DEV_INTEGRATION_EVIDENCE.md
APPROVED_CONTROL_PLANE_CERTIFICATION.md
APPROVED_PIPELINE_EVIDENCE.md
APPROVED_CAPTURE_EVIDENCE.md
APPROVED_WAREHOUSE_EVIDENCE.md
APPROVED_WAREHOUSE_FAULT_DRILL.md
FABRIC_WAREHOUSE_SESSION_ABSENCE_CERTIFIER.md
INTEGRATION_EVIDENCE_MERGE.md
```

Strict staged merge remains fail closed:

```text
NOT_RUN = absence
one substantive result = retain unchanged
identical substantive duplicate = allowed
different substantive rerun evidence = conflict
no latest/PASS-wins/FAIL-wins arbitration
```

## Still unproven in approved infrastructure

```text
enterprise Entra token acquisition
real workspace/item authorization smoke
real Fabric SQL Database / Azure SQL Database certification PASS
real approved Pipeline execution
real Copy Job capture + approved observation
real bounded Spark execution + approved observation
real Fabric Warehouse target+marker transaction
provider-specific live Warehouse COMMIT fault injector
retained real ambiguous-COMMIT/network-driver fault-drill PASS
live exact Warehouse session binding via selected driver
live separate Admin identity / DMV observation / KILL / rollback proof
production-approved marker-absence recovery
live Kafka coordination if release scope includes Kafka
live Delta CDF bounded read/retention if release scope includes Delta
capacity/throttling/gateway behavior
backup/restore/HA/DR/monitoring/retention/governance evidence
complete exact-release approved DEV evidence bundle
```

Never upgrade CI/reference evidence to a live-service label without retained approved execution for the exact release hash.

## Exact next order

When approved enterprise inputs are available:

1. replace placeholder DEV release hash/item UUIDs with exact candidate values;
2. run real read-only item smoke;
3. run real production control-plane certification;
4. strict-merge prerequisites;
5. run approved Pipeline;
6. run approved Copy Job + bounded Spark capture;
7. run approved Warehouse target+marker recovery;
8. if required, run provider-specific real ambiguous-COMMIT fault drill;
9. if the unresolved branch matters, exercise exact-session termination recovery under a separately controlled Admin authority;
10. merge required evidence and pass `integration-evidence-validate --require-certified`;
11. prove Kafka/Delta live only if part of `0.4.0` public promise;
12. run exact-candidate release audit.

If real inputs remain unavailable, **do not add another Warehouse recovery abstraction**. Commit recovery, real-fault evidence separation, exact-session absence proof, and approved NOT_COMMITTED wiring now exist at CI-contract level. The next reusable work should prepare the exact 0.4.0 evidence candidate or implement a provider-specific live fault injector only when its actual enterprise mechanism is known.

## Repository boundaries

```text
fabric-data-framework  reusable semantics/runtime/transports/evidence/package
fabric-customer        domain/business config + bounded extensions
fabric-infra           optional capacity/workspace/infrastructure lifecycle
```

## Canonical recovery order

For a new conversation, read:

```text
README.md
CURRENT_STATUS.md
CHEATSHEET_PATTERN_ALIGNMENT.md
PRODUCTION_READINESS_AUDIT.md
DEV_INTEGRATION_EVIDENCE.md
APPROVED_CONTROL_PLANE_CERTIFICATION.md
APPROVED_PIPELINE_EVIDENCE.md
APPROVED_CAPTURE_EVIDENCE.md
APPROVED_WAREHOUSE_EVIDENCE.md
APPROVED_WAREHOUSE_FAULT_DRILL.md
FABRIC_WAREHOUSE_SESSION_ABSENCE_CERTIFIER.md
INTEGRATION_EVIDENCE_MERGE.md
GUARANTEE_COVERAGE.md
EXTENSION_MODEL.md
PROJECT_BLUEPRINT.md
PRODUCTION_REQUIREMENTS.md
CAPTURE_PATTERN_CATALOG.md
TARGET_OPERATION_IDEMPOTENCY.md
PROVIDER_NATIVE_RECOVERY.md
FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md
CONTROL_PLANE_CERTIFICATION.md
RELATIONAL_RUNTIME_REPOSITORY.md
FABRIC_PIPELINE_BACKEND.md
FABRIC_CAPTURE_REST_TRANSPORTS.md
EXECUTION_ENGINE_STRATEGY.md
FABRIC_EXECUTION_MODEL.md
CDC_DESIGN.md
CONTROL_PLANE_DESIGN.md
REPOSITORY_STRUCTURE.md
CICD_DESIGN.md
ECOSYSTEM_BLUEPRINT.md
```

If docs disagree with code/tests, inspect implementation and repair docs before continuing.
