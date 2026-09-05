# MACHINE TOPOLOGY — enterprise Fabric storage and promotion

```yaml
schema: fabric-data-framework-enterprise-topology-v1
updated: 2026-09-06
enterprise_environment_parity:
  environments: [DEV, UAT, PROD]
  same_logical_topology_required: true
  promote_runtime_state_between_environments: false
control_plane:
  canonical_profile: fabric_sql_database_v1
  canonical_store: Fabric SQL Database
  role: operational Framework state
  environment_local: true
  lakehouse_as_enterprise_canonical_control_plane: false
  sqlite_reference_only: true
data_plane:
  bronze: Lakehouse / OneLake
  silver: Lakehouse / OneLake
  gold: Lakehouse or optional Fabric Warehouse
  quarantine_full_payload: governed OneLake/Lakehouse
warehouse:
  mandatory: false
  preferred_role: SQL-first Gold / dimensional analytical serving
ci_cd:
  promote:
    - framework/customer code
    - DatasetConfig and execution-group policies
    - DQ/reconciliation rules
    - Notebook/Pipeline definitions
    - SQL control-plane schema/migrations
    - non-secret logical binding templates
  never_promote_as_runtime_state:
    - pipeline_run rows
    - dataset_run rows
    - watermarks/checkpoints
    - retry/reprocess history
    - operation journal state
    - credentials/tokens
    - physical item/resource IDs
    - business data
```

## Non-negotiable invariant

Enterprise DEV is a smaller instance of the production architecture, not a different storage architecture. Do not use Lakehouse/Delta as the canonical DEV control plane and then switch to Fabric SQL Database in UAT/PROD.

Framework generic backend qualification can support other relational products, but the Microsoft Fabric enterprise reference topology is explicitly:

```text
control_plane_profile = fabric_sql_database_v1
DEV/UAT/PROD            = same control-plane backend class
```

## Medallion vs products

```text
Bronze / Silver / Gold = analytical data maturity layers
Lakehouse / Warehouse / SQL Database = workload/storage engines
```

Canonical split:

```text
Fabric SQL Database -> operational control plane
Lakehouse / OneLake -> Bronze/Silver/Gold data plane + quarantine detail
Fabric Warehouse    -> optional SQL-first Gold serving
```

## Concurrency reason

Delta optimistic concurrency can reject overlapping concurrent writes/merges after another transaction changes files seen by a writer. This is correct data protection but is not the preferred semantics for frequent small operational state transitions from many parallel dataset workers.

For multi-table Pipelines, business work may be concurrent while each worker also records `dataset_run`, `step_run`, watermark/checkpoint, retry lineage and operation-journal state. The enterprise reference therefore keeps these operational records in Fabric SQL Database.

## Code contract

Implementation owner:

```text
src/fabric_data_framework/control_plane/enterprise.py
```

It locks the enterprise Fabric profile name to `fabric_sql_database_v1` and fails closed if an enterprise topology attempts to substitute a reference/Lakehouse profile.

Human architecture guide:

```text
docs/human/ENTERPRISE_FABRIC_ARCHITECTURE.md
```

## Release/evidence boundary

This topology decision does not itself prove a real Fabric SQL Database deployment, external security/resilience controls, UAT/PROD promotion, or release readiness. Those remain evidence-backed claims only.
