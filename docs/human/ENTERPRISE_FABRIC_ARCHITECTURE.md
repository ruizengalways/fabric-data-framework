# Enterprise Fabric architecture — control plane vs medallion data plane

This document is the canonical storage/topology guide for the enterprise reference implementation.

## 1. DEV is not a downgraded architecture

DEV, UAT and PROD use the same logical topology and the same control-plane backend class. They differ in physical resource IDs, credentials, capacity, scale and data only.

```text
Git / immutable release inputs
        |
        +--> DEV  Fabric SQL Database + Lakehouse/optional Warehouse
        +--> UAT  Fabric SQL Database + Lakehouse/optional Warehouse
        +--> PROD Fabric SQL Database + Lakehouse/optional Warehouse
```

Do not develop against a Lakehouse control table and then switch to SQL Database in UAT/PROD. That changes transaction/concurrency semantics during promotion and is not the enterprise reference pattern.

Canonical Framework contract:

```text
control_plane_profile = fabric_sql_database_v1
enterprise environments = DEV / UAT / PROD
```

`sqlite_reference_v1` remains local/CI reference only. Other relational profiles may be qualified by Framework, but the Microsoft Fabric enterprise reference topology uses Fabric SQL Database consistently across DEV/UAT/PROD.

## 2. Bronze / Silver / Gold are data maturity layers, not database products

Medallion labels describe analytical/business data maturity:

```text
source
  -> Bronze: raw/source-faithful history
  -> Silver: normalized, deduplicated, DQ governed, SCD/current-state models
  -> Gold: consumption models, facts/dimensions/KPIs/semantic serving
```

Lakehouse, Warehouse and SQL Database describe workload engines. They are not competing names for Bronze/Silver/Gold.

Recommended enterprise split:

```text
CONTROL PLANE                         DATA PLANE
Fabric SQL Database                  OneLake / Lakehouse
-------------------                  -------------------
dataset definitions                  Bronze raw/history
pipeline_run                         Silver normalized/SCD
 dataset_run                         quarantine payloads
 step_run                            large reconciliation detail
 watermark                           Gold analytical data
 retry/reprocess lineage                    |
 target operation journal                  +--> Gold Lakehouse OR Warehouse
 reconciliation state
 quarantine batch metadata
```

## 3. What each Fabric store is for

### Fabric SQL Database — operational control plane

Use it for small, frequently changing operational state that needs relational transaction semantics, compare-and-swap/version checks, point lookup and concurrent writers.

Typical Framework tables:

```text
dataset
pipeline_run
dataset_run
step_run
watermark / CDC checkpoint
reprocess_request
dataset_attempt_lineage
target_operation + target_operation_event
reconciliation
quarantine_batch metadata/reference
```

The control database is authoritative operational truth. DEV/UAT/PROD each own an independent database. Runtime rows never promote between environments.

### Lakehouse — scalable engineering and medallion data plane

Use Lakehouse/Delta for business data and large append/merge workloads:

```text
Bronze source-faithful data
Silver normalized/current/SCD data
Gold data when Lakehouse serving is sufficient
full quarantine row payloads
large reconciliation detail/history
control-plane analytical history copies
```

A Lakehouse is excellent for large Delta operations; it is not the enterprise reference store for high-frequency Framework run-state mutations.

### Warehouse — optional SQL-first Gold/serving engine

Warehouse is optional. Use it when Gold is primarily relational analytics / SQL / dimensional serving:

```text
facts + dimensions
SQL-first ELT/serving
complex relational BI queries
consumer-facing star schemas
```

A valid topology can be all-Lakehouse Bronze/Silver/Gold. Another valid topology is Bronze/Silver Lakehouse plus Gold Warehouse. Warehouse is not mandatory merely because the project uses medallion architecture.

## 4. Why Lakehouse control tables can conflict under concurrent Pipeline runs

Delta uses optimistic concurrency rather than classic OLTP row locking. Two writers may both read a valid snapshot, then one commits first. If the second transaction depends on files changed by the first, the second write can fail with a concurrency conflict.

That behavior protects data correctness, but it is a poor fit for a busy operational control plane where many workers repeatedly perform small state transitions such as:

```text
RUNNING -> SUCCEEDED / FAILED
claim/update watermark
insert step audit
record retry lineage
record operation journal state
```

For a 100-table execution group with bounded parallelism, many workers can legitimately update control state at the same time. A Delta table can therefore become a contention point even when the business-table work itself succeeds.

The enterprise reference avoids this mismatch by keeping operational state in Fabric SQL Database and business/quarantine payloads in OneLake.

## 5. CI/CD promotion contract

Promote definitions, not runtime state.

Promoted through Git/CI/CD:

```text
Framework/customer code
DatasetConfig and execution-group policy
DQ/reconciliation rules
Notebook/Pipeline definitions
SQL control-plane schema/migrations
non-secret logical bindings/templates
```

Environment-specific and never copied from DEV to UAT/PROD:

```text
pipeline_run rows
dataset_run rows
watermarks/checkpoints
retry/reprocess history
operation journal state
credentials/tokens
physical Fabric item/resource IDs
business data
```

A deployment must create/update the same logical component types in every stage and then resolve that stage's physical bindings.

## 6. Failure/recovery implication

If business data mutation succeeds but control-state persistence cannot be proven, Framework must fail closed rather than invent success. This is why the control plane needs strong operational semantics.

Unknown/ambiguous target commit is handled through the operation journal and reconciliation before retry. DQ quarantine payloads stay in governed data-plane storage; SQL control plane stores summary and lineage references rather than full sensitive business rows.

## 7. Reference topology

```text
DEV/UAT/PROD (same logical topology)

Fabric SQL Database
  framework_control_<env>

Lakehouse / OneLake
  Bronze
  Silver
  quarantine/detail/history
  Gold when appropriate

Optional Fabric Warehouse
  Gold dimensional / SQL serving

Fabric Pipelines / Notebooks / Jobs
  use the same source-controlled definitions
  bind to environment-local resources at deployment/runtime
```

## 8. Decision rule

Use this shortcut:

```text
operational Framework state       -> Fabric SQL Database
large engineering/business data   -> Lakehouse
SQL-first analytical Gold serving -> optional Warehouse
```

Do not infer that medallion architecture eliminates the need for an operational database. Medallion describes the data plane; the Framework control plane is a separate operational workload.
