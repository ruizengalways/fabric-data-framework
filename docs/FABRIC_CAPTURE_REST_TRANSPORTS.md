# Fabric Copy Job and Spark Capture REST Transports

Status: implemented transport contract / deterministic CI target; not yet Fabric-proven.

## Purpose

This runbook defines the concrete Microsoft Fabric REST boundary for two framework capture engines:

- `FABRIC_COPY_JOB` -> `ExecutionKind.FABRIC_COPY_JOB`
- `SPARK` capture -> `ExecutionKind.SPARK_JOB_DEFINITION`

The implementation reuses `FabricRestClient` job mechanics but keeps provider-specific endpoint rules and progress ownership explicit.

## Evidence boundary

A Fabric job instance can prove native job identity, status, root activity correlation and provider timestamps. The generic job-instance response does **not** prove all framework capture facts, including:

- rows read/written for the selected logical dataset;
- actual landing reference;
- exact framework lower/upper source bounds;
- Copy Job native watermark/CDC checkpoint;
- schema version/fingerprint;
- complete-snapshot evidence.

Therefore remote `Completed` alone never creates a `CaptureReceipt`.

Concrete transports require a `FabricCaptureObservationResolver` after successful provider completion. The resolver supplies auditable item/provider-specific post-run facts as `FabricCaptureObservation`. Missing observation evidence fails closed rather than being fabricated.

## Copy Job REST path

Current Microsoft Fabric documentation describes on-demand Copy Job execution through:

```text
POST /v1/workspaces/{workspaceId}/items/{copyJobId}/jobs/instances?jobType=Execute
```

and the Copy Job-specific instance read through:

```text
GET /v1/workspaces/{workspaceId}/copyJobs/{copyJobId}/jobs/instances/{jobInstanceId}
```

`FabricRestClient.run_and_wait_copy_job` preserves those endpoint shapes and shares only generic timeout / `Retry-After` polling mechanics with other item jobs.

### Copy Job progress ownership

The registered default Copy Job capability allows:

```text
FULL
WATERMARK
CDC
```

with:

```text
ProgressOwner.FABRIC_NATIVE
```

The concrete Copy Job transport enforces this again at runtime.

It rejects:

- `ProgressOwner.FRAMEWORK`;
- framework-provided `source_lower_bound` / `source_upper_bound`;
- arbitrary per-run framework parameters.

Reason: the preconfigured Copy Job owns its own incremental state. The framework must not pretend that it dictated a bounded source interval when the provider actually chose the native interval.

Microsoft currently documents that incremental Copy Job tracks state from the last successful run and that a failed Copy Job does not advance that provider-managed state. This provider state remains separate from framework downstream apply/checkpoint state.

Correct ordering is therefore conceptually:

```text
Copy Job native state
  -> Copy Job run
  -> provider Completed
  -> post-run observation
  -> CaptureReceipt
  -> framework normalize/apply/reconcile
  -> framework downstream checkpoint / state commit
```

A Copy Job native checkpoint reference, when available, must come from retained provider/item evidence. The framework does not substitute `jobInstanceId` as a fake source checkpoint.

## Copy Job CDC fidelity

The framework capture strategy `CDC` is intentionally coarse. Source-fidelity onboarding must still classify what the provider actually preserves.

As of the current Microsoft documentation, Copy Job CDC has a known limitation: **net change capture only; full change capture is not yet available**. It can capture inserts, updates and deletes, but a dataset that promises every intermediate row-change event must not be mapped to this provider path merely because the coarse strategy is `CDC`.

Other current provider limitations and connector-specific retention behavior must be revalidated at deployment time.

## Spark Job Definition REST path

Current Microsoft Fabric v1 documentation uses the dedicated execution endpoint:

```text
POST /v1/workspaces/{workspaceId}/sparkJobDefinitions/{sparkJobDefinitionId}/jobs/sparkjob/instances
```

The optional request body is:

```json
{
  "executionData": {
    "commandLineArguments": "...",
    "executableFile": "...",
    "mainClass": "...",
    "additionalLibraryUris": [],
    "defaultLakehouseId": {},
    "environmentId": {}
  }
}
```

Only fields required by the selected Spark child contract should be supplied.

The returned `Location` identifies the job instance. Status polling uses the generic item job-instance endpoint exposed by the current provider response model.

## Spark framework-bounded capture

The concrete Spark capture transport requires:

```text
ProgressOwner.FRAMEWORK
```

If `FabricCaptureRequest` contains source bounds or runtime parameters, a `FabricSparkExecutionDataResolver` is mandatory. The resolver translates framework runtime facts into the selected Spark Job Definition's documented `executionData` contract.

The transport deliberately does not invent a universal command-line syntax such as `--lower` / `--upper`; that syntax belongs to the released Spark child/runtime contract.

After provider completion, the observation resolver must report the actual observed lower/upper bounds. `FabricCaptureAdapter` then compares them against the requested framework bounds. Any mismatch fails closed.

## Native evidence

Both transports retain provider correlation inside `FabricNativeRunEvidence.diagnostics.provider`:

```text
workspace_id
item_id
job_instance_id
root_activity_id
job_type
remote_status
failure_reason
provider_start_time_present
provider_end_time_present
```

Provider timestamps are preferred. If the provider response omits a start/end timestamp, the transport uses local invocation/observation timestamps only to maintain a valid evidence interval and explicitly records that the provider timestamp was absent.

Observation-specific details are nested under:

```text
diagnostics.observation
```

Do not store access tokens, connection secrets, passwords or other credentials in observation diagnostics.

## Failure behavior

Provider terminal status maps as follows:

```text
Completed -> SUCCEEDED
Failed    -> FAILED
Cancelled -> CANCELLED
Deduped   -> UNKNOWN
```

Only `SUCCEEDED` proceeds to post-run observation and potential `CaptureReceipt` creation.

Failed/cancelled/deduped runs produce native evidence for diagnosis but do not invoke a success observer and do not become successful framework capture receipts.

## Environment-local binding

Physical item IDs remain deployment/environment bindings:

```python
FabricCopyJobBinding(
    workspace_id=...,
    copy_job_id=...,
)

FabricSparkJobDefinitionBinding(
    workspace_id=...,
    spark_job_definition_id=...,
)
```

Domain metadata selects semantic engine/profile. It must not hard-code DEV/TEST/PROD Fabric item IDs into framework code.

## Microsoft documentation used by this contract

Revalidate these current product pages when certifying a real environment:

- Microsoft Fabric: REST API capabilities for Copy Job in Data Factory
- Microsoft Fabric REST API: Run on-demand Spark Job Definition
- Microsoft Fabric: Incremental copy in Copy Job
- Microsoft Fabric: Change data capture (CDC) in Copy Job
- Microsoft Fabric: Spark Job Definition item definition / V2 API

## Current proof level

After deterministic tests pass, the correct claim is:

```text
IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT
```

It is **not** yet:

```text
FABRIC PROVEN
```

Real proof still requires an approved Fabric workspace execution retaining:

- real Entra/service-principal/managed-identity authentication evidence;
- real workspace/item authorization;
- real Copy Job and Spark job instance/root activity IDs;
- real post-run metrics/landing/source-bound observations;
- throttling/retry behavior;
- provider failure/cancel behavior;
- relational framework `CaptureReceipt` and downstream state correlation.
