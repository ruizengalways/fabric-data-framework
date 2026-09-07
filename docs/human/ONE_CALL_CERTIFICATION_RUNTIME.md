# One-call Fabric certification runtime contract

Audience: Framework developers and Fabric operators using framework-owned certification against exact framework wheel bytes.

This document exists so a new engineer can understand the runtime/Control Plane behavior without relying on chat history.

## Public entry points

Preferred installed-wheel entry point:

```python
from fabric_data_framework.certification import certify_installed, print_certification_summary

report = certify_installed(
    spark=spark,
    certification_root="/lakehouse/default/Files/framework_cert",
)
print_certification_summary(report)
```

The older convenience entry point remains available:

```python
from fabric_data_framework.certification import certify
report = certify(spark=spark)
```

Both belong to `fabric-data-framework`. `fabric-customer` is not the owner of this lifecycle.

## Conventional certification root

```text
/lakehouse/default/Files/framework_cert/
  CANDIDATE.json
  exactly one fabric_data_framework-*.whl
  customer-inputs/        # optional LEGACY DIRECTORY NAME
```

The physical directory/CLI spelling `customer-inputs` is retained for backward compatibility. Its meaning is now:

> optional framework certification integration-input bundle.

It does **not** mean the `fabric-customer` repository owns or must generate the bundle.

No optional integration bundle means bounded/self-contained certification only. The Framework does not scan the workspace and does not guess a SQL Database, Warehouse or Pipeline.

## Runtime values are explicit, not source-controlled

An optional integration runner config may declare allowed runtime variable names such as:

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

The mapping is runtime-only. Secret values must not be committed into integration input bundles or retained in certification reports/evidence.

## Scoped environment bridge

Approved Framework runners accept an explicit `environ` mapping. Legacy integration extension entry points may also read `os.environ` directly.

The public one-call API therefore uses one scoped rule:

```text
exact runner-config declared names
  + runtime_environment/current process values
  -> one resolved runtime mapping
  -> declared names temporarily mirrored into os.environ
  -> approved runners / legacy bounded extensions execute
  -> previous os.environ values restored before certify() returns
```

Only names declared by the exact runner config are mirrored. The public API does not copy arbitrary integration metadata into process environment.

The Fabric REST token follows the same resolved runtime. If the configured token name is absent in a Fabric Notebook, the public API may obtain the current NotebookUtils `pbi` token for the duration of the call.

This bridge changes execution visibility only. It does not make secret values eligible for retained reports or evidence references.

## First-time dedicated Control Plane bootstrap

A newly created certification SQL Database may need:

```text
1. current Framework Control Plane schema
2. exact certification semantic dataset definitions required by the integration bundle
```

A schema-only migration can be insufficient because the Framework intentionally fails when an exact deployed dataset definition is required but absent.

For a newly provisioned **dedicated certification database**, use explicit authorization:

```python
report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
    allow_control_plane_migration=True,
)
```

The first-time path remains fail-closed and ordered:

```text
exact Framework bounded suite
  -> all bounded checks must PASS
  -> optional integration INPUTS identity must match the same Framework wheel
  -> resolve configured Control Plane runtime URL
  -> apply current baseline schema
  -> idempotently materialize exact certification semantic metadata
  -> verify materialized config bundle hash
  -> run normal unified certification stages
```

If bounded certification fails, the first-time bootstrap does not create/mutate the SQL Control Plane.

If the optional integration bundle does not match the exact Framework wheel, bootstrap fails before semantic metadata deployment.

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

The reusable Pipeline child must receive exactly the Framework execution identity fields required by the current contract and execute through the Framework child/runtime boundary. The parent runner then reads the durable Framework outcome for the same generated dataset run identity.

Therefore:

```text
Fabric Completed + no matching Framework outcome != PASS
Fabric Completed + Framework FAILED          != success business path
Fabric Completed + exact Framework SUCCEEDED  can satisfy the provider/framework gate
```

Optional integration extensions can return semantic execution facts only. They cannot author release-readiness PASS.

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

It does not select/freeze a candidate, publish `v0.4.0`, or change release governance.

Every real-Fabric result belongs only to the exact wheel bytes identified by `CANDIDATE.json` and the wheel SHA256. Any executable Framework source change requires a new exact artifact and new real-Fabric execution for those bytes.
