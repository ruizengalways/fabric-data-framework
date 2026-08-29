# Approved DEV Integration Evidence

Status: implementation + CI contract; real provider execution must still be retained.

This runbook defines how to upgrade framework capabilities from `IMPLEMENTED / CI PROVEN` to provider-specific DEV evidence without storing credentials in repository artifacts.

## Goal

A DEV evidence run must answer all of these separately:

```text
Can the runtime authenticate to Fabric?
Can it read the intended workspace/item?
Can Pipeline execution retain framework + native IDs?
Can Copy Job / Spark produce a verified CaptureReceipt plus native job/root evidence?
Can Warehouse prove a target mutation committed through the same-transaction marker?
Can ambiguous Warehouse outcomes be reconciled without blind retry?
Can the selected relational control plane pass its certification contract?
Are optional provider profiles such as Kafka/Delta also proven when they are in scope?
```

A successful HTTP call by itself is not certification.

## Evidence architecture

```text
source-controlled IntegrationEvidenceSpec
source-controlled ApprovedIntegrationRunnerConfig (no secret values)
        |
        v
credential-free preflight
        |
        v
approved DEV check runners
        |
        +-- Fabric item read-only smoke
        +-- Data Pipeline run
        +-- Copy Job capture
        +-- Spark Job Definition capture
        +-- Warehouse target commit/recovery
        +-- control-plane certification
        +-- optional Kafka / Delta drills
        |
        v
sanitized IntegrationEvidenceCheckResult values
        |
        v
strict staged merge
        |
        v
IntegrationEvidenceManifest
        |
        v
fabric-framework integration-evidence-validate --require-certified
```

The manifest stores correlation IDs and durable references only. It must not contain tokens, passwords, signed URLs, connection strings with user-info credentials, `Authorization` headers or client secrets.

## Authentication

The framework provides two token-provider adapters:

```python
from fabric_data_framework.fabric_auth import (
    AzureIdentityTokenProvider,
    EnvironmentAccessTokenProvider,
)
```

`EnvironmentAccessTokenProvider` reads an ephemeral token on every call and retains only the environment-variable name.

`AzureIdentityTokenProvider` accepts any Azure Identity-compatible credential via the structural `get_token()` contract and requests:

```text
https://api.fabric.microsoft.com/.default
```

The core package does not require or configure `azure-identity`. The deployment environment owns credential selection and policy.

## Source-controlled runner configuration

`ApprovedIntegrationRunnerConfig` is the environment-facing configuration for an exact evidence run. It contains only:

```text
environment
domain
framework_version
release_hash
names of runtime environment variables
control-plane profile name
environment-local Fabric workspace/item UUID bindings by check_id
```

It must not contain access tokens, database URLs, passwords or secret-bearing endpoints.

A schema-valid example is retained at:

```text
examples/dev_integration_runner_config.json
```

The example UUIDs and release hash are placeholders. A real DEV configuration must replace them with the exact released artifact identity and actual DEV item IDs.

Runtime values are injected separately, for example:

```text
FABRIC_ACCESS_TOKEN
FABRIC_CONTROL_PLANE_DATABASE_URL
FABRIC_WAREHOUSE_DATABASE_URL
```

Only the environment-variable **names** are source controlled. Preflight inspects whether each variable is non-empty but never copies its value into the retained plan.

## Credential-free preflight

Before any provider call, run:

```bash
fabric-framework integration-run-preflight \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --require-ready \
  --output evidence/preflight.json
```

By default this plans every required check. Checks that can start remote execution, write target/control state, change provider cursor state or run conformance mutations are classified as mutating and are **not authorized by default**.

To approve the full mutating DEV plan explicitly:

```bash
fabric-framework integration-run-preflight \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --allow-mutating-checks \
  --require-ready \
  --output evidence/preflight-full.json
```

`--allow-mutating-checks` changes the preflight authorization result only. It does not execute provider calls.

### Staged preflight

A first DEV connection should not require Warehouse/control-plane credentials before a safe Fabric read can be tested. Use repeated `--check-id` options to stage a subset:

```bash
fabric-framework integration-run-preflight \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --check-id fabric.item.read \
  --require-ready \
  --output evidence/preflight-item-read.json
```

For this subset only the Fabric token and the selected item binding are prerequisites. Later stages can select control-plane, Pipeline, Copy, Spark and Warehouse checks separately.

Preflight fails closed when exact config/spec identity differs, a selected check is unknown, a required Fabric binding is missing, a runtime env-var is absent/blank, or a mutating check lacks explicit authorization.

## Minimum Fabric authorization smoke

The first real provider call can be executed directly from the CLI:

```bash
fabric-framework integration-item-smoke-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --check-id fabric.item.read \
  --evidence-reference approved-ci:item-read:<artifact-key> \
  --output evidence/item-read-manifest.json
```

This validates exact config/spec identity, performs staged read-only preflight, reads the token only at request time, calls Fabric Core item GET, validates returned item identity, and leaves every other spec check as `NOT_RUN`.

The check calls:

```text
GET /v1/workspaces/{workspaceId}/items/{itemId}
```

HTTP 200 without matching identity is not accepted as PASS. Provider failure text is sanitized before retention.

## Control-plane evidence

The approved runner is:

```bash
fabric-framework integration-control-plane-certify-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --check-id control.cert \
  --external-evidence evidence/control-plane-external.json \
  --evidence-reference artifact:control-plane-certification \
  --report-output evidence/control-plane-certification-report.json \
  --output evidence/control-plane-partial.json \
  --allow-conformance-writes
```

For a production-candidate release gate, the selected backend must be production eligible and the retained report must be production certified. CI only proves the runner contract.

## Pipeline evidence

Run only after the exact-spec prerequisite manifest contains item-read PASS and control-plane certification PASS:

```bash
fabric-framework integration-pipeline-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/prerequisites-merged.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --check-id fabric.pipeline \
  --dataset-id crm.customer \
  --evidence-reference artifact:pipeline-run \
  --output evidence/pipeline-partial.json \
  --allow-pipeline-execution
```

Provider `Completed` is not enough. PASS requires the exact durable framework `DatasetDispatchOutcome` for the generated child `dataset_run_id` and that outcome must be `SUCCEEDED`.

## Copy Job / Spark evidence

The approved capture runner is:

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

Provider `Completed` still requires item-specific post-run observation, verified `FabricNativeRunEvidence`, a verified `CaptureReceipt`, and exact workspace/item/job/root correlation.

Copy Job native incremental/CDC progress remains provider-owned. Spark WATERMARK/CDC evidence requires a frozen framework upper bound and bounded `executionData` resolution when runtime values are supplied.

## Warehouse target commit/recovery evidence

The approved Warehouse runner is:

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

The exact run requires item-read PASS, control-plane certification PASS, the selected Warehouse check still `NOT_RUN`, exact release/config identity, a fingerprinted bounded mutation extension, a production-eligible relational control plane, runtime control-plane and Warehouse DB URLs, a pre-existing marker table, and explicit execution authorization.

The framework owns:

```text
TargetOperationIntent
control-plane target-operation claim/journal
Warehouse SQL transaction
target-side framework marker
commit probe
reconciliation
PASS/FAIL decision
```

The customer/domain extension receives the existing SQLAlchemy `Connection` and may only perform the bounded target mutation. It must not commit, write the framework marker, mutate the journal, or decide PASS.

Primary commit truth remains:

```text
matching same-transaction marker -> COMMITTED
marker absent -> UNRESOLVED
marker absent + independently certified no-late-commit absence proof -> NOT_COMMITTED
```

The normal deterministic runner path commits target+marker and then deliberately simulates framework ACK loss. It proves:

```text
UNKNOWN -> marker probe COMMITTED -> SUCCEEDED -> later SKIP_SUCCEEDED
```

This is not evidence of a real network/driver COMMIT disconnect. A real fault-injection approved run must be retained separately for that stronger claim.

If the provider/driver raises around `execute_atomic`, the runner persists UNKNOWN using the exception **type only**, probes the marker, reconciles only when the marker proves COMMITTED, and otherwise leaves the result unresolved/failed. Raw connection/provider diagnostics are not retained.

## Evidence spec

Example:

```json
{
  "evidence_schema_version": 1,
  "environment": "DEV",
  "domain": "customer",
  "framework_version": "0.4.0",
  "release_hash": "<64 lowercase hex characters>",
  "checks": [
    {"check_id": "fabric.item.read", "kind": "FABRIC_ITEM_READ", "required": true},
    {"check_id": "fabric.pipeline", "kind": "FABRIC_PIPELINE_RUN", "required": true},
    {"check_id": "fabric.copy", "kind": "FABRIC_COPY_JOB_CAPTURE", "required": true},
    {"check_id": "fabric.spark", "kind": "FABRIC_SPARK_CAPTURE", "required": true},
    {"check_id": "warehouse.commit", "kind": "FABRIC_WAREHOUSE_TARGET_COMMIT", "required": true},
    {"check_id": "control.cert", "kind": "CONTROL_PLANE_CERTIFICATION", "required": true},
    {"check_id": "kafka.live", "kind": "KAFKA_PROVIDER", "required": false},
    {"check_id": "delta.live", "kind": "DELTA_CDF_PROVIDER", "required": false}
  ]
}
```

A source-controlled example is retained at `examples/dev_integration_evidence_spec.json`.

## Strict staged merge and certification gate

Do not overwrite a previous substantive stage by rerunning it into the same logical check. Merge partial manifests with:

```bash
fabric-framework integration-evidence-merge \
  --spec evidence-spec.json \
  --manifest evidence/item-read-partial.json \
  --manifest evidence/control-plane-partial.json \
  --manifest evidence/pipeline-partial.json \
  --manifest evidence/copy-partial.json \
  --manifest evidence/spark-partial.json \
  --manifest evidence/warehouse-partial.json \
  --output evidence/evidence-merged.json
```

Merge rules are fail closed:

```text
NOT_RUN = absence
one substantive result = retain unchanged
identical substantive duplicate = allowed
different substantive rerun evidence = conflict
no latest/PASS/FAIL precedence
```

Then run:

```bash
fabric-framework integration-evidence-validate \
  --spec evidence-spec.json \
  --manifest evidence/evidence-merged.json \
  --require-certified
```

The command exits non-zero unless schema/environment/domain/framework/release/check identity matches and every required check is PASS.

## Suggested DEV execution order

```text
1. create exact-release evidence spec + runner config
2. staged preflight for fabric.item.read
3. run read-only Fabric item smoke
4. run approved production control-plane certification
5. strict-merge item + control-plane prerequisites
6. explicitly authorize and execute representative Pipeline child handoff
7. execute representative Copy Job capture
8. execute representative bounded Spark capture
9. execute approved Warehouse mutation + same-transaction marker/recovery stage
10. run required real failure drills, including real ambiguous COMMIT fault injection if claimed
11. strict-merge sanitized evidence partials
12. run --require-certified gate
13. retain manifests, reports and provider correlation artifacts immutably
```

Do not start with destructive or expensive checks before the read-only authorization and backend prerequisites pass.

## Required failure drills before provider-proven release claims

At minimum retain evidence for the release-relevant paths:

```text
Fabric 429 / Retry-After
Pipeline failure or cancellation
remote Completed with missing framework outcome
Copy/Spark failed native job
Copy/Spark success with missing/mismatched observation
Warehouse real ambiguous client/driver outcome around COMMIT boundary
Warehouse absent marker remaining UNRESOLVED without independent absence proof
control-plane transaction rollback/CAS conflict
```

If Kafka or Delta are part of the release scope, also retain cursor drift/retention-gap drills.

## Evidence labels

Until a real approved DEV run is retained:

```text
DEV evidence harness                  IMPLEMENTED + CI PROVEN EVIDENCE HARNESS CONTRACT
approved-run preflight                IMPLEMENTED + CI PROVEN APPROVED-RUN PREFLIGHT CONTRACT
Fabric item smoke runner              IMPLEMENTED + CI PROVEN READ-ONLY RUNNER CONTRACT
approved control-plane runner         IMPLEMENTED + CI PROVEN APPROVED CONTROL-PLANE CERTIFICATION RUNNER CONTRACT
approved Pipeline runner              IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT
approved Copy/Spark capture runner    IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT
approved Warehouse runner             IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
```

After an approved real DEV run, only the exact exercised capability may be upgraded to a provider-proven DEV label. That still does not prove PROD IAM, private networking, capacity behavior, HA/restore, monitoring or governance controls.
