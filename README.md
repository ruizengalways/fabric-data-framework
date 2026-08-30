# fabric-data-framework

Reusable, versioned Microsoft Fabric Data Engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns reusable data-engineering semantics and operational contracts. Domain repositories consume an immutable framework wheel and normally onboard datasets through source-controlled metadata, environment bindings, capability profiles and bounded logical-name extensions rather than framework edits.

## Release status

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
current code baseline = 4dfa5e22fd8eab67406ced8af954f2d81ad18321  (PR #51 merge)
latest code CI        = Actions 33283668067
full tests            = 525
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
```

## Current reusable capability surface

- orthogonal cheatsheet-aligned source/change/read/delete/Bronze semantics and exact fourteen-row presets;
- semantic onboarding CI gate and full-baseline -> WATERMARK / snapshot -> CDC handoff contracts;
- APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF;
- normalized Bronze lineage, DQ/quarantine/accounting and reconciliation;
- provider-neutral CDC order/dedupe/checkpoint contracts plus Kafka/Debezium and Delta CDF adapter contracts;
- durable target-operation CAS journal and fail-closed unknown-outcome recovery;
- SQLAlchemy relational control-plane repository;
- Fabric REST Pipeline, Copy Job and Spark Job Definition transports/backends;
- Fabric Warehouse same-transaction target-side marker proof;
- approved-run preflight, read-only item smoke, control-plane certification, Pipeline, Copy/Spark capture and Warehouse commit/recovery runners;
- separate approved Warehouse ambiguous-COMMIT fault-drill runner;
- Fabric Warehouse exact-session termination absence-certifier provider contract;
- controlled `capture_observers`, `spark_execution_data`, `warehouse_mutations`, and `warehouse_commit_fault_injectors` extension entry points;
- strict staged integration evidence merge and credential-safe retained evidence.

These are reference/transport/backend/runner contracts unless a retained exact-release real-service run explicitly proves more.

## Warehouse recovery evidence ladder

Normal target commit proof:

```text
same transaction: target mutation + framework marker
matching marker -> COMMITTED
marker absent   -> UNRESOLVED
```

PR #47 added `integration-warehouse-run` and deterministic recovery of simulated framework ACK loss:

```text
EXECUTE -> target+marker commit -> UNKNOWN -> marker COMMITTED
        -> SUCCEEDED -> later SKIP_SUCCEEDED
```

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
```

PR #49 added the separate evidence kind `FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL` and `integration-warehouse-fault-drill-run`. PASS requires an actual observed provider/driver exception, independently verified same fault identity, marker `COMMITTED`, durable `SUCCEEDED`, and later `SKIP_SUCCEEDED`. A normal return can never satisfy this stronger drill.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT
```

PR #51 added the provider-specific session-termination absence-certifier contract. It does **not** make marker absence generally safe. `NOT_COMMITTED` becomes eligible only when all of this is proven:

```text
exact target connection_id + session_id captured before mutation
same exact session still observable after ambiguity
open_transaction_count > 0
independent Admin-capable connection KILLs that exact session
same exact connection/session no longer observable
post-termination marker read succeeds
marker is still absent
```

Critical race rule:

```text
marker appears during termination -> NOT_COMMITTED forbidden
session already disappeared        -> UNRESOLVED
no observable open transaction     -> UNRESOLVED
DMV / KILL / post-check failure    -> UNRESOLVED
```

Query Insights remains secondary correlation only; completed history is not an immediate no-late-commit proof.

Correct PR #51 label:

```text
IMPLEMENTED + CI PROVEN FABRIC WAREHOUSE SESSION-TERMINATION ABSENCE CERTIFIER CONTRACT
```

This is **not** a production-approved marker-absence certifier yet. Approved-run wiring with a separately controlled Admin credential/authorization and retained live Fabric execution are still missing.

## Approved evidence runbooks

```text
docs/DEV_INTEGRATION_EVIDENCE.md
docs/INTEGRATION_EVIDENCE_MERGE.md
docs/APPROVED_CONTROL_PLANE_CERTIFICATION.md
docs/APPROVED_PIPELINE_EVIDENCE.md
docs/APPROVED_CAPTURE_EVIDENCE.md
docs/APPROVED_WAREHOUSE_EVIDENCE.md
docs/APPROVED_WAREHOUSE_FAULT_DRILL.md
docs/FABRIC_WAREHOUSE_SESSION_ABSENCE_CERTIFIER.md
```

## Current real-service gaps

Still not retained/proven for the exact 0.4.0 candidate:

```text
enterprise Entra token path
live workspace/item authorization
real Fabric SQL Database / Azure SQL Database certification PASS
live Pipeline run through the approved runner
live Copy Job / Spark runs through approved observation and CaptureReceipt evidence
real Fabric Warehouse target mutation + same-transaction marker execution
provider-specific live Warehouse COMMIT fault injector
retained real ambiguous Warehouse COMMIT fault-drill PASS
live exact Warehouse session binding / DMV / Admin KILL / post-KILL marker proof
production-approved marker-absence certifier
live Kafka / Delta CDF if included in public release scope
capacity/gateway/throttling and enterprise IAM/network/DR/monitoring/governance evidence
complete exact-release IntegrationEvidenceManifest
```

## Next active work

Preferred real sequence when approved runtime inputs are available:

1. replace DEV placeholder release hash/item UUIDs with exact candidate values;
2. run read-only item smoke;
3. run production control-plane certification;
4. strict-merge prerequisites;
5. run approved Pipeline evidence;
6. run approved Copy Job and Spark capture evidence;
7. run approved Warehouse target+marker transaction/recovery;
8. if required, run the separate provider-specific real ambiguous-COMMIT fault drill;
9. if the `NOT_COMMITTED` recovery branch is required, run approved exact-session termination recovery with a separately controlled Admin authority;
10. strict-merge required evidence and pass `integration-evidence-validate --require-certified`;
11. prove Kafka/Delta live only if included in the public `0.4.0` promise;
12. run exact-candidate release audit.

If real enterprise inputs remain unavailable, the next reusable slice is **approved session-termination recovery wiring**: separate Admin DB credential env-var name, separate explicit termination authorization, exact-session capture before mutation, and use of PR #51 only after a real ambiguous execution exception. Do not make session termination default and do not reuse normal Warehouse mutation authorization for `KILL`.

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

Credentials and physical environment values remain outside reusable semantic config and retained release artifacts.

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
