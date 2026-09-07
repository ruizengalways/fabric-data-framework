# Fabric Pipeline child contract

Audience: framework maintainers and implementation/domain engineers building the reusable Fabric Data Pipeline child used by the framework dispatcher or certification fixtures.

## Why the contract exists

Fabric provider status `Completed` is not enough to prove framework semantic success. The remote child must persist an exact framework dataset outcome for the same framework-generated run identity before the parent accepts success.

Canonical framework boundary:

```text
fabric_data_framework.execution.pipeline_child
```

The framework owns correlation, config/plan validation and durable outcome identity. The implementation owns the bounded project-specific physical work invoked inside that contract.

## Required remote parameters

The reusable child accepts these framework-owned values:

```text
framework_pipeline_run_id
framework_dataset_run_id
dataset_id
run_mode
attempt
effective_config_hash
execution_plan_hash
```

Do not add passwords, bearer tokens, database URLs or connection strings to this external parameter bag. Secret/runtime material belongs to the approved runtime credential mechanism.

## Execution sequence

```text
Pipeline receives framework parameters
-> child obtains approved runtime credentials
-> construct exact ControlPlaneRepository
-> load deployed implementation DatasetConfig
-> parse FabricPipelineChildRequest
-> validate effective_config_hash
-> recompute/validate execution_plan_hash
-> bounded implementation executor performs physical work
-> executor returns FabricPipelineChildResult
-> framework persists exact DatasetRunAudit/outcome
-> child finishes
-> parent reads durable outcome by framework_dataset_run_id
```

Public helpers:

```python
from fabric_data_framework.execution import (
    execute_pipeline_child,
    pipeline_child_request_from_parameters,
)
```

`execute_pipeline_child(...)` fails before data-plane execution when the deployed config hash or execution-plan hash does not match the invocation.

## Provider success vs framework success

Treat these as different facts:

```text
Fabric job status
Framework DatasetDispatchOutcome
```

Valid outcomes include:

```text
Fabric Completed + Framework SUCCEEDED
Fabric Completed + Framework FAILED
```

A Fabric `Completed` run with no matching durable framework outcome is fail-closed, not PASS.

## Executor boundary

The bounded implementation executor may return semantic execution facts such as:

```text
status
row accounting
mutation counts
error code/message
retryable
```

It must not author framework release-readiness PASS evidence. Certification/release proof authority remains framework-owned.

## Certification reference implementation

Framework certification fixtures provide their own reference child/driver/observer behavior inside `fabric-data-framework`. A real implementation repo follows the same public child contract but owns its own physical project deployment and bindings.

Environment-local item IDs and credentials remain outside source-controlled reusable framework contracts.
