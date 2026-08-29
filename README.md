# fabric-data-framework

Reusable, versioned Microsoft Fabric Data Engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns reusable data-engineering semantics and operational contracts. Domain repositories consume an immutable framework wheel and normally onboard datasets through source-controlled metadata, environment bindings, capability profiles and bounded logical-name extensions rather than framework edits.

## Release status

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
current baseline      = f8c2f24264480613ca048aaece09371a72aa529a
latest CI             = Actions 33279105627
full tests            = 490
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
- controlled `capture_observer` and `spark_execution_data` customer extension entry points;
- credential-like retained evidence/provider exception redaction;
- immutable release/config/deployment provenance.

These are portable/reference or adapter/backend contracts unless explicitly backed by retained real-service evidence.

## Cheatsheet acceptance model

Canonical detail:

```text
docs/CHEATSHEET_PATTERN_ALIGNMENT.md
```

A 2026-08-29 audit found the legacy fourteen `CapturePattern` values were not the same taxonomy as the cheatsheet's fourteen semantic rows. PR #34 introduced orthogonal semantics and exact presets; PR #35 added semantic onboarding; PR #37 added full-baseline -> WATERMARK bootstrap.

At the **semantic-contract + onboarding-validation level**, all fourteen cheatsheet rows are now first-class and tested. Legacy `CapturePattern` remains supported through compatibility projection.

## Staged approved-environment evidence

Canonical runbooks:

```text
docs/DEV_INTEGRATION_EVIDENCE.md
docs/INTEGRATION_EVIDENCE_MERGE.md
docs/APPROVED_CONTROL_PLANE_CERTIFICATION.md
docs/APPROVED_PIPELINE_EVIDENCE.md
docs/APPROVED_CAPTURE_EVIDENCE.md
```

PR #39 added strict staged evidence merge. Contradictory reruns are never silently resolved by latest/PASS/FAIL precedence.

PR #41 added the exact-release approved control-plane certification runner. The runtime database URL value never enters source-controlled config or retained evidence. Real `PRODUCTION DB PROVEN` still requires a retained PASS against the selected real backend.

PR #43 added the approved Pipeline runner. Fabric `Completed` becomes PASS only when the exact durable framework `DatasetDispatchOutcome` for the generated child `dataset_run_id` exists and is `SUCCEEDED`.

PR #45 added the approved Copy Job + Spark capture runner:

```bash
fabric-framework integration-capture-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/prerequisites-merged.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --capture-config evidence/copy-capture-run.json \
  --evidence-reference artifact:copy-output-manifest \
  --report-output evidence/copy-capture-report.json \
  --output evidence/copy-partial.json \
  --allow-capture-execution
```

The capture runner requires:

```text
same exact evidence spec/release
FABRIC_ITEM_READ PASS prerequisite
CONTROL_PLANE_CERTIFICATION PASS prerequisite
selected capture check still NOT_RUN
exact release manifest + config bundle hash
customer observer extension artifact fingerprint present in release manifest
explicit remote execution authorization
```

Copy Job keeps `FABRIC_NATIVE` progress authority and cannot accept framework bounds/runtime parameters. Spark keeps `FRAMEWORK` progress authority; WATERMARK/CDC evidence requires a frozen upper bound and a logical Spark `executionData` resolver when runtime data is present. Provider `Completed` still requires item-specific post-run observation before `FabricNativeRunEvidence` and a verified `CaptureReceipt` exist.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT
```

It is not `FABRIC COPY JOB PROVEN` or `FABRIC SPARK PROVEN` until retained exact-release approved tenant runs exist.

## Current real-service gaps

Still not retained/proven for the exact 0.4.0 candidate:

```text
enterprise Entra token path
live workspace/item authorization
real Fabric SQL Database / Azure SQL Database certification PASS
live Pipeline run through the approved runner
live Copy Job / Spark runs through approved observers and verified CaptureReceipt evidence
real Fabric Warehouse transaction + ambiguous COMMIT drill
live Kafka / Delta CDF if included in public release scope
capacity/gateway/throttling and enterprise IAM/network/DR/monitoring/governance evidence
complete exact-release IntegrationEvidenceManifest
```

## Next active work

Preferred real sequence when approved runtime inputs are available:

1. replace DEV placeholder release hash/item UUIDs with exact candidate values;
2. run read-only item smoke;
3. run production control-plane certification;
4. merge prerequisite evidence;
5. run approved Pipeline evidence;
6. run approved Copy Job and Spark capture evidence with fingerprinted customer observer extensions;
7. run approved Fabric Warehouse target+marker transaction plus ambiguous COMMIT/lost-ack recovery drill;
8. finish exact-release evidence and release audit before considering `0.4.0`.

If real enterprise credentials/environment are unavailable in the current execution context, the next reusable code slice is the approved **Fabric Warehouse transaction + ambiguous COMMIT drill runner**. It must preserve the existing tri-state recovery rule and must never turn marker absence alone into retry authorization.

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
8. `docs/INTEGRATION_EVIDENCE_MERGE.md`
9. `docs/GUARANTEE_COVERAGE.md`
10. `docs/EXTENSION_MODEL.md`
11. `docs/PROJECT_BLUEPRINT.md`
12. `docs/PRODUCTION_REQUIREMENTS.md`
13. `docs/CAPTURE_PATTERN_CATALOG.md`
14. `docs/TARGET_OPERATION_IDEMPOTENCY.md`
15. `docs/PROVIDER_NATIVE_RECOVERY.md`
16. `docs/FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md`
17. `docs/CONTROL_PLANE_CERTIFICATION.md`
18. `docs/RELATIONAL_RUNTIME_REPOSITORY.md`
19. `docs/FABRIC_PIPELINE_BACKEND.md`
20. `docs/FABRIC_CAPTURE_REST_TRANSPORTS.md`
21. `docs/EXECUTION_ENGINE_STRATEGY.md`
22. `docs/FABRIC_EXECUTION_MODEL.md`
23. `docs/CDC_DESIGN.md`
24. `docs/CONTROL_PLANE_DESIGN.md`
25. `docs/REPOSITORY_STRUCTURE.md`
26. `docs/CICD_DESIGN.md`
27. `docs/ECOSYSTEM_BLUEPRINT.md`

If documentation conflicts with code/tests, inspect implementation and repair documentation before continuing.
