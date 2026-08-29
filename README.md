# fabric-data-framework

Reusable, versioned Microsoft Fabric Data Engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns reusable data-engineering semantics and operational contracts. Domain repositories consume an immutable framework wheel and normally onboard datasets through source-controlled metadata, environment bindings, capability profiles and bounded logical-name extensions rather than framework edits.

## Release status

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
current baseline      = ad856d864eb5dec35f3c97ec66ca9e920cfa5e28
latest CI             = Actions 33254804867
full tests            = 466
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
```

PR #39 added strict staged evidence merge:

```bash
fabric-framework integration-evidence-merge \
  --spec evidence-spec.json \
  --input evidence/item-read.json \
  --input evidence/control-plane.json \
  --output evidence/merged.json
```

Merge rules are fail-closed:

```text
NOT_RUN = absence
one substantive result = retain unchanged
identical substantive duplicate = allowed
different rerun evidence = conflict
no latest/PASS-wins/FAIL-wins arbitration
```

PR #41 added the exact-release approved control-plane execution path:

```bash
fabric-framework integration-control-plane-certify-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --check-id control-plane.certify \
  --external-evidence evidence/control-plane-external.json \
  --evidence-reference artifact:control-plane-certification \
  --report-output evidence/control-plane-certification-report.json \
  --output evidence/control-plane-partial.json \
  --allow-conformance-writes
```

The runner requires a production-eligible profile, complete external control references and explicit write authorization. The actual database URL exists only in the environment variable whose **name** is stored in source control. Database/driver exceptions are converted to sanitized evidence failures; credential-like report text is rejected before retention.

Correct evidence label for this runner is:

```text
IMPLEMENTED + CI PROVEN APPROVED CONTROL-PLANE CERTIFICATION RUNNER CONTRACT
```

It is not `PRODUCTION DB PROVEN` until a retained run succeeds against the selected real approved backend for the exact release hash.

## Current real-service gaps

Still not retained/proven for the exact 0.4.0 candidate:

```text
enterprise Entra token path
live workspace/item authorization
real Fabric SQL Database / Azure SQL Database certification run
live Pipeline / Copy Job / Spark runs and observations
real Fabric Warehouse transaction + ambiguous COMMIT drill
live Kafka / Delta CDF if included in public release scope
capacity/gateway/throttling and enterprise IAM/network/DR/monitoring/governance evidence
complete exact-release IntegrationEvidenceManifest
```

## Next active work

1. replace DEV placeholder release hash/item UUIDs with exact candidate values;
2. run approved read-only item preflight and live item smoke;
3. run `integration-control-plane-certify-run` against the selected real approved DB;
4. merge retained item + control-plane partial evidence;
5. only after those prerequisites pass, add/authorize representative Pipeline/Copy/Spark approved-run commands;
6. execute real Warehouse target+marker and ambiguous COMMIT failure drills;
7. finish exact-release evidence and release audit before considering `0.4.0`.

If no real enterprise credentials/environment are available in the current execution context, the next reusable code slice is the explicitly-authorized approved Pipeline execution runner; it must not weaken the existing durable framework outcome requirement.

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
6. `docs/INTEGRATION_EVIDENCE_MERGE.md`
7. `docs/GUARANTEE_COVERAGE.md`
8. `docs/PROJECT_BLUEPRINT.md`
9. `docs/PRODUCTION_REQUIREMENTS.md`
10. `docs/CAPTURE_PATTERN_CATALOG.md`
11. `docs/TARGET_OPERATION_IDEMPOTENCY.md`
12. `docs/PROVIDER_NATIVE_RECOVERY.md`
13. `docs/FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md`
14. `docs/CONTROL_PLANE_CERTIFICATION.md`
15. `docs/RELATIONAL_RUNTIME_REPOSITORY.md`
16. `docs/FABRIC_PIPELINE_BACKEND.md`
17. `docs/FABRIC_CAPTURE_REST_TRANSPORTS.md`
18. `docs/EXECUTION_ENGINE_STRATEGY.md`
19. `docs/FABRIC_EXECUTION_MODEL.md`
20. `docs/CDC_DESIGN.md`
21. `docs/CONTROL_PLANE_DESIGN.md`
22. `docs/REPOSITORY_STRUCTURE.md`
23. `docs/CICD_DESIGN.md`
24. `docs/ECOSYSTEM_BLUEPRINT.md`

If documentation conflicts with code/tests, inspect implementation and repair documentation before continuing.
