# Fabric Pipeline Child Contract

Audience: Framework maintainers and Customer/domain engineers building the reusable Fabric Data Pipeline item used by the Framework dispatcher and certification lane.

## Why this contract exists

A Fabric Data Pipeline reaching provider status `Completed` is not enough to prove Framework semantic success.  The remote child must persist an exact `DatasetRunAudit` / `DatasetDispatchOutcome` for the same Framework-generated dataset run before the parent runner accepts the job.

The generic Framework boundary is implemented by:

```text
fabric_data_framework.execution.pipeline_child
```

Customer/domain code owns the physical data mutation.  Framework owns correlation, exact config/plan validation and durable outcome identity.

## The seven remote parameters

Every reusable child Pipeline must accept and forward exactly these Framework-owned values:

```text
framework_pipeline_run_id
framework_dataset_run_id
dataset_id
run_mode
attempt
effective_config_hash
execution_plan_hash
```

Do not add database URLs, passwords, bearer tokens or connection strings to this external Framework parameter bag.  Environment-specific secret material belongs to the child runtime credential mechanism.

## Child execution sequence

The recommended remote worker sequence is:

```text
Pipeline receives seven Framework parameters
  -> Notebook/activity obtains approved runtime credentials
  -> construct exact released ControlPlaneRepository
  -> load exact Customer/domain DatasetConfig bundle
  -> parse FabricPipelineChildRequest
  -> Framework validates deployed DatasetConfig hash
  -> Framework recomputes execution_plan_hash
  -> Customer/domain executor performs bounded physical mutation
  -> executor returns FabricPipelineChildResult
  -> Framework persists exact DatasetRunAudit
  -> Fabric child finishes
  -> parent reads DatasetDispatchOutcome by framework_dataset_run_id
```

The public helper is:

```python
from fabric_data_framework.execution import (
    execute_pipeline_child,
    pipeline_child_request_from_parameters,
)
```

`execute_pipeline_child(...)` fails before data-plane execution if the deployed effective config hash or execution-plan hash does not match the invocation.

## Provider success versus Framework success

The parent `FabricPipelineBackend` treats these as separate facts:

```text
Fabric job status
Framework DatasetDispatchOutcome
```

Therefore these are valid and important outcomes:

```text
Fabric Completed + Framework SUCCEEDED
Fabric Completed + Framework FAILED
```

The second case is required for fail-closed scenarios such as reconciliation rejection and retryable semantic failures.

A Fabric `Completed` result with no durable Framework outcome is a failure:

```text
FABRIC_PIPELINE_RESULT_MISSING
```

## Customer executor boundary

A Customer/domain executor returns `FabricPipelineChildResult` with semantic execution facts such as:

```text
status
row_accounting
mutation counts
error_code / error_message
retryable
```

It must not construct release-readiness PASS evidence.  Release and certification proof remains Framework-owned.

## Certification reference

The reference Customer repo must provide a deployable child Pipeline/Notebook implementation that follows this contract.  It should be reusable across the representative certification datasets instead of creating one ad-hoc Pipeline per test.

The Pipeline/Notebook definition is environment-local because physical workspace/item bindings and credential references differ by environment.  The Customer repo should keep the source template and deployment/runbook; real IDs and secret values must stay out of source control.
