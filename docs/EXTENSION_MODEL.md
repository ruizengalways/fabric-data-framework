# Domain Extension Model — fabric-data-framework

Status: Canonical design  
Last updated: 2026-08-30

## Purpose

The released framework wheel must cover ordinary enterprise ingestion/application patterns without modification while still supporting genuinely irregular datasets.

Custom logic belongs in the domain solution/package and plugs into stable framework extension contracts. It does not fork or patch `fabric-data-framework`.

## Stable logical extension names

Source-controlled metadata/run configuration references a logical extension name, not an arbitrary Python import path.

Example:

```yaml
extensions:
  transform: weird_feed_v1
```

The domain Python package registers that implementation through a controlled registry / Python package entry point, conceptually:

```toml
[project.entry-points."fabric_data_framework.transforms"]
weird_feed_v1 = "fabric_customer.extensions.weird_feed:WeirdFeedTransform"
```

This creates a stable boundary:

```text
metadata logical name
  -> framework extension registry
  -> domain release plugin implementation
```

## Bounded extension contracts

Extension families include:

- capture adapter — unusual source protocol or custom micro-batch acquisition;
- parser/normalizer — irregular binary/text/semi-structured format;
- batch transform — domain-specific transformation before standard apply;
- DQ rule provider — domain/business validation rules;
- specialized apply adapter — only when no standard APPEND/REPLACE/UPSERT/SCD strategy is sufficient;
- capture observer — item-specific post-run facts required to turn provider completion into framework capture evidence;
- Spark execution-data resolver — translation of already-frozen framework bounds/parameters into one Spark Job Definition `executionData` contract;
- Warehouse mutation extension — one bounded representative target mutation executed inside the framework-owned same transaction as the commit marker;
- Warehouse COMMIT fault injector — provider/session-specific machinery for one explicitly authorized ambiguous-COMMIT evidence drill.

Each extension receives typed immutable/framework-owned inputs and returns typed data/evidence. It does not control the entire run lifecycle.

## Approved capture evidence extensions

Stable entry-point groups:

```text
fabric_data_framework.capture_observers
fabric_data_framework.spark_execution_data
```

A customer package can register:

```toml
[project.entry-points."fabric_data_framework.capture_observers"]
"crm.customer.copy-observer" = "fabric_customer.observers:observe_customer_copy"
"crm.customer.spark-observer" = "fabric_customer.observers:observe_customer_spark"

[project.entry-points."fabric_data_framework.spark_execution_data"]
"crm.customer.spark-execution-data" = "fabric_customer.spark:customer_execution_data"
```

Contracts:

```python
(request: FabricCaptureRequest, job: FabricJobInstance) -> FabricCaptureObservation
```

```python
(request: FabricCaptureRequest, binding: FabricSparkJobDefinitionBinding)
    -> Mapping[str, object] | None
```

These extensions fill provider/item-specific gaps only. The framework still owns exact-release/prerequisite validation, physical binding, explicit authorization, provider invocation, one-shot execution, native evidence validation, `CaptureReceipt`, provider correlation, retained evidence safety and PASS/FAIL.

Canonical runbook: `docs/APPROVED_CAPTURE_EVIDENCE.md`.

## Approved Warehouse mutation extension

Stable entry-point group:

```text
fabric_data_framework.warehouse_mutations
```

Customer registration:

```toml
[project.entry-points."fabric_data_framework.warehouse_mutations"]
"sales.order.evidence-mutation" = "fabric_customer.warehouse:mutate_sales_order"
```

Contract:

```python
(
    connection: sqlalchemy.engine.Connection,
    intent: TargetOperationIntent,
    payload: Mapping[str, object],
) -> FabricWarehouseMutationEvidence | None
```

The framework owns:

```text
control-plane target-operation claim/CAS
Warehouse transaction begin/commit
same-transaction marker write
UNKNOWN transition
marker probe
COMMITTED/UNRESOLVED resolution
SUCCEEDED transition
re-entry decision
retained evidence PASS/FAIL
```

The customer extension owns only the representative target mutation performed with the
already-open framework `Connection`. It must not call `commit()`, replace the marker,
change journal state or certify the run.

This is deliberately narrower than handing arbitrary target SQL/lifecycle ownership to
the customer package.

Canonical runbook: `docs/APPROVED_WAREHOUSE_EVIDENCE.md`.

## Approved Warehouse COMMIT fault injector

Stable entry-point group:

```text
fabric_data_framework.warehouse_commit_fault_injectors
```

Customer/provider registration:

```toml
[project.entry-points."fabric_data_framework.warehouse_commit_fault_injectors"]
"sales.order.commit-ack-fault" = "fabric_customer.warehouse_faults:create_commit_ack_fault"
```

The registered callable is a bounded controller factory:

```python
(
    warehouse_engine: sqlalchemy.Engine,
    request: FabricWarehouseCommitFaultRequest,
    payload: Mapping[str, object],
) -> FabricWarehouseCommitFaultInjector
```

The returned controller exposes:

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

The framework still owns the target-operation semantic identity, target transaction,
marker, UNKNOWN transition, read-only probe, journal reconciliation, re-entry decision
and final PASS/FAIL.

The injector can only install/remove/verify the provider-specific fault mechanism for the
explicitly approved drill. It cannot claim that an exception occurred; the framework
must actually observe `execute_atomic()` raising. It cannot turn marker absence into
`NOT_COMMITTED`, and it cannot make a normal transaction return count as a real ambiguous
COMMIT drill.

The first supported fault phase is:

```text
COMMIT_ACKNOWLEDGEMENT
```

Arm and verification evidence must correlate to the same provider fault identity or
retained evidence reference. Both the mutation-extension artifact and fault-injector
artifact must be fingerprinted in the exact release manifest.

Canonical runbook: `docs/APPROVED_WAREHOUSE_FAULT_DRILL.md`.

## Exact extension artifact provenance

For approved evidence, every customer extension wheel or source artifact used by the run must be fingerprinted in `ReleaseManifest.artifact_sha256`.

```text
logical extension name alone          -> insufficient
logical name + exact artifact digest  -> intended artifact provenance
```

The release digest does not itself attest what is installed in the live Fabric Environment. Deployment/environment evidence remains a separate real-service proof.

## Framework-owned boundaries extensions cannot bypass

Custom code may not directly own or override:

- framework watermark/checkpoint commits;
- dataset leases;
- row-accounting invariants;
- reconciliation status;
- final dataset status;
- release/config provenance;
- production secret resolution;
- undeclared target publication;
- semantic strategy changes at runtime;
- approved evidence status or certification level;
- target-operation CAS/retry authority;
- Warehouse transaction commit or same-transaction marker semantics;
- marker-absence retry safety;
- whether an ambiguous-COMMIT fault drill qualifies as PASS.

Where custom code performs a physical write, it must do so through a declared extension contract and participate in the same recovery/idempotency model.

A capture observer cannot claim success independently; its output must pass through `FabricCaptureAdapter` validation before a `CaptureReceipt` exists.

A Warehouse mutation extension cannot claim commit independently; the framework marker and durable target-operation reconciliation remain authoritative evidence.

A Warehouse fault injector cannot self-certify the drill. The framework must observe an actual provider/driver exception, verify the fault correlation, resolve the marker as `COMMITTED`, reconcile `SUCCEEDED`, and observe later `SKIP_SUCCEEDED` before PASS is possible.

## Failure behavior

Extensions must fail explicitly. They must not silently skip malformed records or mutate framework state before the framework can determine recovery behavior.

For approved capture evidence, observer exceptions after provider `Completed` become correlated FAIL evidence when native identity is available.

For approved Warehouse evidence, a mutation/provider exception around transaction execution is treated conservatively as an ambiguous target outcome. The journal becomes `UNKNOWN` and the framework probes the marker. Marker absence remains `UNRESOLVED`; it does not authorize retry.

For the approved Warehouse fault drill, `arm=false` prevents target execution and the drill fails. A normal target return also fails the drill even if the target marker committed. A real execution exception with an absent marker remains `UNKNOWN/UNRESOLVED` and cannot be retried blindly.

## Why this is preferred over framework edits

Routine domain onboarding becomes:

```text
standard dataset
  -> metadata only

standard dataset + business rules
  -> metadata + domain DQ/mapping

provider/item-specific observation
  -> run config + registered customer observer

representative Warehouse mutation evidence
  -> run config + registered customer Warehouse mutation

approved provider-specific ambiguous-COMMIT drill
  -> run config + registered bounded fault injector

true exception
  -> metadata + registered bounded domain extension

new reusable industry-wide pattern
  -> framework feature through normal framework release process
```

Only the last case changes `fabric-data-framework` itself.

The development model is:

```text
fabric-data-framework
  -> immutable framework wheel

fabric-customer
  -> editable source
  -> metadata/config
  -> bounded extension implementation
  -> customer extension wheel/source artifact

exact release manifest
  -> fingerprints framework/domain artifacts used by approved execution
```
