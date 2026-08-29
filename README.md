# fabric-data-framework

Reusable, versioned Microsoft Fabric Data Engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

The framework owns reusable data-engineering semantics and operational contracts. Domain repositories consume an immutable framework wheel and normally onboard datasets through source-controlled metadata, environment bindings, capability profiles and bounded logical-name extensions rather than framework edits.

## Release status

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
current baseline      = 014cd334105de6f867b6320509b94147a444a2fa
latest CI             = Actions 33253817758
full tests            = 455
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
```

PR #39 added:

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

Merge/certification validation happens before output write, so failed or conflicting merges do not clobber retained evidence.

## Current real-service gaps

Still not retained/proven for the exact 0.4.0 candidate:

```text
enterprise Entra token path
live workspace/item authorization
live Pipeline / Copy Job / Spark runs and observations
real Fabric Warehouse transaction + ambiguous COMMIT drill
real Fabric SQL Database / Azure SQL Database certification
live Kafka / Delta CDF if included in public release scope
capacity/gateway/throttling and enterprise IAM/network/DR/monitoring/governance evidence
complete exact-release IntegrationEvidenceManifest
```

## Next active work

1. implement an environment-variable-driven approved-run control-plane certification runner;
2. replace DEV placeholder release hash/item UUIDs with exact candidate values;
3. run approved read-only item preflight and live item smoke;
4. run selected real control-plane backend certification;
5. merge retained partial evidence;
6. only then authorize representative Pipeline/Copy/Spark/Warehouse mutation/failure drills;
7. finish exact-release evidence and release audit before considering `0.4.0`.

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
5. `docs/INTEGRATION_EVIDENCE_MERGE.md`
6. `docs/GUARANTEE_COVERAGE.md`
7. `docs/PROJECT_BLUEPRINT.md`
8. `docs/PRODUCTION_REQUIREMENTS.md`
9. `docs/CAPTURE_PATTERN_CATALOG.md`
10. `docs/TARGET_OPERATION_IDEMPOTENCY.md`
11. `docs/PROVIDER_NATIVE_RECOVERY.md`
12. `docs/FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md`
13. `docs/CONTROL_PLANE_CERTIFICATION.md`
14. `docs/RELATIONAL_RUNTIME_REPOSITORY.md`
15. `docs/FABRIC_PIPELINE_BACKEND.md`
16. `docs/FABRIC_CAPTURE_REST_TRANSPORTS.md`
17. `docs/EXECUTION_ENGINE_STRATEGY.md`
18. `docs/FABRIC_EXECUTION_MODEL.md`
19. `docs/CDC_DESIGN.md`
20. `docs/CONTROL_PLANE_DESIGN.md`
21. `docs/REPOSITORY_STRUCTURE.md`
22. `docs/CICD_DESIGN.md`
23. `docs/ECOSYSTEM_BLUEPRINT.md`

If documentation conflicts with code/tests, inspect implementation and repair documentation before continuing.
