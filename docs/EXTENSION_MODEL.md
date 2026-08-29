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
- Warehouse mutation extension — one bounded representative target mutation executed inside the framework-owned same transaction as the commit marker.

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

## Exact extension artifact provenance

For approved evidence, the customer extension wheel or source artifact used by the run must be fingerprinted in `ReleaseManifest.artifact_sha256`.

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
- Warehouse transaction commit or same-transaction marker semantics.

Where custom code performs a physical write, it must do so through a declared extension contract and participate in the same recovery/idempotency model.

A capture observer cannot claim success independently; its output must pass through `FabricCaptureAdapter` validation before a `CaptureReceipt` exists.

A Warehouse mutation extension cannot claim commit independently; the framework marker and durable target-operation reconciliation remain authoritative evidence.

## Failure behavior

Extensions must fail explicitly. They must not silently skip malformed records or mutate framework state before the framework can determine recovery behavior.

For approved capture evidence, observer exceptions after provider `Completed` become correlated FAIL evidence when native identity is available.

For approved Warehouse evidence, a mutation/provider exception around transaction execution is treated conservatively as an ambiguous target outcome. The journal becomes `UNKNOWN` and the framework probes the marker. Marker absence remains `UNRESOLVED`; it does not authorize retry.

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
