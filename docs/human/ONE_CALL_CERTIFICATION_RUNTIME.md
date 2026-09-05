# One-call Fabric certification runtime contract

Audience: Framework developers and Fabric operators using `fabric_data_framework.certification.certify` with an exact Customer certification bundle.

This document exists so a new engineer can understand the runtime/Control Plane behavior without relying on chat history.

## Public entry point

```python
from fabric_data_framework.certification import certify, print_certification_summary

report = certify(spark=spark)
print_certification_summary(report)
```

The conventional root is:

```text
/lakehouse/default/Files/framework_cert/
  CANDIDATE.json
  exactly one fabric_data_framework-*.whl
  customer-inputs/                     # optional
```

No `customer-inputs/` means bounded certification only. The Framework does not scan the workspace and does not guess a SQL Database, Warehouse or Pipeline.

## Runtime values are explicit, not source-controlled

The exact Customer `runner-config.json` owns the allowed runtime variable names. The reference Customer bundle normally declares:

```text
FABRIC_ACCESS_TOKEN
CONTROL_PLANE_DATABASE_URL
WAREHOUSE_DATABASE_URL
WAREHOUSE_ADMIN_DATABASE_URL
```

Actual values come from either an explicit mapping:

```python
runtime_environment = {
    "CONTROL_PLANE_DATABASE_URL": control_plane_database_url,
    "WAREHOUSE_DATABASE_URL": warehouse_database_url,
}

report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
)
```

or, when the mapping is omitted, the current process environment.

The mapping is runtime-only. Values must not be committed into the Customer bundle or retained in certification reports/evidence.

## Why the public API temporarily mirrors declared names into process environment

Approved Framework runners accept an explicit `environ` mapping. Customer/domain Python extension entry points may also need the same runtime value and historically read `os.environ` directly.

The public one-call API therefore uses one scoped rule:

```text
exact runner-config declared names
  + runtime_environment/current process values
  -> one resolved runtime mapping
  -> declared names temporarily mirrored into os.environ
  -> approved runners + exact Customer extensions execute
  -> previous os.environ values restored before certify() returns
```

Only names declared by the exact runner config are mirrored. The public API does not copy arbitrary Customer metadata into process environment.

The Fabric REST token follows the same resolved runtime. If the configured token name is absent in a Fabric Notebook, the public API may obtain the current NotebookUtils `pbi` token for the duration of the call.

This runtime bridge changes execution visibility only. It does not make secret values eligible for retained reports, source-controlled input bundles or evidence references.

## First-time dedicated Control Plane bootstrap

A newly created certification SQL Database has two separate requirements before Pipeline/Warehouse stages can use it:

```text
1. current Framework Control Plane schema
2. exact Customer semantic dataset definitions
```

A schema-only migration is insufficient because `SqlAlchemyControlPlaneRepository.get_dataset()` deliberately fails when the exact released dataset definition has not been deployed/materialized.

For a newly provisioned **dedicated certification database**, use:

```python
report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
    allow_control_plane_migration=True,
)
```

The explicit first-time path is fail-closed and ordered:

```text
exact Framework bounded suite
  -> all bounded checks must PASS
  -> exact Customer INPUTS identity must match the same Framework wheel
  -> resolve the configured Control Plane runtime URL
  -> apply current baseline schema
  -> idempotently materialize exact Customer semantic metadata
  -> verify materialized config bundle hash
  -> run the normal unified certification stages
```

`materialize_semantic_metadata` preserves environment-local runtime state while updating the released semantic definition tables.

If bounded certification fails, the first-time bootstrap does not create/mutate the SQL Control Plane.

If the Customer bundle does not match the exact Framework wheel, bootstrap fails before semantic metadata deployment.

If the Control Plane runtime URL is absent, bootstrap is not invented against another database; the later Control Plane stage remains not ready.

## Normal reruns

After first-time bootstrap, use:

```python
report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
)
```

with:

```text
allow_control_plane_migration=False
```

Normal certification must not silently migrate or redeploy a shared/production Control Plane just to obtain a green result.

## Pipeline durable-outcome boundary

A Fabric Data Pipeline reaching provider `Completed` is not enough for `fabric.pipeline` PASS.

The reusable Pipeline child must receive exactly:

```text
framework_pipeline_run_id
framework_dataset_run_id
dataset_id
run_mode
attempt
effective_config_hash
execution_plan_hash
```

and must execute through:

```python
execute_pipeline_child(...)
```

The Framework validates the exact deployed DatasetConfig/effective config/execution plan and persists the exact terminal `DatasetRunAudit`. The parent runner then reads the durable `DatasetDispatchOutcome` for the same generated dataset run ID.

Therefore:

```text
Fabric Completed + no matching Framework outcome != PASS
Fabric Completed + Framework FAILED          != success business path
Fabric Completed + exact Framework SUCCEEDED  can satisfy the provider/framework gate
```

Customer/domain code returns semantic execution facts only. It cannot author release-readiness PASS.

## Warehouse Admin boundary

Ordinary live certification authorization does not imply session termination permission.

If an approved ambiguous-COMMIT drill requires an Admin connection/session termination, supply its separately declared runtime value and explicitly set:

```python
allow_warehouse_session_termination=True
```

Never enable this against a shared or production Warehouse merely to fill a certification result.

## Release boundary

The one-call runner always keeps:

```text
release_authorized = false
```

It does not select/freeze a candidate, publish `v0.4.0`, change `release_allowed`, or migrate the Customer production pin.

Every real-Fabric result belongs only to the exact wheel bytes identified by `CANDIDATE.json` and the wheel SHA256. Any Framework source change requires a new exact main artifact and new real-Fabric execution for those bytes.
