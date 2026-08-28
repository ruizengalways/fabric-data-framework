# Fabric Execution Model — fabric-data-framework

Status: Canonical design
Last updated: 2026-08-28

## 1. Purpose

This document defines how provider-neutral framework semantics map onto Microsoft Fabric runtime items.

Core rule:

> Fabric items orchestrate/host physical stages; the framework owns reusable correctness semantics unless a native stage is explicitly capability-certified as equivalent.

Avoid both extremes:

- hundreds of table-specific visual pipelines duplicating logic;
- one opaque giant notebook that hides orchestration/state/recovery.

## 2. Framework-first, stage-level model

A dataset lifecycle is not owned by one physical engine:

```text
capture / movement
    -> normalize / transform
    -> apply
    -> reconcile
    -> state / audit
```

Different Fabric/runtime surfaces may own different stages.

Representative hybrid:

```text
Dataflow Gen2 incremental
  -> landing/staging
  -> CaptureReceipt
  -> framework SCD1
  -> reconciliation/audit
```

Likewise:

```text
Copy Job -> Bronze -> framework UPSERT/SCD1/SCD2
Copy Activity -> Bronze -> framework apply
Mirroring -> replicated state -> framework canonicalization/apply
External CDC -> Bronze -> framework CDC normalization/apply
```

Progress ownership is independent from apply ownership.

## 3. Fabric runtime layers

```text
Trigger / schedule / operator request
        |
        v
Fabric Data Factory Pipeline
  coarse orchestration + activity visibility
        |
        +--> Copy Job / Copy Activity
        +--> Dataflow Gen2
        +--> Spark Job Definition
        +--> Notebook
        +--> SQL / database-native stage
        |
        v
Landing / Bronze / stage + CaptureReceipt where capture is external/native
        |
        v
released framework wheel + released domain wheel
        |
        v
EffectiveDatasetConfig / immutable ExecutionPlan
        |
        v
non-delegated semantic stages
        |
        v
Lakehouse / Warehouse / persistent control plane
```

The visual pipeline is not the source of truth for merge/SCD/delete/recovery semantics.

## 4. Data Factory Pipeline role

Pipeline owns coarse operational control:

- schedule/trigger/operator entry;
- parameter passing;
- Lookup/ForEach/If/Switch/Until/Invoke Pipeline control flow as appropriate;
- child-dataset execution visibility;
- native activity execution;
- failure routing/correlation;
- coarse capacity/concurrency boundaries.

The framework planner owns dataset eligibility/dependencies/criticality semantics. The Fabric adapter translates the provider-neutral plan rather than reimplementing it in dozens of expressions.

## 5. Spark Job Definition vs Notebook

### Spark Job Definition

Preferred generic headless Spark application entrypoint once the adapter is implemented.

A SJD should be thin:

```text
read run/dataset identifiers
 -> import released framework/domain wheels
 -> execute compiled bounded plan/stage
 -> persist/correlate outcome
```

Capture/apply algorithms do not live in the SJD main file.

### Notebook

Supported for:

- interactive development;
- diagnostics;
- smoke/integration tests;
- bounded operator-assisted execution;
- justified notebook-specific workloads.

A production Notebook activity is not automatically weak. The anti-pattern is a notebook that embeds reusable algorithms, physical IDs/secrets, scheduler/state/recovery and is the only operational evidence source.

## 6. One-Notebook/SJD child pipeline

A thin child pipeline can legitimately be:

```text
pl_dataset_execute
  -> SJD/Notebook execute_dataset(dataset_id, run_mode, pipeline_run_id)
```

and still be professional when:

- parameters are explicit;
- package versions are immutable;
- dataset-level parent fan-out/failure is visible;
- framework control plane persists steps/state/reconciliation;
- code is independently tested;
- physical bindings are externalized.

Activity count is not an architecture quality metric.

## 7. Copy Job role

Use Copy Job when its connector/mode is a strong fit for movement/replication and its native checkpoint semantics are acceptable.

Do not assume global support for every CDC/current-state/history requirement. Copy Job capability must be modeled by named profile/connector/version as needed.

Typical safe plan:

```text
Copy Job capture/replicate
  -> native run correlation + CaptureReceipt
  -> framework downstream semantic stages
```

Native Copy Job final apply may be delegated only when a specific profile proves semantic equivalence.

## 8. Copy Activity role

Use Copy Activity when Pipeline-visible movement and framework-controlled source bounds/query are useful:

```text
framework freezes range/predicate
  -> Copy Activity
  -> landing + CaptureReceipt
  -> framework apply/reconcile/state
```

This can be preferable to Spark for movement-heavy sources while preserving framework-owned composite watermark/state behavior.

## 9. Dataflow Gen2 role

Dataflow Gen2 is a first-class low-code/Power Query movement/transformation stage, not the universal apply engine.

Current implemented named profile:

```text
dataflow_gen2_incremental_bucket_v1
```

represents current DateTime-bucket incremental capture/staging behavior with FABRIC_NATIVE progress ownership.

It explicitly does **not** certify:

- composite watermark ordering;
- framework-equivalent SCD1;
- framework-equivalent UPSERT;
- framework-equivalent SCD2.

Therefore this is a supported target topology:

```text
Dataflow Gen2 incremental bucket refresh
   -> staging/Bronze
   -> CaptureReceipt
   -> framework SCD1
```

The same pattern will support framework UPSERT/SCD2 once those target execution paths are certified.

## 10. Mirroring/external CDC

Mirroring can own replicated-source progress where supported. External Debezium/Kafka can own CDC offsets according to the adapter contract.

In both cases, downstream framework canonicalization/apply is independent from capture ownership.

No second competing framework checkpoint is created for the same native/external physical capture.

## 11. Semantic template vs physical plan

Semantic metadata:

```text
capture=WATERMARK
apply=SCD1
merge_key=[customer_id]
ordering=(modified_at, source_version)
```

Possible physical plan A:

```text
Dataflow Gen2 capture
 -> framework SCD1
```

Plan B:

```text
Copy Activity capture
 -> framework SCD1
```

Plan C:

```text
Spark/framework capture + SCD1
```

The semantic contract stays stable.

## 12. Current ExecutionPlan contract

Provider-neutral `ExecutionPlan` and `ExecutionUnit` are implemented/reference-tested.

Current planner can split:

```text
native capture/stage unit
  +
framework Spark processing/apply/state unit
```

It records physical kind/roles/retry/timeout/reconciliation/state boundaries and required bindings.

Next evolution:

- explicit apply executor/native-apply delegation field;
- richer source-boundary/idempotency/run correlation;
- Fabric backend translation.

Do not silently switch from one physical plan to a weaker one during a production run.

## 13. Recommended Pipeline hierarchy

### Domain/source parent

```text
pl_domain_batch
  -> initialize run/request
  -> resolve execution groups/datasets
  -> bounded fan-out
       -> pl_dataset_execute(A)
       -> pl_dataset_execute(B)
       -> pl_dataset_execute(C)
  -> aggregate/finalize
```

### Dataset child

```text
pl_dataset_execute
  parameters: pipeline_run_id, dataset_id, run_mode, reprocess_request_id?
  -> execute compiled stage plan
       Copy / Dataflow / SJD / Notebook / SQL
  -> correlate outcome
```

### Reprocess

```text
pl_reprocess
  -> validate request/scope/mode
  -> invoke normal strategy implementation
  -> retain original/replay lineage
```

Do not duplicate strategy logic in a separate recovery pipeline.

## 14. FULL -> REPLACE examples

### Native movement + framework validation/publication

```text
Copy Activity/Job
 -> isolated stage + receipt
 -> SJD/framework DQ/completeness/reconciliation
 -> SQL/Spark safe publication
```

### Single Spark application

```text
SJD execute FULL -> REPLACE
```

Both are valid when the same semantic guards/evidence are preserved.

## 15. Observability

Fabric-visible evidence should eventually include:

- parent pipeline run;
- child dataset activity/run;
- native Copy/Dataflow/SJD/Notebook run ID;
- duration/status/failure routing.

Framework control-plane evidence includes:

- effective config hash;
- execution engine/profile and concrete plan;
- CaptureReceipt/source boundary;
- row/quarantine/mutation metrics;
- reconciliation;
- framework state before/after;
- error/retry/reprocess lineage;
- framework/domain/release provenance.

Correlation IDs bridge both views.

## 16. Environment/library contract

Production Spark execution should reference a published stable Fabric Environment containing exact framework/domain wheels and approved dependencies/runtime/compute configuration.

Development iteration convenience is not the production library-publish contract.

Environment/runtime identity should be captured in deployment/run evidence when the adapter exposes it.

## 17. Configuration/bindings

Three layers:

```text
source-controlled semantic metadata
deployed immutable semantic snapshot/hash
environment-specific physical binding + operational overrides
```

Fabric Variable Library may participate in the physical binding layer for suitable non-secret values. It must not become an alternate place to mutate merge keys, apply strategy, engine profile or schema contract.

Secrets stay in approved identity/connection/secret authority.

## 18. Anti-patterns

Avoid:

- one bespoke pipeline/notebook per table when metadata is the only difference;
- one opaque notebook as scheduler + runtime + state store;
- encoding SCD/merge/delete rules in Pipeline expressions;
- assuming native `merge`/`incremental`/`SCD2` names equal framework semantics;
- maintaining a framework watermark beside a native Copy/Dataflow checkpoint;
- hard-coded workspace/lakehouse IDs or secrets in reusable code;
- using notebook logs as the only audit/state system;
- adding activities solely to make a pipeline canvas look sophisticated;
- duplicating retry/reconciliation logic in Pipeline and Python;
- hidden fallback to a semantically weaker engine.

## 19. Current implementation evidence

Implemented/reference-tested in the current hardening branch:

- provider-neutral execution-plan contracts;
- orchestration planner/reference backend split;
- native-capture + framework-processing plan shape;
- execution engine/progress owner metadata;
- named engine capability profiles;
- `Dataflow Gen2 incremental bucket -> framework SCD1` planner/reference composition;
- CaptureReceipt contract/control-plane persistence;
- FULL/REPLACE and SNAPSHOT_DIFF reference execution;
- SCD1/SCD2 portable apply semantics.

Latest fully green implementation suite before final docs audit: 91 tests (`33172961692`).

Not yet proven:

- real Fabric Pipeline backend;
- real Copy Job/Activity/Dataflow adapter invocation;
- real SJD/Environment wheel execution;
- persistent production control-plane store;
- enterprise identity/network/capacity behavior.

## 20. Next Fabric milestones

1. define explicit apply executor/native apply delegation in `ExecutionPlan`;
2. implement Fabric adapter contracts for Copy Job, Copy Activity, Dataflow Gen2 and SJD;
3. implement recovery/CDC/UPSERT so hybrid capture has robust downstream semantics;
4. deploy exact wheel into an approved DEV Environment;
5. run at least one real native capture -> CaptureReceipt -> framework SCD1/UPSERT scenario;
6. retain Fabric run IDs and reconcile with control-plane evidence;
7. update readiness audit with actual product limitations/evidence;
8. only then consider release/promotion scope.
