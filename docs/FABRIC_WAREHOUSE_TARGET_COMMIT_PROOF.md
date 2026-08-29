# Fabric Warehouse Target Commit Proof

Status: implemented provider contract / deterministic CI target; not yet Warehouse-proven.

## Purpose

The framework already has a durable semantic target-operation journal. That journal answers:

```text
Is this logical target operation allowed to execute, skip, or reconcile?
```

It cannot by itself prove whether an ambiguous physical Fabric Warehouse transaction actually committed.

This runbook defines the provider-specific target proof layer for Fabric Warehouse.

## Two independent responsibilities

```text
framework control plane
  -> TargetOperationIntent
  -> claim / CAS
  -> EXECUTE or RECONCILE_REQUIRED

target Fabric Warehouse
  -> target mutation
  -> target-side operation marker
  -> same explicit transaction
```

The control plane remains the semantic retry gate. The Warehouse marker is target-native commit evidence, not a second framework control plane.

## Atomic target unit

The preferred execution shape is:

```text
BEGIN TRAN
  target mutation
  INSERT fabric_framework_target_operation_marker(...operation_key...)
COMMIT TRAN
```

The marker uses the existing stable `TargetOperationIntent.operation_key` and repeats the semantic identity fields for diagnostic validation.

Microsoft Fabric Warehouse currently documents ACID explicit transactions: operations inside one transaction succeed or roll back as one atomic unit. This is why the marker and mutation must use the same target connection/transaction.

`FabricWarehouseMarkerStore.execute_atomic()` implements this contract through one SQLAlchemy transaction and an injected mutation callback receiving that same connection.

## Marker schema

`build_fabric_warehouse_operation_marker_table()` defines the canonical logical marker columns but performs **no DDL**.

Runtime requires the target table to be deployed already. This avoids silently changing a production Warehouse during target execution.

The logical columns are:

```text
marker_version
operation_key
dataset_id
operation_kind
target_reference
effective_config_hash
input_fingerprint
semantic_version
owner_dataset_run_id
attempt
native_operation_id
query_label
detail
recorded_at
```

Warehouse-persisted types are intentionally compatible with the current Fabric Warehouse persisted type surface: varchar/integer/datetime2-style values rather than unsupported persisted `nvarchar`, `text`, or `datetimeoffset` assumptions.

`recorded_at` is UTC. The persisted database value is timezone-free UTC wall-clock time because Warehouse uses `datetime2`; the framework reattaches UTC on read.

## Do not use a Warehouse constraint as the execution lock

The marker table does not rely on an enforced primary/unique key to serialize target writes.

The framework's existing target-operation CAS decides who has the `EXECUTE` claim. This matters because Fabric Warehouse constraint semantics can include `NOT ENFORCED` constraints; target proof must not silently depend on a uniqueness guarantee the provider does not enforce.

If a consistent committed marker is already present when `execute_atomic()` is called, the mutation is not executed again. This is a secondary idempotence safety belt, not a replacement for the framework claim/reconciliation state machine.

## Ambiguous outcome probe

`FabricWarehouseTargetCommitProbe` implements the provider-neutral `TargetCommitProbe` contract.

### Marker exists

If a committed marker is visible and its semantic fields match the framework request:

```text
resolution = COMMITTED
```

The evidence reference is stable:

```text
fabric-warehouse-marker:<schema.table>:<operation_key>
```

A retained target-native statement/operation ID can also be attached when the mutation implementation can capture one.

### Marker absent

Marker absence by itself means:

```text
UNRESOLVED
```

It does **not** mean `NOT_COMMITTED`.

A connection can fail at an awkward boundary, and this portable contract does not assume that an absent marker immediately proves the server cannot still complete/commit a transaction.

To resolve absence to `NOT_COMMITTED`, an environment/provider-specific `FabricWarehouseAbsenceCertifier` must supply independent evidence that the prior transaction cannot commit later and retry is safe.

```text
marker absent
+ independent safe-to-retry proof
  -> NOT_COMMITTED

marker absent
+ no proof / inconclusive proof
  -> UNRESOLVED
```

That evidence must retain an `evidence_reference` or native operation ID when it grants retry safety.

## Query Insights and query labels

Warehouse Query Insights is useful secondary evidence. It exposes completed request history including `distributed_statement_id`, `label`, command and timing information, and Warehouse supports query labels for supported statement shapes.

However current Microsoft documentation warns that completed queries can take up to roughly 15 minutes to appear in Query Insights / Monitor under load.

Therefore:

```text
Query Insights correlation != immediate commit truth
```

`FabricWarehouseSecondaryCorrelationReader` is diagnostic only. Finding a correlated query cannot override a missing marker into `COMMITTED`, and not finding a query cannot override it into `NOT_COMMITTED`.

Query labels should be used where the actual DML statement shape supports them, but the framework does not require every mutation implementation to manufacture a label.

## Journal reconciliation

Canonical ambiguous recovery flow:

```text
TargetOperationIntent
  -> claim EXECUTE
  -> Warehouse target transaction
       mutation + marker
  -> client result ambiguous
  -> framework operation remains/turns UNKNOWN
  -> FabricWarehouseTargetCommitProbe
       read marker
  -> probe_and_reconcile_target_operation
       COMMITTED     -> durable SUCCEEDED
       NOT_COMMITTED -> durable NOT_COMMITTED
       UNRESOLVED    -> durable UNKNOWN / blocked
```

Only durable `NOT_COMMITTED` may later reopen execution through the existing CAS claim logic.

## Marker lifecycle and retention

The target-side marker is evidence for semantic target operations. Do not delete markers merely because a dataset run ended.

A production retention policy must be longer than every supported replay/retry/reconciliation window and must account for audit requirements. Deleting a marker too early can turn a previously provable committed operation into an ambiguous one.

The framework does not automate marker cleanup in this slice.

## Transaction scope limitation

The atomic guarantee applies only when the selected target mutation and marker write are both valid inside the same Fabric Warehouse explicit transaction.

If an operation uses a provider path that cannot share that target transaction, do not label it covered by this contract. It needs its own provider-native proof mechanism.

## Microsoft product facts to revalidate during live certification

Deployment/live certification should revalidate current Microsoft documentation for:

- Fabric Data Warehouse explicit ACID transactions;
- T-SQL surface area for the selected target DML;
- Warehouse persisted data types;
- query labels for the selected statements;
- Query Insights request-history behavior and latency;
- connection/session behavior under the exact driver and network failure modes used by the runtime.

## Current proof level

After deterministic tests pass, the correct label is:

```text
IMPLEMENTED + CI PROVEN PROVIDER COMMIT CONTRACT
```

It is not yet:

```text
FABRIC WAREHOUSE PROVEN
```

Real proof still requires approved DEV execution retaining:

- actual Warehouse connection/auth identity;
- real target mutation and marker in one explicit transaction;
- ambiguous client/network failure drills around COMMIT;
- marker visibility after reconnect;
- independently certified marker-absence behavior for any path that wants to emit `NOT_COMMITTED`;
- optional Query Insights statement/label correlation;
- framework target-operation journal transitions and exact dataset/native correlation.
