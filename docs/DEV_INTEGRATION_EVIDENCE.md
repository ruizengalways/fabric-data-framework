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
Can the selected relational control plane pass its certification contract?
Are optional provider profiles such as Kafka/Delta also proven when they are in scope?
```

A successful HTTP call by itself is not certification.

## Evidence architecture

```text
source-controlled IntegrationEvidenceSpec
        |
        v
approved DEV check runners
        |
        +-- Fabric item read-only smoke
        +-- Data Pipeline run
        +-- Copy Job capture
        +-- Spark Job Definition capture
        +-- Warehouse target marker
        +-- control-plane certification
        +-- optional Kafka / Delta drills
        |
        v
sanitized IntegrationEvidenceCheckResult values
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

## Minimum Fabric authorization smoke

Use `run_fabric_item_read_check()` against a known DEV item before starting expensive jobs.

The check calls the current Fabric Core item endpoint:

```text
GET /v1/workspaces/{workspaceId}/items/{itemId}
```

It validates the returned item ID. HTTP 200 without matching identity is not accepted as PASS.

The caller must supply a retained evidence reference, for example an approved CI artifact path or evidence-store key. Do not use a signed download URL.

## Pipeline evidence

Pipeline PASS evidence requires:

```text
framework_pipeline_run_id
dataset_run_id
workspace_id
pipeline item_id
native job_instance_id
root_activity_id
retained evidence reference
```

The provider job must be `Completed`. This does not replace the existing semantic rule that `Fabric Completed != framework success`; the exact durable framework dataset outcome must still exist.

## Copy Job / Spark evidence

Approved DEV capture should call:

```python
result = adapter.execute_with_evidence(request)
```

rather than invoking the transport twice.

The result contains:

```text
FabricCaptureExecutionResult
  receipt          -> verified framework CaptureReceipt
  native_evidence  -> provider workspace/item/job/root/status diagnostics
```

`build_fabric_capture_check_result()` verifies that the native job identity agrees with `CaptureReceipt.native_run_id` and requires the provider root activity ID.

Copy Job native incremental/CDC progress remains provider-owned. It must not be copied into the framework downstream checkpoint as if it were framework-owned state.

## Warehouse target commit evidence

The primary proof remains the Warehouse operation marker committed in the same transaction as the target mutation.

```text
target mutation
+ framework operation marker
----------------------------
same Warehouse transaction
```

`build_fabric_warehouse_commit_check_result()` references that durable marker. Query Insights/query labels remain secondary correlation only; delayed query history is not primary commit truth.

## Control-plane evidence

Run the existing control-plane certification against the selected real backend, retain the report, then project it into the DEV evidence manifest with `build_control_plane_certification_check_result()`.

For a production-candidate release gate, require `production_certified=True`; reference-only certification is insufficient.

The evidence harness deliberately does not duplicate transaction rollback, target-operation CAS or CDC checkpoint CAS tests.

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

A runner ID not declared in this spec is rejected rather than silently ignored.

## Runner behavior

`run_integration_evidence()` is fail closed:

```text
registered runner returns exact valid PASS -> PASS
registered runner returns FAIL           -> FAIL
registered runner raises                 -> sanitized FAIL
missing runner                           -> NOT_RUN
unknown runner ID                        -> whole run rejected
```

Provider/driver exception text is not copied into retained evidence because it can include connection strings or credential-bearing URLs.

## Certification gate

Retain the spec and manifest as immutable build/deployment evidence, then run:

```bash
fabric-framework integration-evidence-validate \
  --spec evidence-spec.json \
  --manifest evidence-manifest.json \
  --require-certified
```

The command exits non-zero unless:

```text
schema version matches
DEV/UAT/PROD identity matches
same domain
same framework version
same release_hash
exact same check specification
all required checks == PASS
```

The printed `manifest_hash` can be stored in deployment provenance or an external evidence index.

## Suggested DEV execution order

```text
1. resolve environment-local bindings
2. acquire ephemeral identity through approved environment configuration
3. read-only Fabric item smoke
4. certify the real control-plane backend
5. execute one representative Pipeline child handoff
6. execute representative Copy Job capture
7. execute representative bounded Spark capture
8. execute Warehouse mutation + same-transaction marker
9. run required failure drills
10. assemble sanitized evidence manifest
11. run --require-certified gate
12. retain manifest, reports and provider correlation artifacts immutably
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
Warehouse ambiguous client outcome after target COMMIT boundary
Warehouse absent marker remaining UNRESOLVED without independent absence proof
control-plane transaction rollback/CAS conflict
```

If Kafka or Delta are part of the release scope, also retain cursor drift/retention-gap drills.

## Evidence labels

Until a real approved DEV run is retained:

```text
DEV evidence harness                  IMPLEMENTED + CI PROVEN CONTRACT
Fabric Pipeline backend               IMPLEMENTED + CI PROVEN BACKEND
Copy/Spark transports                 IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT
Warehouse target commit proof         IMPLEMENTED + CI PROVEN PROVIDER CONTRACT
SQLAlchemy runtime repository         IMPLEMENTED + CI PROVEN RELATIONAL RUNTIME
```

After an approved real DEV run, only the exact exercised capability may be upgraded to a provider-proven DEV label. That still does not prove PROD IAM, private networking, capacity behavior, HA/restore, monitoring or governance controls.
