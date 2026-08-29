# fabric-data-framework

Reusable, versioned Microsoft Fabric Data Engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns reusable data-engineering semantics and operational contracts. Domain repositories consume an immutable framework wheel and normally onboard datasets through source-controlled metadata, environment bindings, capability profiles and bounded logical-name extensions rather than framework edits.

## Release status

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
current code baseline = e7bd8b7c55c5acdf14c58c24085c30e104edf0d6  (PR #47 merge)
latest code CI        = Actions 33279727906
full tests            = 501
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
- approved production control-plane certification runner using runtime-only DB URL values;
- approved Fabric Pipeline evidence runner requiring prerequisite PASS evidence and exact durable child outcome;
- approved Copy Job + Spark capture evidence runner requiring verified observation -> `CaptureReceipt` + native correlation;
- approved Warehouse commit/recovery runner requiring same-transaction marker proof and durable target-operation reconciliation;
- controlled `capture_observer`, `spark_execution_data`, and `warehouse_mutations` customer extension entry points;
- credential-like retained evidence/provider exception redaction;
- immutable release/config/deployment provenance.

These are portable/reference or adapter/backend contracts unless explicitly backed by retained real-service evidence.

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

The Warehouse runner requires:

```text
same exact evidence spec/release
FABRIC_ITEM_READ PASS prerequisite
CONTROL_PLANE_CERTIFICATION PASS prerequisite
selected Warehouse check still NOT_RUN
exact release manifest + config bundle hash
fingerprinted bounded warehouse mutation extension
production-eligible relational control plane
pre-existing target-side marker table
explicit mutation authorization
```

The framework owns the SQL transaction and operation marker. The customer extension receives the existing SQLAlchemy `Connection` and may perform only the bounded target mutation; it must not commit, write the framework marker, mutate the journal, or decide PASS.

Recovery remains tri-state:

```text
matching marker -> COMMITTED
marker absent -> UNRESOLVED
marker absent + independently certified no-late-commit absence proof -> NOT_COMMITTED
```

A normal successful approved run deliberately simulates **framework ACK loss after the target transaction returns** and proves `UNKNOWN -> COMMITTED -> SUCCEEDED -> SKIP_SUCCEEDED`. This does not claim that a real driver/network COMMIT disconnect occurred. Provider/driver exceptions are also persisted as UNKNOWN and reconciled from the target marker; raw exception text is not retained.

Correct Warehouse label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
```

It is not `FABRIC WAREHOUSE PROVEN` until retained exact-release approved real-service execution exists.

## Current real-service gaps

Still not retained/proven for the exact 0.4.0 candidate:

```text
enterprise Entra token path
live workspace/item authorization
real Fabric SQL Database / Azure SQL Database certification PASS
live Pipeline run through the approved runner
live Copy Job / Spark runs through approved observers and verified CaptureReceipt evidence
real Fabric Warehouse target mutation + same-transaction marker execution
real driver/network ambiguous Warehouse COMMIT fault-injection drill
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
8. separately run a real network/driver ambiguous COMMIT fault-injection drill if that claim is required;
9. strict-merge all required evidence and pass `integration-evidence-validate --require-certified`;
10. prove Kafka/Delta live only if included in the `0.4.0` public promise;
11. run exact-candidate release audit before considering `0.4.0`.

If real enterprise inputs remain unavailable, the next reusable slice should target a missing evidence boundary rather than add another broad provider abstraction—for example a controlled real-fault-injection harness or a production-approved marker-absence certifier contract. It must not weaken the existing Warehouse tri-state rule.

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
9. `docs/INTEGRATION_EVIDENCE_MERGE.md`
10. `docs/GUARANTEE_COVERAGE.md`
11. `docs/EXTENSION_MODEL.md`
12. `docs/PROJECT_BLUEPRINT.md`
13. `docs/PRODUCTION_REQUIREMENTS.md`
14. `docs/CAPTURE_PATTERN_CATALOG.md`
15. `docs/TARGET_OPERATION_IDEMPOTENCY.md`
16. `docs/PROVIDER_NATIVE_RECOVERY.md`
17. `docs/FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md`
18. `docs/CONTROL_PLANE_CERTIFICATION.md`
19. `docs/RELATIONAL_RUNTIME_REPOSITORY.md`
20. `docs/FABRIC_PIPELINE_BACKEND.md`
21. `docs/FABRIC_CAPTURE_REST_TRANSPORTS.md`
22. `docs/EXECUTION_ENGINE_STRATEGY.md`
23. `docs/FABRIC_EXECUTION_MODEL.md`
24. `docs/CDC_DESIGN.md`
25. `docs/CONTROL_PLANE_DESIGN.md`
26. `docs/REPOSITORY_STRUCTURE.md`
27. `docs/CICD_DESIGN.md`
28. `docs/ECOSYSTEM_BLUEPRINT.md`

If documentation conflicts with code/tests, inspect implementation and repair documentation before continuing.
