# Approved Copy Job and Spark Capture Evidence

Status: implemented runner contract; real approved Fabric execution still required.

## Purpose

`integration-capture-run` executes one representative Microsoft Fabric Copy Job or
Spark Job Definition capture for an exact release candidate and emits:

- one partial `IntegrationEvidenceManifest`;
- one safe `ApprovedCaptureEvidenceReport` on PASS;
- exact Fabric workspace/item/job/root correlation;
- the verified framework `CaptureReceipt` used by the PASS decision.

The command deliberately does **not** treat Fabric provider `Completed` as capture
success. Generic job status does not prove row counts, actual landing identity,
framework source bounds, native checkpoint identity or snapshot completeness.

## Required sequence

Before a mutating capture check is allowed, the prerequisite manifest for the same
`environment/domain/framework_version/release_hash` must already contain:

```text
FABRIC_ITEM_READ                 PASS
CONTROL_PLANE_CERTIFICATION     PASS
selected Copy/Spark check       NOT_RUN
```

The selected check must remain `NOT_RUN`; the runner does not silently rerun a prior
PASS or FAIL. A rerun is an explicit evidence-selection decision and staged merge will
still reject contradictory substantive evidence.

## Exact-release inputs

The runner validates all of the following before invoking Fabric:

```text
ApprovedIntegrationRunnerConfig.release_hash
        == IntegrationEvidenceSpec.release_hash
        == ReleaseManifest.bundle.release_hash

config_bundle_hash(current dataset JSON files)
        == ReleaseManifest.bundle.config_bundle_hash

capture extension artifact name
        exists in ReleaseManifest.artifact_sha256
```

The last rule is important. Customer/domain observer code may live in a separate wheel,
but the exact wheel or source artifact used for an approved run must be fingerprinted by
the release manifest. A logical entry-point name alone is not sufficient provenance.

## Capture run config

Example Copy Job recipe:

```json
{
  "check_id": "fabric.copy",
  "dataset_id": "crm.customer_copy",
  "landing_reference": "bronze.crm_customer_copy",
  "observation_extension": "crm.customer.copy-observer",
  "extension_artifact_name": "fabric-customer-0.4.0.dev1-py3-none-any.whl"
}
```

Example bounded Spark recipe:

```json
{
  "check_id": "fabric.spark",
  "dataset_id": "crm.customer_spark",
  "landing_reference": "bronze.crm_customer_spark",
  "observation_extension": "crm.customer.spark-observer",
  "extension_artifact_name": "fabric-customer-0.4.0.dev1-py3-none-any.whl",
  "spark_execution_data_extension": "crm.customer.spark-execution-data",
  "source_lower_bound": {
    "updated_at": "2026-08-29T00:00:00Z",
    "customer_id": 10
  },
  "source_upper_bound": {
    "updated_at": "2026-08-30T00:00:00Z",
    "customer_id": 99
  },
  "parameters": {
    "mode": "approved-evidence"
  }
}
```

The recipe is credential-free and has a deterministic `run_config_hash` retained in
the PASS report.

## Bounded extension contract

Fabric does not expose one universal post-run API that proves all framework capture
facts for every Copy Job/Spark implementation. The customer/domain package therefore
supplies narrow extensions through controlled Python entry points.

### Capture observer

Entry-point group:

```text
fabric_data_framework.capture_observers
```

The resolved callable receives:

```python
(request: FabricCaptureRequest, job: FabricJobInstance) -> FabricCaptureObservation
```

It must return the item-specific facts that make the provider run meaningful to the
framework, for example:

```text
rows_read
rows_written
landing_reference
source_reference
source_lower_bound / source_upper_bound
snapshot_id / complete_snapshot
external_checkpoint_reference
schema_version
```

Arbitrary observer diagnostics are not copied into the approved safe report. Store rich
provider/item evidence separately and reference it through `--evidence-reference`.

### Spark execution data

Entry-point group:

```text
fabric_data_framework.spark_execution_data
```

The resolved callable receives:

```python
(request: FabricCaptureRequest, binding: FabricSparkJobDefinitionBinding)
    -> Mapping[str, object] | None
```

It translates already-frozen framework bounds/parameters into the specific Spark Job
Definition `executionData` contract. The framework does not invent a universal command
line syntax.

Example customer `pyproject.toml`:

```toml
[project.entry-points."fabric_data_framework.capture_observers"]
"crm.customer.copy-observer" = "fabric_customer.observers:observe_customer_copy"
"crm.customer.spark-observer" = "fabric_customer.observers:observe_customer_spark"

[project.entry-points."fabric_data_framework.spark_execution_data"]
"crm.customer.spark-execution-data" = "fabric_customer.spark:customer_execution_data"
```

Normal business variation belongs in the customer package. Do not patch the installed
framework wheel or `site-packages` to implement an observer.

## Copy Job rules

The current generic Copy Job profile uses:

```text
execution_engine = FABRIC_COPY_JOB
progress_owner   = FABRIC_NATIVE
```

Therefore the approved run config must **not** supply framework lower/upper bounds or
arbitrary per-run parameters. Native Copy Job progress remains provider transport state,
while the returned verified `CaptureReceipt` is the framework handoff evidence.

Remote `Completed` calls the observer exactly once. Remote FAILED/CANCELLED/DEDUPED does
not call the success observer and cannot produce a receipt.

## Spark rules

The approved Spark capture path uses:

```text
execution_engine = SPARK
progress_owner   = FRAMEWORK
```

For WATERMARK/CDC evidence a frozen `source_upper_bound` is required. If bounds or
runtime parameters are present, `spark_execution_data_extension` is mandatory.

The compiled execution plan must contain exactly one dedicated capture-only
`SPARK_JOB_DEFINITION` unit with `EXTRACT + STAGE` and without downstream roles.

A combined Spark `dataset_execute` unit that also owns APPLY/RECONCILE/COMMIT_STATE is
**not** reused for capture-only evidence. Configure capture and apply stages separately
when proving the capture transport independently.

## Execution

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

Use a separate capture recipe and output files for Spark.

## PASS rule

The effective chain is:

```text
exact release + prerequisites + explicit authorization
        -> concrete Fabric REST transport
        -> provider terminal job
        -> post-run observation extension
        -> FabricNativeRunEvidence
        -> FabricCaptureAdapter.execute_with_evidence()
        -> verified CaptureReceipt
        -> native job/root/provider correlation validation
        -> safe ApprovedCaptureEvidenceReport
        -> IntegrationEvidenceCheckResult PASS
```

Any break in that chain is FAIL or a preflight rejection.

In particular:

```text
provider Completed + missing observer evidence   != PASS
provider Completed + wrong landing              != PASS
provider Completed + wrong framework bound      != PASS
provider success + missing root activity ID      != PASS
```

## Retained report safety

The safe report retains the typed `CaptureReceipt`, run-config hash, execution-plan
hash and provider correlation IDs. It deliberately excludes arbitrary raw provider and
observer diagnostic payloads.

Credential-like values in the capture recipe, report or evidence references are
rejected before retention, including access/refresh token labels, passwords/client
secrets, Authorization/Bearer material, signed URL query values and URI user-info
credentials.

## Evidence label

Until a real approved Fabric tenant run is retained for the exact candidate, the
correct label is:

```text
IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT
```

Do not upgrade this to `FABRIC COPY JOB PROVEN` or `FABRIC SPARK PROVEN` from CI alone.
