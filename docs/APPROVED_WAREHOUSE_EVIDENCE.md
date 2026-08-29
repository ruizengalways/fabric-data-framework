# Approved Fabric Warehouse Commit and Recovery Evidence

Status: implemented runner contract; real approved Fabric Warehouse execution is still required.

## Purpose

`integration-warehouse-run` executes one exact-release representative Warehouse target
mutation and retains proof that:

```text
1. target mutation + framework operation marker share one transaction;
2. the durable control-plane target-operation journal owns retry authority;
3. UNKNOWN is reconciled from provider-native marker evidence;
4. a committed operation converges to SUCCEEDED;
5. later re-entry is SKIP_SUCCEEDED, not a second mutation.
```

The runner also supports the harder case where `execute_atomic()` raises a provider or
driver exception. It records `UNKNOWN` using only the exception type and probes the
Warehouse marker. It never blindly retries an ambiguous mutation.

## Evidence boundary

There are two different ambiguity proofs and they must not be confused.

### A. Simulated framework acknowledgement loss

When the Warehouse transaction returns successfully, the runner deliberately behaves as
if the framework lost the acknowledgement:

```text
claim EXECUTE
  -> Warehouse transaction commits mutation + marker
  -> framework deliberately records UNKNOWN
  -> marker probe = COMMITTED
  -> journal = SUCCEEDED
  -> later claim = SKIP_SUCCEEDED
```

This proves the end-to-end recovery contract against the real target/control-plane
services used by the approved run.

It is **not** evidence that the network or SQL driver actually failed during COMMIT.

### B. Provider/driver exception around `execute_atomic()`

If the call itself raises:

```text
execute_atomic raises
  -> journal = UNKNOWN
  -> read-only marker probe
      matching marker -> COMMITTED -> SUCCEEDED
      marker absent   -> UNRESOLVED -> remain UNKNOWN
```

A retained approved run in which a real injected network/session fault causes the
exception and the marker subsequently proves `COMMITTED` is the stronger ambiguous
COMMIT drill. CI can exercise this contract with deterministic doubles, but cannot claim
the real fault happened.

## Prerequisites

The same exact-spec prerequisite manifest must already contain:

```text
FABRIC_ITEM_READ                  PASS
CONTROL_PLANE_CERTIFICATION      PASS
FABRIC_WAREHOUSE_TARGET_COMMIT   NOT_RUN
```

The runner refuses automatic mutation reruns after substantive Warehouse evidence.

`ApprovedIntegrationRunnerConfig` must name both runtime URL environment variables:

```json
{
  "control_plane_profile": "fabric_sql_database_v1",
  "control_plane_database_url_env_var": "FABRIC_CONTROL_PLANE_DATABASE_URL",
  "warehouse_database_url_env_var": "FABRIC_WAREHOUSE_DATABASE_URL"
}
```

Only the environment-variable **names** belong in source control. URL values remain
runtime-only.

The selected control-plane profile must be production eligible.

## Exact release and extension provenance

Before secret-bearing URL values are retrieved, the runner verifies:

```text
runner/spec/release environment-domain-framework-release identity
config_bundle_hash(current DatasetConfig bundle) == ReleaseManifest bundle hash
selected dataset exists in the exact release bundle
mutation extension artifact name exists in ReleaseManifest.artifact_sha256
explicit --allow-warehouse-execution authorization
```

The artifact fingerprint records the intended exact customer extension artifact used by
approved execution. It does not by itself prove which artifact is installed in a live
Fabric Environment; deployment/environment evidence remains separate.

## Bounded Warehouse mutation extension

Entry-point group:

```text
fabric_data_framework.warehouse_mutations
```

Contract:

```python
(
    connection: sqlalchemy.engine.Connection,
    intent: TargetOperationIntent,
    payload: Mapping[str, object],
) -> FabricWarehouseMutationEvidence | None
```

The framework opens and commits the transaction. The extension receives the existing
transactional `Connection` and performs only the representative target mutation. It
must not call `commit()` or declare evidence PASS.

The framework then writes the operation marker on the **same connection** before the
transaction is committed.

Customer package example:

```toml
[project.entry-points."fabric_data_framework.warehouse_mutations"]
"sales.order.evidence-mutation" = "fabric_customer.warehouse:mutate_sales_order"
```

The customer extension wheel/source artifact must be fingerprinted in the exact release
manifest.

## Run config

Example:

```json
{
  "check_id": "warehouse.commit",
  "dataset_id": "sales.order",
  "operation_kind": "EVIDENCE_MERGE",
  "target_reference": "warehouse.dbo.sales_order",
  "mutation_extension": "sales.order.evidence-mutation",
  "extension_artifact_name": "fabric-customer-0.4.0.dev1-py3-none-any.whl",
  "mutation_payload": {
    "evidence_key": "candidate-0.4.0-sales-order"
  },
  "marker_table_name": "fabric_framework_operation_commit",
  "marker_schema": "dbo"
}
```

`mutation_payload` is deterministic JSON-compatible semantic input. Its canonical hash
becomes the target operation `input_fingerprint`; together with dataset/config/target/
operation kind it produces the durable `operation_key`.

Choose a bounded representative payload that is safe in the approved DEV target. Do
not put credentials, connection strings or arbitrary secret-bearing SQL in this file.

## Marker table prerequisite

The approved runner never provisions the Warehouse marker table. The table must already
exist as part of explicit deployment/migration:

```text
dbo.fabric_framework_operation_commit
```

(or the explicitly configured approved schema/table name).

This preserves the rule that runtime evidence execution does not silently create
production schema.

## Execution

```bash
fabric-framework integration-warehouse-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/prerequisites-merged.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --warehouse-config evidence/warehouse-run.json \
  --evidence-reference artifact:warehouse-query-and-marker-evidence \
  --report-output evidence/warehouse-report.json \
  --output evidence/warehouse-partial.json \
  --allow-warehouse-execution
```

## PASS rule

A normal fresh PASS requires:

```text
fresh journal claim = EXECUTE
same-transaction mutation + marker committed
framework UNKNOWN state created deliberately
marker probe = COMMITTED
journal converged to SUCCEEDED
later claim = SKIP_SUCCEEDED
safe report retained
```

A recovery of a previously interrupted approved invocation may start from
`RECONCILE_REQUIRED` or `SKIP_SUCCEEDED`, but the marker must still prove the same exact
semantic operation before PASS evidence can be reconstructed.

## Marker absence rule

This remains intentionally strict:

```text
matching marker -> COMMITTED
marker absent   -> UNRESOLVED
```

The approved runner has no built-in `NOT_COMMITTED` shortcut. `NOT_COMMITTED` requires a
separate independently certified provider/session-specific no-late-commit absence proof.

Therefore:

```text
marker absent != safe to retry
```

## Retained evidence safety

Raw SQLAlchemy/provider exception messages are not retained by the approved runner or
generic target-probe fallback. Only the exception type may be persisted in the
ambiguity path because driver errors can contain connection/credential material.

The PASS report retains:

```text
run_config_hash
operation_key
dataset_run_id
target_reference
marker_reference
native_operation_id if supplied
whether this invocation executed the marker transaction
initial journal action
ambiguity origin
exception type only when applicable
probe resolution
final journal status
re-entry action
evidence references
```

## Evidence label

Until retained exact-release approved Warehouse service execution exists, the correct
label is:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
```

A real run of the simulated framework-ACK path can prove the same-transaction marker and
recovery chain on the selected service. A true network/driver ambiguous-COMMIT claim
still requires retained real fault-injection evidence; CI does not prove that fault.
