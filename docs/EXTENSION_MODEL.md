# Domain Extension Model — fabric-data-framework

Status: Canonical design  
Last updated: 2026-08-30

## Purpose

The released framework wheel must cover ordinary enterprise ingestion/application patterns without modification while still supporting genuinely irregular datasets.

Custom logic belongs in the domain solution/package and plugs into stable framework extension contracts. It does not fork or patch `fabric-data-framework`.

## Stable logical extension names

Source-controlled dataset metadata references a logical extension name, not an arbitrary Python import path.

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

The domain release identity therefore versions both ordinary metadata and any exceptional custom implementation.

## Bounded extension contracts

Initial extension families include:

- capture adapter — unusual source protocol or custom micro-batch acquisition;
- parser/normalizer — irregular binary/text/semi-structured format;
- batch transform — domain-specific transformation before standard apply;
- DQ rule provider — domain/business validation rules;
- specialized apply adapter — only when no standard APPEND/REPLACE/UPSERT/SCD strategy is sufficient;
- capture observer — item-specific post-run facts required to turn provider completion into framework capture evidence;
- Spark execution-data resolver — translation of already-frozen framework bounds/parameters into one Spark Job Definition `executionData` contract.

Each extension receives typed immutable framework/provider inputs and returns typed data/evidence. It does not control the entire run lifecycle.

## Approved capture evidence extensions

Two dedicated entry-point groups are stable framework contracts:

```text
fabric_data_framework.capture_observers
fabric_data_framework.spark_execution_data
```

A customer package can register implementations such as:

```toml
[project.entry-points."fabric_data_framework.capture_observers"]
"crm.customer.copy-observer" = "fabric_customer.observers:observe_customer_copy"
"crm.customer.spark-observer" = "fabric_customer.observers:observe_customer_spark"

[project.entry-points."fabric_data_framework.spark_execution_data"]
"crm.customer.spark-execution-data" = "fabric_customer.spark:customer_execution_data"
```

The capture observer contract is:

```python
(request: FabricCaptureRequest, job: FabricJobInstance) -> FabricCaptureObservation
```

The Spark execution-data contract is:

```python
(request: FabricCaptureRequest, binding: FabricSparkJobDefinitionBinding)
    -> Mapping[str, object] | None
```

These extensions fill provider/item-specific gaps only. The framework still owns:

```text
exact-release/prerequisite validation
physical item binding
explicit mutation authorization
REST invocation semantics
one-shot capture execution
FabricNativeRunEvidence validation
CaptureReceipt construction
provider/native correlation validation
retained evidence safety
PASS/FAIL decision
```

For approved evidence, the customer extension wheel or source artifact used by the run must be fingerprinted in `ReleaseManifest.artifact_sha256`. A logical extension name without exact artifact provenance is insufficient.

Canonical runbook:

```text
docs/APPROVED_CAPTURE_EVIDENCE.md
```

## Framework-owned boundaries that extensions cannot bypass

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
- approved evidence status or certification level.

Where custom code performs a physical write, it must do so through a declared extension contract that returns publication evidence to the framework and participates in the same recovery/idempotency model.

A capture observer is specifically **not** allowed to claim success independently. Its output still passes through the concrete transport and `FabricCaptureAdapter` validation before a `CaptureReceipt` exists.

## Failure behavior

Extensions must fail explicitly. They must not silently skip malformed records or mutate target/state before the framework can determine whether the operation is retryable or recoverable.

For approved capture evidence, observer exceptions after provider `Completed` are retained as correlated FAIL evidence when the native job identity is available. They are never promoted to PASS.

## Why this is preferred over framework edits

Routine domain onboarding becomes:

```text
standard dataset
  -> metadata only

standard dataset + business rules
  -> metadata + domain DQ/mapping

provider/item-specific observation
  -> metadata/run config + registered customer observer extension

true exception
  -> metadata + registered domain extension

new reusable industry-wide pattern
  -> framework feature through normal framework release process
```

Only the last case changes `fabric-data-framework` itself.

The development model is therefore:

```text
fabric-data-framework
  -> immutable framework wheel

fabric-customer
  -> editable source
  -> metadata/config
  -> bounded extension implementation
  -> customer extension wheel/source artifact

exact release manifest
  -> fingerprints both artifacts used by approved execution
```
