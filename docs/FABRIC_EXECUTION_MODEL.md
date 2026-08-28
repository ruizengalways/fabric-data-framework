# Fabric Execution Model — fabric-data-framework

Status: Canonical design
Last updated: 2026-08-29

## 1. Purpose

This document defines how provider-neutral framework semantics map onto Microsoft Fabric runtime items.

Core rule:

> Fabric items orchestrate/host physical stages; the framework owns reusable correctness semantics unless a native stage is explicitly capability-certified as equivalent.

Avoid both extremes:

- hundreds of table-specific visual pipelines duplicating logic;
- one opaque giant notebook hiding orchestration/state/recovery.

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

Representative hybrids:

```text
Dataflow Gen2 incremental
  -> landing/staging
  -> CaptureReceipt
  -> framework SCD1/UPSERT
  -> reconciliation/audit

Copy Job/native CDC
  -> native checkpoint/run evidence
  -> CaptureReceipt
  -> canonical CDC events/checkpoints
  -> framework UPSERT/SCD1/SCD2
  -> downstream cdc_checkpoint
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
        +--> thin Notebook
        +--> SQL / provider-native stage
        |
        v
Landing / Bronze / stage + CaptureReceipt
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
Lakehouse / Warehouse + persistent control plane
```

Visual Pipeline is not the source of truth for merge/SCD/delete/recovery/CDC semantics.

## 4. Data Factory Pipeline role

Pipeline owns coarse operational control:

- schedule/trigger/operator entry;
- parameter passing;
- Lookup/ForEach/If/Switch/Until/Invoke Pipeline where appropriate;
- child/dataset execution visibility;
- native activity execution;
- failure routing/correlation;
- coarse capacity/concurrency boundaries.

Framework planner owns dataset eligibility/dependencies/criticality semantics. Fabric backend translates provider-neutral plans rather than reimplementing them in dozens of expressions.

## 5. Spark Job Definition vs Notebook

### Spark Job Definition

Preferred generic headless Spark application entrypoint once the real Fabric backend is implemented.

A SJD should be thin:

```text
read run/dataset identifiers
 -> import released framework/domain wheels
 -> execute compiled bounded stage/plan
 -> persist/correlate outcome
```

Capture/apply algorithms do not live in SJD main files.

### Notebook

Supported for interactive development, diagnostics, smoke/integration tests, bounded operator-assisted execution and justified notebook-specific workloads.

A production Notebook activity is not automatically weak. The anti-pattern is a notebook that embeds reusable algorithms, physical IDs/secrets, scheduling/state/recovery and is the only operational evidence source.

## 6. One-Notebook/SJD child pipeline

A thin child pipeline can legitimately be:

```text
pl_dataset_execute
  -> SJD/Notebook execute_dataset(dataset_id, run_mode, pipeline_run_id)
```

and still be professional when parameters are explicit, package versions immutable, parent fan-out/failure visible, control-plane state/reconciliation durable, code independently tested and physical bindings externalized.

Activity count is not an architecture-quality metric.

## 7. Copy Job role

Use Copy Job when connector/mode is a strong fit for movement/replication/native CDC and native checkpoint semantics are acceptable.

Typical safe plan:

```text
Copy Job capture/replicate
  -> native run/checkpoint correlation
  -> CaptureReceipt
  -> canonical framework semantic stages
```

For native CDC, provider output/checkpoints must be normalized into canonical `CDCEvent`/`CDCCheckpoint` before CDC semantic apply.

Native final apply may be delegated only when a specific profile proves semantic equivalence.

## 8. Copy Activity role

Use Copy Activity when Pipeline-visible movement and framework-controlled source bounds/query are useful:

```text
framework freezes range/predicate
  -> Copy Activity
  -> landing + validated CaptureReceipt
  -> framework apply/reconcile/state
```

This can be preferable to Spark for movement-heavy sources while preserving framework-owned composite watermark/state behavior.

## 9. Dataflow Gen2 role

Dataflow Gen2 is a first-class low-code/Power Query movement/transformation stage, not the universal apply engine.

Current profile:

```text
dataflow_gen2_incremental_bucket_v1
```

certifies bounded Dataflow Gen2 DateTime-bucket incremental capture/staging with FABRIC_NATIVE progress. It does **not** certify composite watermark ordering or framework-equivalent SCD1/UPSERT/SCD2.

Supported topology:

```text
Dataflow Gen2 incremental bucket refresh
   -> staging/Bronze
   -> CaptureReceipt
   -> framework SCD1/UPSERT/SCD2
```

## 10. Mirroring / external CDC

Mirroring can own replicated-source progress where supported. External Debezium/Kafka/database-native CDC can own offsets according to adapter contracts.

For CDC there are two progress concepts:

```text
provider/native source cursor
    !=
framework downstream semantic application checkpoint
```

The provider source cursor remains authoritative for FABRIC_NATIVE/EXTERNAL progress. `cdc_checkpoint` records only the canonical changes successfully applied/reconciled downstream.

## 11. CDC runtime shape

Canonical CDC design: `CDC_DESIGN.md`.

```text
provider envelope
    -> provider adapter
    -> canonical CDCEvent / CDCCheckpoint
    -> bounded normalize/dedupe/order
    -> UPSERT / SCD1 / SCD2
    -> reconcile
    -> cdc_checkpoint(expected_version)
```

Current provider-neutral core rejects ambiguous shared positions, same-key cross-partition ordering and checkpoint regression rather than guessing.

## 12. Snapshot/bootstrap -> CDC

Safe initialization requires a source fence:

```text
retain CDC from S
S <= snapshot consistency checkpoint B
complete snapshot consistent through B
apply/publish snapshot
buffered CDC <= B -> ignore
buffered CDC >  B -> apply
```

Current reference proof rejects partition-set changes during the bootstrap handoff.

A provider adapter must prove how it obtains/retains the fence; the semantic core does not invent one.

## 13. Semantic template vs physical plan

Semantic metadata:

```text
capture=CDC
apply=SCD1
merge_key=[customer_id]
```

Possible physical plan A:

```text
Copy Job native CDC
 -> canonical CDC adapter
 -> framework SCD1
```

Plan B:

```text
Debezium/Kafka
 -> canonical CDC adapter
 -> framework SCD1
```

Plan C:

```text
Spark/database reader
 -> canonical CDC
 -> framework SCD1
```

The semantic contract stays stable.

## 14. Current ExecutionPlan contract

Provider-neutral `ExecutionPlan` / `ExecutionUnit` are implemented/reference-tested and record:

```text
capture_engine
capture_capability_profile
apply_engine
apply_capability_profile
execution kinds/roles
retry/timeout
reconciliation gate
state commit boundary
required bindings
```

Planner can split native capture/staging from framework processing/apply/state, or native apply from framework preparation/finalization when explicitly certified.

Do not silently switch to a weaker physical plan during a production run.

## 15. Recommended Pipeline hierarchy

```text
pl_domain_or_source_batch
  -> initialize/correlate run
  -> resolve metadata execution groups
  -> bounded fan-out
       -> pl_dataset_or_stage_execute
            -> planned native/Spark/Notebook activity
            -> framework state/audit correlation
```

Separate pipelines/execution groups when there is a real operational reason: source/gateway, capture engine, schedule/SLA, capacity, volume, criticality/blast radius or dependency stage.

Do not create separate pipelines merely because tables use SCD1 vs SCD2; those are apply semantics.

## 16. Current proof boundary

Reference/adapter-contract proof currently includes:

- immutable execution planning;
- capture/apply engine separation;
- Copy Job/Copy Activity/Dataflow/Spark capture adapter validation;
- CaptureReceipt conversion;
- canonical CDC semantics + bootstrap;
- downstream CDC checkpoint persistence.

Not yet real-Fabric proven:

- Fabric REST/SDK/CLI transport;
- Pipeline backend;
- authentication/workspace binding;
- actual native run polling/correlation;
- provider CDC envelope adapters against real services;
- capacity/throttling/gateway behavior.

## 17. Near-term Fabric work

1. selected provider CDC envelope mappings/capability profiles;
2. provider native/external offset resume/commit recovery;
3. actual Fabric transports and run polling;
4. Pipeline backend translating ExecutionPlan groups/stages;
5. approved DEV hybrid execution with retained native run evidence;
6. only after real evidence, promote the same immutable artifact through later environments.
