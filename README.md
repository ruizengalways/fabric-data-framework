# fabric-data-framework

Reusable, versioned Microsoft Fabric Data Engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns reusable data-engineering semantics and operational contracts. Domain repositories consume an immutable framework wheel and normally onboard datasets through source-controlled metadata, environment bindings, capability profiles and bounded logical-name extensions rather than framework edits.

## Release status

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
current code baseline = b9187d93015d921614147831da1336b2d91f3e22  (PR #53 merge)
latest code CI        = Actions 33284190041
full tests            = 534
```

**Do not publish v0.4.0 yet.** The remaining gate is retained exact-release approved real-environment evidence plus required enterprise controls.

## Governing model

```text
source semantic truth
  -> immutable DatasetConfig + semantic onboarding
  -> capability resolver + immutable ExecutionPlan
  -> provider/native capture or orchestration
  -> verified receipt/native evidence or durable framework outcome
  -> normalize / DQ / apply
  -> target-operation commit proof / reconciliation
  -> downstream semantic checkpoint
  -> exact-release retained integration evidence
```

Core rules:

```text
capture fidelity <= truthful history fidelity
provider/native cursor != framework downstream semantic checkpoint
provider Completed != framework semantic success
unknown target commit outcome never permits blind re-execution
marker absence alone never proves NOT_COMMITTED
simulated framework ACK loss != real provider/driver/network COMMIT fault evidence
session disappearance alone != rollback proof
fault-drill PASS != NOT_COMMITTED recovery
```

## Current reusable capability surface

- exact fourteen-row cheatsheet semantic presets and semantic onboarding guardrails;
- full-baseline -> WATERMARK and snapshot -> CDC fenced handoff contracts;
- APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF;
- normalized Bronze lineage, DQ/quarantine/accounting and reconciliation;
- provider-neutral CDC order/dedupe/checkpoint contracts plus Kafka/Debezium and Delta CDF adapter contracts;
- durable target-operation CAS journal and fail-closed unknown-outcome recovery;
- SQLAlchemy relational control-plane repository;
- Fabric REST Pipeline, Copy Job and Spark Job Definition transports/backends;
- Fabric Warehouse same-transaction target-side marker proof;
- approved-run preflight, item smoke, control-plane certification, Pipeline, Copy/Spark capture and Warehouse commit/recovery runners;
- separate approved Warehouse ambiguous-COMMIT fault-drill runner;
- Fabric Warehouse exact-session termination absence-certifier provider contract;
- approved optional session-termination recovery wiring with separate Admin credential/authorization;
- controlled customer extension surfaces and strict staged evidence merge.

These are reference/transport/backend/runner contracts unless retained exact-release real-service evidence explicitly proves more.

## Warehouse recovery evidence ladder

### Normal Warehouse commit/recovery — PR #47

```text
EXECUTE
 -> same transaction: target mutation + framework marker
 -> commit returns
 -> simulated framework ACK loss
 -> UNKNOWN
 -> matching marker COMMITTED
 -> SUCCEEDED
 -> later SKIP_SUCCEEDED
```

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
```

This does not prove an actual network/driver fault.

### Real ambiguous-COMMIT fault drill — PR #49

Separate evidence kind:

```text
FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL
```

PASS requires:

```text
actual provider/driver exception
verified exact injected fault identity
matching marker -> COMMITTED
journal -> SUCCEEDED
later claim -> SKIP_SUCCEEDED
```

A normal transaction return can never PASS.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT
```

### Session-termination absence proof — PR #51

`NOT_COMMITTED` is eligible only when all of these hold:

```text
exact target connection_id + session_id captured before mutation
same exact session remains observable after ambiguity
open_transaction_count > 0
independent Admin authority KILLs that exact session
same exact connection/session disappears
post-termination marker read succeeds
marker remains absent
```

Any missing fact remains fail closed. In particular:

```text
session already disappeared -> UNRESOLVED
no open transaction         -> UNRESOLVED
DMV/KILL/post-check failure -> UNRESOLVED
marker appears in race      -> NOT_COMMITTED forbidden
```

Correct label:

```text
IMPLEMENTED + CI PROVEN FABRIC WAREHOUSE SESSION-TERMINATION ABSENCE CERTIFIER CONTRACT
```

### Approved session-termination recovery wiring — PR #53

PR #53 connects the PR #51 certifier to the approved fault runner while keeping the evidence questions separate.

Source-controlled runner config now supports a third runtime credential **name**:

```text
warehouse_admin_database_url_env_var
```

It must differ from the ordinary Warehouse DB URL env-var name. Session termination also requires both:

```text
fault run config: enable_session_termination_recovery=true
CLI/runtime:       --allow-warehouse-session-termination
```

`--allow-warehouse-fault-injection` never implies `KILL` permission.

The Admin URL value is read only after:

```text
actual execution exception
+ exact session binding captured
+ fault disarmed
+ fault verified
+ fault identity matched
+ first marker probe UNRESOLVED
+ journal UNKNOWN
```

If the primary marker is already `COMMITTED`, Admin credentials are never read and Admin authority is never constructed.

If exact-session termination proves safe absence:

```text
UNKNOWN -> NOT_COMMITTED
retry_eligible = true
no automatic re-claim or re-execution
fault-drill evidence result remains FAIL
```

This is deliberate: the fault drill proves **committed ambiguity recovery**; session termination proves **safe non-commit recovery**. They cannot satisfy each other's evidence claim.

Correct PR #53 label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE SESSION-TERMINATION RECOVERY CONTRACT
```

No live Admin/KILL or production-approved marker-absence claim exists yet.

## Canonical runbooks

```text
docs/CURRENT_STATUS.md
docs/PRODUCTION_READINESS_AUDIT.md
docs/DEV_INTEGRATION_EVIDENCE.md
docs/APPROVED_CONTROL_PLANE_CERTIFICATION.md
docs/APPROVED_PIPELINE_EVIDENCE.md
docs/APPROVED_CAPTURE_EVIDENCE.md
docs/APPROVED_WAREHOUSE_EVIDENCE.md
docs/APPROVED_WAREHOUSE_FAULT_DRILL.md
docs/FABRIC_WAREHOUSE_SESSION_ABSENCE_CERTIFIER.md
docs/INTEGRATION_EVIDENCE_MERGE.md
docs/GUARANTEE_COVERAGE.md
```

## Current real-service gaps

Still not retained/proven for the exact 0.4.0 candidate:

```text
enterprise Entra token path
live workspace/item authorization
real Fabric SQL Database / Azure SQL Database certification PASS
live approved Pipeline
live Copy Job / Spark with approved observations and verified CaptureReceipt
real Fabric Warehouse target+marker transaction
provider-specific live Warehouse COMMIT fault injector
retained real ambiguous-COMMIT fault-drill PASS
live exact Warehouse session binding using selected SQL driver
live Admin DMV/KILL/rollback chain
production-approved marker-absence recovery
live Kafka / Delta CDF if part of public release scope
capacity/gateway/throttling and enterprise IAM/network/DR/monitoring/governance evidence
complete exact-release certified IntegrationEvidenceManifest
```

## Next active work

Preferred real sequence:

1. replace DEV placeholder release hash/item UUIDs with exact candidate values;
2. run read-only item smoke;
3. run production control-plane certification;
4. strict-merge prerequisites;
5. run approved Pipeline;
6. run approved Copy Job + Spark capture;
7. run approved Warehouse target+marker recovery;
8. if required, run provider-specific real ambiguous-COMMIT fault drill;
9. if the unresolved branch matters, exercise exact-session termination recovery under separately controlled Admin authority;
10. strict-merge required evidence and pass `integration-evidence-validate --require-certified`;
11. prove Kafka/Delta only if included in the `0.4.0` public promise;
12. perform exact-candidate release audit.

If real enterprise inputs remain unavailable, do not invent another Warehouse recovery algorithm. The reusable implementation for commit, real-fault evidence, and safe NOT_COMMITTED recovery is now present. The next useful work should prepare exact-candidate real evidence or a provider-specific live injector only when the actual enterprise mechanism is known.

## Main CLI surfaces

```text
fabric-framework capture-semantic-onboarding-validate ...
fabric-framework integration-run-preflight ...
fabric-framework integration-item-smoke-run ...
fabric-framework integration-control-plane-certify-run ...
fabric-framework integration-pipeline-run ...
fabric-framework integration-capture-run ...
fabric-framework integration-warehouse-run ...
fabric-framework integration-warehouse-fault-drill-run ...
fabric-framework integration-evidence-merge ...
fabric-framework integration-evidence-validate ...
```

## Canonical project memory

For a new conversation, read in this order:

1. `docs/CURRENT_STATUS.md`
2. `docs/CHEATSHEET_PATTERN_ALIGNMENT.md`
3. `docs/PRODUCTION_READINESS_AUDIT.md`
4. `docs/DEV_INTEGRATION_EVIDENCE.md`
5. `docs/APPROVED_CONTROL_PLANE_CERTIFICATION.md`
6. `docs/APPROVED_PIPELINE_EVIDENCE.md`
7. `docs/APPROVED_CAPTURE_EVIDENCE.md`
8. `docs/APPROVED_WAREHOUSE_EVIDENCE.md`
9. `docs/APPROVED_WAREHOUSE_FAULT_DRILL.md`
10. `docs/FABRIC_WAREHOUSE_SESSION_ABSENCE_CERTIFIER.md`
11. `docs/INTEGRATION_EVIDENCE_MERGE.md`
12. `docs/GUARANTEE_COVERAGE.md`
13. `docs/EXTENSION_MODEL.md`
14. `docs/PROJECT_BLUEPRINT.md`
15. `docs/PRODUCTION_REQUIREMENTS.md`
16. `docs/CAPTURE_PATTERN_CATALOG.md`
17. `docs/TARGET_OPERATION_IDEMPOTENCY.md`
18. `docs/PROVIDER_NATIVE_RECOVERY.md`
19. `docs/FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md`
20. `docs/CONTROL_PLANE_CERTIFICATION.md`
21. `docs/RELATIONAL_RUNTIME_REPOSITORY.md`
22. `docs/FABRIC_PIPELINE_BACKEND.md`
23. `docs/FABRIC_CAPTURE_REST_TRANSPORTS.md`
24. `docs/EXECUTION_ENGINE_STRATEGY.md`
25. `docs/FABRIC_EXECUTION_MODEL.md`
26. `docs/CDC_DESIGN.md`
27. `docs/CONTROL_PLANE_DESIGN.md`
28. `docs/REPOSITORY_STRUCTURE.md`
29. `docs/CICD_DESIGN.md`
30. `docs/ECOSYSTEM_BLUEPRINT.md`

If documentation conflicts with code/tests, inspect implementation and repair documentation before continuing.
