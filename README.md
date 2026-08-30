# fabric-data-framework

Reusable, versioned Microsoft Fabric Data Engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns reusable data-engineering semantics and operational contracts. Domain repositories consume an immutable framework wheel and normally onboard datasets through source-controlled metadata, environment bindings, capability profiles and bounded logical-name extensions rather than framework edits.

## Release status

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
current code baseline = 264c7547b4e70d24f258bdc3962af83d972e967d  (PR #49 merge)
latest code CI        = Actions 33282725576
full tests            = 513
```

**Do not publish v0.4.0 yet.** The remaining gate is approved real-environment evidence, selected production backend certification and retained enterprise controls.

## Architecture

```text
source semantic truth
  -> immutable DatasetConfig + semantic onboarding
  -> capability resolver + immutable ExecutionPlan
  -> native/external capture movement
  -> validated CaptureReceipt / native evidence
  -> normalize / DQ / apply
  -> target-operation commit proof / reconciliation
  -> downstream watermark or CDC checkpoint
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
```

## Current reusable capability surface

- orthogonal cheatsheet-aligned source/change/read/delete/Bronze semantics;
- exact fourteen-row cheatsheet semantic presets and semantic onboarding CI gate;
- composite WATERMARK + lookback semantics;
- full-baseline -> WATERMARK bootstrap evidence contract;
- snapshot -> CDC no-gap/no-double-apply bootstrap;
- APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF;
- normalized Bronze lineage, DQ/quarantine/accounting and reconciliation;
- provider-neutral CDC order/dedupe/checkpoint contracts;
- Debezium/Kafka and Delta CDF normalization/recovery contracts;
- replay-stable file manifests and API cursor/window guardrails;
- durable target-operation CAS journal and unknown-outcome recovery;
- SQLAlchemy relational control-plane repository;
- Fabric REST Job Scheduler and Data Pipeline backend;
- concrete Copy Job and Spark Job Definition REST transports;
- Fabric Warehouse same-transaction target-side commit marker proof;
- approved-environment evidence spec/manifest/preflight/read-only item runner;
- strict staged integration evidence merge with conflict/output-safety rules;
- approved production control-plane certification runner;
- approved Fabric Pipeline evidence runner requiring exact durable child outcome;
- approved Copy Job + Spark capture evidence runner requiring verified observation -> `CaptureReceipt` + native correlation;
- approved Warehouse commit/recovery runner requiring same-transaction marker proof and durable target-operation reconciliation;
- approved Warehouse ambiguous-COMMIT fault-drill runner with a separate evidence kind and explicit authorization;
- controlled `capture_observers`, `spark_execution_data`, `warehouse_mutations`, and `warehouse_commit_fault_injectors` extension entry points;
- credential-like retained evidence/provider exception redaction, including Warehouse secondary-correlation failures;
- immutable release/config/deployment provenance.

These are portable/reference, transport/backend, or approved-runner contracts unless explicitly backed by retained real-service evidence.

## Cheatsheet acceptance model

Canonical detail:

```text
docs/CHEATSHEET_PATTERN_ALIGNMENT.md
```

At the **semantic-contract + onboarding-validation level**, all fourteen cheatsheet rows are first-class and tested. Legacy `CapturePattern` remains supported through compatibility projection.

## Staged approved-environment evidence

Canonical runbooks:

```text
docs/DEV_INTEGRATION_EVIDENCE.md
docs/INTEGRATION_EVIDENCE_MERGE.md
docs/APPROVED_CONTROL_PLANE_CERTIFICATION.md
docs/APPROVED_PIPELINE_EVIDENCE.md
docs/APPROVED_CAPTURE_EVIDENCE.md
docs/APPROVED_WAREHOUSE_EVIDENCE.md
docs/APPROVED_WAREHOUSE_FAULT_DRILL.md
```

PR #39 added strict staged evidence merge. Contradictory reruns are never silently resolved by latest/PASS/FAIL precedence.

PR #41 added the exact-release approved control-plane certification runner. The runtime database URL value never enters source-controlled config or retained evidence. Real `PRODUCTION DB PROVEN` still requires a retained PASS against the selected real backend.

PR #43 added the approved Pipeline runner. Fabric `Completed` becomes PASS only when the exact durable framework `DatasetDispatchOutcome` for the generated child `dataset_run_id` exists and is `SUCCEEDED`.

PR #45 added the approved Copy Job + Spark capture runner. Provider `Completed` still requires item-specific post-run observation before `FabricNativeRunEvidence` and a verified `CaptureReceipt` exist.

Correct capture label:

```text
IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT
```

PR #47 added the approved Fabric Warehouse commit/recovery runner:

```bash
fabric-framework integration-warehouse-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/prerequisites-merged.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --warehouse-config evidence/warehouse-run.json \
  --evidence-reference artifact:warehouse-query-and-marker-evidence \
  --report-output evidence/warehouse-report.json \
  --output evidence/warehouse-partial.json \
  --allow-warehouse-execution
```

The framework owns the SQL transaction and operation marker. The customer mutation extension receives the existing SQLAlchemy `Connection` and may perform only the bounded target mutation; it must not commit, write the framework marker, mutate the journal, or decide PASS.

Recovery remains tri-state:

```text
matching marker -> COMMITTED
marker absent -> UNRESOLVED
marker absent + independently certified no-late-commit absence proof -> NOT_COMMITTED
```

A normal successful approved run deliberately simulates **framework ACK loss after the target transaction returns** and proves `UNKNOWN -> COMMITTED -> SUCCEEDED -> SKIP_SUCCEEDED`. This does not claim that a real driver/network COMMIT disconnect occurred.

Correct Warehouse label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
```

PR #49 added a **separate** stronger evidence surface for a real ambiguous-COMMIT drill:

```bash
fabric-framework integration-warehouse-fault-drill-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/warehouse-prerequisites-merged.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --fault-config evidence/warehouse-fault-drill.json \
  --evidence-reference artifact:warehouse-fault-provider-log \
  --report-output evidence/warehouse-fault-report.json \
  --output evidence/warehouse-fault-partial.json \
  --allow-warehouse-fault-injection
```

The evidence kind is:

```text
FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL
```

A PASS requires all of the following for the exact operation:

```text
normal approved Warehouse commit/recovery prerequisite PASS
fault injector armed
execute_atomic() actually raises a provider/driver exception
fault injector independently verifies the intended fault triggered
arm/verification fault identity matches
fault mechanism disarms before marker probe
marker probe = COMMITTED
journal = SUCCEEDED
later claim = SKIP_SUCCEEDED
```

A normal transaction return can **never** PASS the fault drill, even if the marker committed and even if an injector reports `triggered=true`. Marker absence remains `UNRESOLVED`; the fault injector is not an absence certifier and cannot manufacture `NOT_COMMITTED`.

Correct fault-drill label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT
```

CI uses deterministic doubles to prove the runner and fail-closed semantics. It does **not** prove that a real Fabric/network/driver fault occurred.

## Current real-service gaps

Still not retained/proven for the exact 0.4.0 candidate:

```text
enterprise Entra token path
live workspace/item authorization
real Fabric SQL Database / Azure SQL Database certification PASS
live Pipeline run through the approved runner
live Copy Job / Spark runs through approved observers and verified CaptureReceipt evidence
real Fabric Warehouse target mutation + same-transaction marker execution
provider-specific real Warehouse COMMIT fault injector in an approved environment
retained real ambiguous Warehouse COMMIT fault-drill PASS
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
4. strict-merge prerequisite evidence;
5. run approved Pipeline evidence;
6. run approved Copy Job and Spark capture evidence with fingerprinted customer extensions;
7. run approved Warehouse target+marker transaction/recovery stage;
8. if the stronger claim is required, install a provider-specific fingerprinted fault injector and run the separate approved ambiguous-COMMIT drill;
9. strict-merge all required evidence and pass `integration-evidence-validate --require-certified`;
10. prove Kafka/Delta live only if included in the `0.4.0` public promise;
11. run exact-candidate release audit before considering `0.4.0`.

If real enterprise inputs remain unavailable, do not duplicate another Warehouse fault runner. The most plausible remaining reusable boundary is a production-approved marker-absence certifier contract **only if** a provider/session-specific no-late-commit proof can be defined without weakening the tri-state rule.

## Local development

```bash
python -m pip install -e '.[dev]'
pytest
```

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
fabric-framework control-plane-migrate ...
fabric-framework control-plane-certify ...
fabric-framework metadata-materialize ...
fabric-framework release-manifest ...
fabric-framework deployment-plan ...
fabric-framework deployment-record ...
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
10. `docs/INTEGRATION_EVIDENCE_MERGE.md`
11. `docs/GUARANTEE_COVERAGE.md`
12. `docs/EXTENSION_MODEL.md`
13. `docs/PROJECT_BLUEPRINT.md`
14. `docs/PRODUCTION_REQUIREMENTS.md`
15. `docs/CAPTURE_PATTERN_CATALOG.md`
16. `docs/TARGET_OPERATION_IDEMPOTENCY.md`
17. `docs/PROVIDER_NATIVE_RECOVERY.md`
18. `docs/FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md`
19. `docs/CONTROL_PLANE_CERTIFICATION.md`
20. `docs/RELATIONAL_RUNTIME_REPOSITORY.md`
21. `docs/FABRIC_PIPELINE_BACKEND.md`
22. `docs/FABRIC_CAPTURE_REST_TRANSPORTS.md`
23. `docs/EXECUTION_ENGINE_STRATEGY.md`
24. `docs/FABRIC_EXECUTION_MODEL.md`
25. `docs/CDC_DESIGN.md`
26. `docs/CONTROL_PLANE_DESIGN.md`
27. `docs/REPOSITORY_STRUCTURE.md`
28. `docs/CICD_DESIGN.md`
29. `docs/ECOSYSTEM_BLUEPRINT.md`

If documentation conflicts with code/tests, inspect implementation and repair documentation before continuing.
