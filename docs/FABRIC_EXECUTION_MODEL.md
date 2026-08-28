# Fabric Execution Model — fabric-data-framework

Status: Canonical design
Last updated: 2026-08-29

## 1. Purpose

This document maps provider-neutral framework semantics onto Microsoft Fabric runtime items.

Core rule:

> Fabric items orchestrate/host physical stages. Reusable correctness semantics remain framework-owned unless a native stage is explicitly capability-certified as equivalent.

Avoid both hundreds of table-specific pipelines duplicating logic and one giant opaque notebook hiding orchestration/state/recovery.

## 2. Stage-level lifecycle

```text
capture / movement
    -> normalize / transform
    -> apply
    -> reconcile
    -> state / audit
```

Different surfaces may own different stages. Progress ownership is independent from apply ownership.

Representative hybrid:

```text
Dataflow Gen2 incremental
  -> validated native run evidence
  -> CaptureReceipt
  -> framework UPSERT/SCD1
  -> reconciliation/state/audit
```

## 3. Runtime topology

```text
Trigger / schedule / operator request
        |
        v
Fabric Data Factory Pipeline
  coarse orchestration + native activity visibility
        |
        +--> Copy Job / Copy Activity
        +--> Dataflow Gen2
        +--> Spark Job Definition
        +--> Notebook
        +--> SQL/database-native stage
        |
        v
landing / Bronze / stage
        |
        v
provider native run evidence + CaptureReceipt
        |
        v
released framework wheel + released domain wheel
        |
        v
non-delegated semantic stages
        |
        v
Lakehouse / Warehouse / persistent control plane
```

The visual pipeline is not the semantic source of truth for merge/SCD/delete/recovery.

## 4. Data Factory Pipeline role

Pipeline owns coarse operational control:

- schedule/trigger/operator entry;
- parameter passing;
- native activity invocation;
- child execution visibility;
- coarse fan-out/failure routing;
- capacity/concurrency boundaries;
- provider run correlation.

The framework planner owns dataset eligibility/dependency/criticality semantics. A future Fabric Pipeline backend should translate the provider-neutral plan rather than duplicating those decisions in visual expressions.

## 5. Spark Job Definition and Notebook

### Spark Job Definition

Preferred generic headless Spark application surface for framework-controlled stages.

A production SJD should remain thin:

```text
receive dataset/run/plan identifiers
  -> import pinned framework/domain wheels
  -> execute bounded compiled stage/plan
  -> persist framework evidence
```

The **capture adapter contract for Spark Job execution kind is implemented**. The real SJD REST/deployment/run transport is not yet implemented/proven.

### Notebook

Supported for interactive development, diagnostics, smoke/integration tests and justified bounded production activity. The anti-pattern is a notebook that embeds platform scheduler/state/recovery, physical secrets/IDs and all reusable algorithms.

## 6. Thin child pipeline is acceptable

```text
pl_dataset_execute
  -> SJD/Notebook execute_dataset(dataset_id, run_mode, pipeline_run_id)
```

This is professional when parameters/versioning/failure visibility/control-plane evidence/bindings are explicit. Activity count is not an architecture quality metric.

## 7. Copy Job

Use Copy Job when connector/mode/native checkpoint behavior is a good movement fit.

Framework integration boundary now exists:

```text
compiled COPY_JOB capture unit
  -> FabricCaptureRequest
  -> CopyJobCaptureAdapter
  -> injected provider transport
  -> FabricNativeRunEvidence
  -> CaptureReceipt
  -> framework downstream semantics
```

The adapter contract is deterministically tested. A real Copy Job API/run transport remains unimplemented.

## 8. Copy Activity

Use Copy Activity when framework-owned source bounds/query and Pipeline-visible movement are useful.

```text
framework freezes lower/upper boundary
  -> Copy Activity transport
  -> observed boundary must equal request
  -> CaptureReceipt
  -> framework apply/reconcile/state
```

The current adapter explicitly fails if a supposedly successful FRAMEWORK-owned bounded run reports different source bounds.

## 9. Dataflow Gen2

Dataflow Gen2 is a first-class Power Query movement/transformation stage, not a universal apply semantic.

Named profile:

```text
dataflow_gen2_incremental_bucket_v1
```

certifies only:

```text
WATERMARK-like DateTime bucket capture/staging
FABRIC_NATIVE progress ownership
no composite framework watermark guarantee
no generic native UPSERT/SCD1/SCD2 equivalence
```

Current supported reference topology:

```text
Dataflow Gen2 incremental
  -> DataflowGen2CaptureAdapter evidence boundary
  -> CaptureReceipt
  -> framework UPSERT or SCD1
```

The compiled Dataflow capture unit is directly certified against the adapter contract with deterministic fake transport evidence. Real Dataflow API execution is still required for Fabric evidence.

## 10. Mirroring and external CDC

Mirroring/provider replication can own source progress where supported. Governed Debezium/Kafka can own CDC offsets. Downstream framework normalization/apply remains independent.

No competing framework checkpoint is created for the same native/external physical capture.

CDC canonical normalization/checkpoint semantics are the next implementation area.

## 11. ExecutionPlan contract

Current `ExecutionPlan` is immutable and records:

```text
dataset/run mode
capture strategy
apply strategy
concrete capture engine/profile
concrete apply engine/profile
execution units + roles
retry/timeout/reconciliation/state boundaries
required bindings
```

Planner can produce:

```text
native capture/stage unit
  + framework normalize/validate/apply/reconcile/state unit
```

or other stage splits where apply is independently delegated.

Apply-executor separation is already implemented; it is no longer a future planning gap.

## 12. Fabric capture adapter contract

Current adapter package proves the translation boundary without pretending to implement Microsoft Fabric networking/auth/API calls.

```text
FabricCaptureRequest
FabricCaptureTransport protocol
FabricNativeRunEvidence
FabricCaptureAdapter
```

Concrete wrappers:

```text
CopyJobCaptureAdapter
CopyActivityCaptureAdapter
DataflowGen2CaptureAdapter
SparkJobCaptureAdapter
```

Fail-closed requirements:

- adapter engine/kind matches compiled unit;
- capture unit contains EXTRACT/STAGE;
- pure capture adapter cannot silently own APPLY/PUBLISH/RECONCILE/COMMIT_STATE;
- FAILED/CANCELLED/UNKNOWN status => no receipt;
- landing/source/snapshot/kind mismatch => failure;
- FRAMEWORK-owned bounded source range mismatch => failure;
- successful native run ID is retained in receipt.

## 13. Recovery interaction

Provider/API errors are inputs to the framework recovery model, not justification for blind retries.

```text
explicit transient error -> bounded retry
permanent/unclassified   -> stop
ambiguous target commit  -> reconcile before retry
```

Unknown commit resolution:

```text
COMMITTED     -> converge success/no duplicate write
NOT_COMMITTED -> retry may proceed
UNRESOLVED    -> fail/stop
```

For native-progress capture, replay/resume must respect provider checkpoint authority and retained `CaptureReceipt` evidence.

## 14. Recommended Pipeline hierarchy

```text
pl_domain_batch
  -> initialize pipeline run/request
  -> resolve execution group/datasets
  -> bounded fan-out
       -> provider-native capture where selected
       -> framework/Spark execution for non-delegated stages
  -> aggregate terminal outcomes
```

Do not generate one permanent bespoke pipeline per ordinary table when metadata can select the same execution pattern.

## 15. Many-table grouping

Group by real operational boundaries:

- source/gateway/concurrency limit;
- capture engine/profile;
- schedule/SLA;
- volume/runtime class;
- dependency stage;
- criticality/blast radius;
- capacity/network boundary.

Apply semantics may affect runtime grouping, but they do not define ingestion architecture.

## 16. Release/deployment boundary

Target production path remains:

```text
GitHub Release framework wheel
  -> Fabric Environment/custom library
  -> Full Publish
  -> domain SJD/Notebook/Pipeline item
  -> same immutable wheel DEV/UAT/PROD
```

Physical workspace/item/connection identities are environment bindings. Runtime control-plane state is not promoted.

## 17. Current evidence boundary

Implemented/reference-tested:

- ExecutionPlan stage split;
- independent apply engine;
- Dataflow hybrid planner path;
- Fabric capture request/evidence adapter layer;
- provider status/evidence fail-closed behavior;
- generic recovery/unknown-outcome core.

Not yet real-Fabric proven:

- Pipeline backend;
- REST/SDK/CLI transports;
- real Copy Job/Copy Activity/Dataflow/SJD run correlation;
- wheel Environment deployment in the current hardening milestone;
- Lakehouse/Warehouse mutation/unknown-outcome recovery drills.

## 18. Next Fabric execution milestone

After CDC and strategy-specific recovery are sufficiently complete:

```text
real company DEV Fabric estate
  -> deploy exact framework wheel
  -> execute one native capture stage
  -> retain actual native run id/evidence
  -> create CaptureReceipt
  -> execute framework UPSERT/SCD1
  -> reconcile/audit
```

That proof must remain clearly separate from enterprise IAM/network/capacity controls supplied by the company platform.
