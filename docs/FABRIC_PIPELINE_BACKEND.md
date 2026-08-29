# Fabric Pipeline Backend — Runtime and Integration Runbook

Status: executable/reference contract for unreleased `0.4.0`

Last updated: 2026-08-29

## Purpose

The framework can now execute planner-selected dataset waves through a reusable Microsoft Fabric Data Pipeline item while preserving framework-owned dependency, criticality, execution-plan and outcome semantics.

The boundary is deliberately thin:

```text
framework planner
    -> dependency-ready dataset wave
    -> compile ExecutionPlan
    -> FabricPipelineBackend
    -> Fabric REST Job Scheduler
    -> reusable child Data Pipeline
    -> released framework/domain runtime
    -> durable framework dataset outcome
    -> parent verifies exact dataset_run_id
```

The Data Pipeline is a physical orchestration host. It is not a second semantic engine.

---

## 1. Current executable components

```text
adapters/fabric/rest.py
    Fabric v1 on-demand job POST
    Location/job-instance correlation
    typed per-run parameters
    Retry-After aware polling
    provider error/retry evidence

adapters/fabric/pipeline.py
    environment-local workspace/pipeline binding
    stable framework correlation parameters
    REST-backed pipeline transport

execution/backends/fabric_pipeline.py
    planner-ready wave execution
    compiled ExecutionPlan handoff
    remote status mapping
    framework outcome verification
    native run correlation evidence

dispatcher.py
    provider-neutral ReadyWaveBackend contract
    existing dependency/criticality semantics
```

The existing `dispatch_datasets(...)` remains the in-process compatibility API. A physical backend uses `dispatch_datasets_with_backend(...)`.

---

## 2. Environment-local binding

A domain dataset must not contain hard-coded Fabric workspace/item IDs.

The runtime resolves a `FabricPipelineBinding`:

```text
workspace_id
pipeline_item_id
job_type = Pipeline
```

Those values are environment-local physical bindings. DEV/UAT/PROD can point at different Fabric workspaces/items without changing business metadata or framework semantics.

Recommended ownership:

```text
fabric-customer
    semantic DatasetConfig

release/environment binding artifact
    logical pipeline role -> workspace/item identity

fabric-data-framework
    typed binding + execution contract
```

Do not put bearer tokens, client secrets or passwords into the binding model.

---

## 3. Authentication boundary

`FabricRestClient` accepts an injected access-token provider:

```python
client = FabricRestClient(token_provider=get_fabric_access_token)
```

The framework does not choose whether the enterprise uses a user token, service principal, managed identity or another approved Entra flow. Authentication and secret authority remain environment/security concerns.

A production integration must retain evidence for:

```text
identity used
workspace/item permission
credential/token acquisition method
network path
successful authenticated API call
```

Do not log the access token.

---

## 4. Stable child-pipeline parameters

Every invocation sends framework correlation values:

```text
framework_pipeline_run_id    Guid
framework_dataset_run_id     Guid
dataset_id                   Text
run_mode                     Text
attempt                      Integer
effective_config_hash        Text
execution_plan_hash          Text
```

The REST client emits the explicit Job Scheduler parameter `type`; it does not rely on `Automatic` inference.

The child pipeline must treat these values as immutable correlation inputs. It must not replace `dataset_id`, hashes or run IDs with locally generated alternatives.

Microsoft documents per-run parameter support as item/job-type dependent. Therefore a real DEV run must prove that the selected Data Pipeline job type accepts the required parameter set. A `FeatureNotAvailable` response is an integration failure, not something the framework silently bypasses.

---

## 5. Remote job lifecycle

The REST flow is:

```text
POST on-demand item job
    -> HTTP 202
    -> require Location header
    -> derive job_instance_id
    -> poll job instance
    -> respect Retry-After when supplied
    -> terminal status
```

Recognized job statuses are:

```text
NotStarted
InProgress
Completed
Failed
Cancelled
Deduped
```

Unknown future statuses fail closed until explicitly supported.

Provider HTTP errors retain, when returned:

```text
HTTP status
Fabric errorCode
isRetriable
Retry-After
provider payload
```

This evidence can drive later retry policy without converting every provider failure into a generic exception.

---

## 6. Critical success rule

> A Fabric job status of `Completed` is not a framework dataset success signal.

The child pipeline/runtime must persist the terminal framework outcome for the exact `framework_dataset_run_id`.

Parent verification is:

```text
remote status == Completed
    AND durable dataset outcome exists
    AND outcome.dataset_run_id == requested dataset_run_id
    AND framework outcome is terminal
```

Only then can the parent consume that semantic result.

Fail-closed examples:

```text
Fabric Completed + no dataset outcome
    -> FABRIC_PIPELINE_RESULT_MISSING

Fabric Completed + different dataset_run_id
    -> FABRIC_PIPELINE_RESULT_MISMATCH

Fabric Completed + framework RUNNING/PENDING
    -> FABRIC_PIPELINE_RESULT_NON_TERMINAL
```

This prevents a visually green Fabric Pipeline from being mistaken for a committed/reconciled data result.

---

## 7. Provider-native evidence

The parent records one `StepRunAudit` named:

```text
fabric_pipeline_remote_job
```

Its `details` include:

```text
workspace_id
pipeline_item_id
job_instance_id
root_activity_id
job_type
remote_status
failure_reason
execution_plan_hash
```

The relational `step_run` table already has a `details` JSON column, so this evidence does not require a new control-plane schema version.

Relational ordering matters:

```text
step_run.dataset_run_id -> dataset_run.dataset_run_id
```

For provider-side failure, the parent dataset failure is persisted first, then native step evidence. For remote `Completed`, the child is required to have already persisted the dataset outcome; the parent then attaches native correlation.

---

## 8. Deduplication semantics

Fabric job status `Deduped` is not treated as successful execution of the requested framework dataset run.

Current framework mapping:

```text
Deduped -> DatasetStatus.BLOCKED
           retryable = true
           FABRIC_PIPELINE_DEDUPED
```

Reason: deduplication may indicate that another provider job was selected/merged, but it does not by itself prove that the current framework `dataset_run_id` executed and persisted its semantic result.

A future provider-specific correlation rule may safely strengthen this behavior only with retained proof.

---

## 9. Dependency and concurrency ownership

Framework planner remains authoritative for:

```text
dataset selection
dependencies
blocking behavior
criticality
ready waves
maximum framework fan-out
```

A `ReadyWaveBackend` receives one ready set and must return exactly that set.

```text
missing dataset result    -> orchestration integrity failure
unexpected dataset result -> orchestration integrity failure
```

The Fabric backend can use bounded concurrent remote submissions, but it cannot invent additional datasets or skip planner-selected work.

---

## 10. Child Pipeline shape

Recommended reusable child item:

```text
pl_dataset_execute
    parameters:
        framework_pipeline_run_id
        framework_dataset_run_id
        dataset_id
        run_mode
        attempt
        effective_config_hash
        execution_plan_hash

    -> thin SJD / Notebook / planned native activity
    -> released framework + released domain package
    -> verify hashes / load effective config
    -> execute compiled bounded stages
    -> durable target/reconciliation/state semantics
    -> persist terminal DatasetRunAudit
```

Do not copy SCD1/SCD2/CDC/watermark/recovery logic into pipeline expressions.

---

## 11. DEV certification checklist

Before calling this backend `FABRIC PROVEN`, retain one approved DEV evidence bundle containing at least:

```text
framework wheel/version + git SHA
domain artifact/version + git SHA
environment binding identity
Entra principal/approved auth evidence
workspace_id + pipeline_item_id
framework pipeline_run_id + dataset_run_id
Fabric job_instance_id + root_activity_id
ExecutionPlan hash
remote start/end/status
terminal framework DatasetRunAudit
CaptureReceipt where capture is delegated
reconciliation result
state/checkpoint before and after
```

Required failure drills:

```text
provider 429 / Retry-After
remote Pipeline failure
remote cancellation
remote Completed but missing framework outcome
ambiguous target outcome inside child execution
state/checkpoint must not advance on unresolved outcome
```

If the selected tenant/job type rejects per-run parameters, record that evidence and choose a supported invocation pattern before claiming integration complete.

---

## 12. Current evidence boundary

Deterministically implemented/reference-tested:

```text
REST request/response mechanics
Location/job UUID validation
explicit parameter typing
polling + Retry-After
provider error/retry metadata
known job status model
ExecutionPlan/correlation handoff
pluggable ready-wave backend
Completed != semantic success
Deduped fail-closed behavior
native Fabric correlation in StepRunAudit.details
relational FK ordering for parent-side failures
```

Not yet proven in a real Microsoft Fabric environment:

```text
actual token acquisition
workspace/item permissions
Data Pipeline parameter acceptance in the chosen tenant
live POST/poll execution
real job_instance_id/rootActivityId evidence
throttling/capacity behavior
gateway/private-network behavior
real child SJD/Notebook/native activity execution
production control-plane repository wiring
full end-to-end target commit/reconciliation/state handoff
```

Correct label after CI is `IMPLEMENTED + CI PROVEN TRANSPORT/BACKEND`, not `FABRIC PROVEN`.

---

## 13. Microsoft references to revalidate at integration time

Current implementation is based on the Microsoft Fabric v1 Job Scheduler/Data Pipeline REST contracts. Re-check the current Microsoft documentation immediately before a real integration because API capabilities, supported identities, parameter support and item/job types may change.

Useful Microsoft Learn pages:

- Run on-demand item job: `https://learn.microsoft.com/rest/api/fabric/core/job-scheduler/run-on-demand-item-job`
- Get item job instance: `https://learn.microsoft.com/rest/api/fabric/core/job-scheduler/get-item-job-instance`
- Data Pipeline execute job: `https://learn.microsoft.com/rest/api/fabric/datafactory/jobs/run-on-demand-data-pipeline-job`
- Fabric Data Factory REST API capabilities: `https://learn.microsoft.com/fabric/data-factory/pipeline-rest-api-capabilities`
