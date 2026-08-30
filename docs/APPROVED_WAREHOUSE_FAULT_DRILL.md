# Approved Fabric Warehouse Ambiguous-COMMIT Fault Drill

Status: runner contract under CI; no real network/driver fault claim exists until an exact-release approved live run is retained.

## Purpose

`integration-warehouse-fault-drill-run` is deliberately separate from the normal
`integration-warehouse-run` stage.

The normal Warehouse stage proves the target mutation + framework marker transaction and
the framework's UNKNOWN recovery contract. Its deterministic success path simulates a
framework acknowledgement loss after the transaction has already returned.

The fault-drill stage exists only for the stronger claim:

```text
a real provider/session/network fault was armed
execute_atomic() actually raised a provider/driver exception
the injector independently verified the intended fault triggered
the committed Warehouse marker resolved the ambiguous outcome
journal -> SUCCEEDED
later re-entry -> SKIP_SUCCEEDED
```

A normal transaction return can never PASS this drill.

## Separate evidence kind

The evidence spec uses:

```text
FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL
```

Do not reuse `FABRIC_WAREHOUSE_TARGET_COMMIT` for this claim. Keeping the checks separate
prevents a deterministic simulated ACK-loss run from being mistaken for a real
network/driver COMMIT fault.

## Prerequisites

The same exact-spec prerequisite manifest must already contain:

```text
FABRIC_ITEM_READ                         PASS
CONTROL_PLANE_CERTIFICATION             PASS
FABRIC_WAREHOUSE_TARGET_COMMIT          PASS
FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL NOT_RUN
```

The normal Warehouse PASS is intentionally required first. A real fault drill is a
failure-injection certification stage, not the first proof that the target path works.

The runner config must name both runtime database URL environment variables and use a
production-eligible control-plane profile. URL **values** remain runtime-only and are
read only after non-secret gates have passed.

## Exact release provenance

Before database URL values are retrieved, the runner validates:

```text
exact environment/domain/framework/release identity
exact DatasetConfig bundle hash
selected dataset in exact release bundle
mutation extension artifact fingerprint in ReleaseManifest
fault injector extension artifact fingerprint in ReleaseManifest
selected fault-drill check still NOT_RUN
normal Warehouse prerequisite PASS
explicit fault-injection authorization
```

## Bounded mutation extension

The target mutation continues to use:

```text
fabric_data_framework.warehouse_mutations
```

The extension receives the framework-owned transactional SQLAlchemy `Connection` and may
perform only the bounded representative mutation. It must not commit, write the
framework marker, mutate the control-plane journal, or decide PASS.

## Bounded fault injector extension

Entry-point group:

```text
fabric_data_framework.warehouse_commit_fault_injectors
```

The registered callable is a factory:

```python
(
    warehouse_engine: sqlalchemy.Engine,
    request: FabricWarehouseCommitFaultRequest,
    payload: Mapping[str, object],
) -> FabricWarehouseCommitFaultInjector
```

The returned controller implements:

```python
arm(request) -> FabricWarehouseCommitFaultArmEvidence
disarm(request) -> None
verify(
    request,
    *,
    observed_exception_type: str | None,
    probe_evidence: TargetCommitProbeEvidence,
) -> FabricWarehouseCommitFaultVerification
```

The extension may install only the approved provider/session fault mechanism needed for
the drill. It does not receive the control-plane URL and it cannot declare framework
PASS.

The first supported phase is:

```text
COMMIT_ACKNOWLEDGEMENT
```

A provider implementation should target loss/ambiguity of the COMMIT acknowledgement,
not arbitrary target corruption.

## Fault identity

An armed fault must retain either:

```text
provider_fault_id
or evidence_reference
```

Verification must correlate to the same identity. If the arm and verification identities
do not match, the drill fails even when a target marker exists.

This prevents an unrelated provider fault from being credited to the exact approved
operation.

## Run config

Example: `examples/dev_warehouse_fault_drill_run.json`.

```json
{
  "check_id": "warehouse.ambiguous-commit",
  "dataset_id": "sales.order",
  "operation_kind": "EVIDENCE_AMBIGUOUS_COMMIT_DRILL",
  "target_reference": "warehouse.dbo.sales_order",
  "mutation_extension": "sales.order.evidence-mutation",
  "mutation_extension_artifact_name": "fabric-customer-0.4.0.dev1-py3-none-any.whl",
  "mutation_payload": {
    "evidence_key": "candidate-0.4.0-sales-order-fault-drill"
  },
  "fault_injector_extension": "sales.order.commit-ack-fault",
  "fault_injector_artifact_name": "fabric-customer-faults-0.4.0.dev1-py3-none-any.whl",
  "fault_payload": {
    "fault_case": "approved-commit-ack-disconnect"
  },
  "marker_table_name": "fabric_framework_operation_commit",
  "marker_schema": "dbo"
}
```

The operation `input_fingerprint` includes both mutation input and fault-drill identity,
so this drill does not collide with the normal Warehouse evidence operation.

Do not put credentials, raw SQL with secrets, connection strings, access tokens, or
secret-bearing provider diagnostics in this file.

## Execution

```bash
fabric-framework integration-warehouse-fault-drill-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/warehouse-prerequisites-merged.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --fault-config evidence/warehouse-fault-drill.json \
  --evidence-reference artifact:warehouse-fault-provider-log \
  --report-output evidence/warehouse-fault-report.json \
  --output evidence/warehouse-fault-partial.json \
  --allow-warehouse-fault-injection
```

The authorization flag is intentionally distinct from `--allow-warehouse-execution`.
Approving a normal target mutation does not implicitly approve network/session fault
injection.

## Execution chain

For a successful real drill:

```text
claim target operation -> EXECUTE
  ↓
construct exact fault request
  ↓
fault injector arm -> armed + durable fault identity
  ↓
execute target mutation + framework marker in one transaction
  ↓
real provider/driver exception observed
  ↓
always disarm injector before marker probe
  ↓
control-plane journal -> UNKNOWN (exception type only)
  ↓
read-only Warehouse marker probe
  matching marker -> COMMITTED
  ↓
UNKNOWN -> SUCCEEDED
  ↓
fault injector verify -> triggered + same fault identity
  ↓
later claim -> SKIP_SUCCEEDED
  ↓
PASS
```

## PASS rule

All of the following are mandatory:

```text
fault armed
execute_atomic actually raised
execution exception type retained; raw message excluded
fault disarmed successfully before probe
fault verification succeeded
fault verification says triggered=true
arm and verification identities match
marker probe = COMMITTED
journal final status = SUCCEEDED
later claim = SKIP_SUCCEEDED
safe retained report exists
```

If any condition is absent, the drill is FAIL.

## Normal return is FAIL

If the target transaction returns normally:

```text
target+marker may be committed
journal may safely reconcile to SUCCEEDED
later claim may be SKIP_SUCCEEDED
```

but the fault-drill result is still:

```text
FAIL / NO_PROVIDER_OR_DRIVER_EXCEPTION
```

Even a buggy or malicious injector that reports `triggered=true` cannot turn a normal
return into a real-fault PASS.

## Marker absence remains fail closed

If execution raises and the marker is absent:

```text
marker absent -> UNRESOLVED
journal remains UNKNOWN
fault drill -> FAIL
no re-execution
```

The fault injector is not an absence certifier. It cannot turn marker absence into
`NOT_COMMITTED`.

The only valid route to `NOT_COMMITTED` after an ambiguous target attempt remains an
independently certified provider/session-specific no-late-commit proof.

## Fault not armed

If `arm()` returns `armed=false`, the framework does not call the target mutation. Because
execution never started, the control-plane operation can be marked `NOT_COMMITTED` from
local pre-execution knowledge. This is not an inference from marker absence.

The drill still FAILs.

## Retained evidence safety

Raw provider/driver exception messages are not retained. The report stores exception
**types only** for execution/disarm/verification failures.

The report may retain:

```text
run_config_hash
operation_key
dataset_run_id
target_reference
fault phase
armed/exception-observed/verified booleans
provider fault ID and/or safe evidence reference
marker reference
probe resolution
final journal status
re-entry action
PASS/FAIL and stable failure reason
approved evidence references
```

## Evidence label

After deterministic CI proves this implementation, the maximum valid label is:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT
```

That label still does **not** mean a real fault happened.

A stronger live claim requires a retained exact-release approved run using a
provider-specific injector in the selected enterprise environment, with durable fault
identity/correlation evidence plus the committed marker and framework journal chain.
