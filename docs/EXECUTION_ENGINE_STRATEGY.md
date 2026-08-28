# Execution Engine Strategy — fabric-data-framework

Status: Canonical design
Last updated: 2026-08-29

## 1. Product requirement

`fabric-data-framework` is a reusable semantic/runtime product, not a wrapper around one Microsoft Fabric execution surface.

Core DE semantics must have provider-neutral framework implementations. Fabric-native features are used as stage delegates when a capability profile proves the requested scope.

ADR 0009 remains governing architecture: **framework-first semantics with stage-level native delegation**.

## 2. Independent concerns

```text
Capture semantics
  FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM

Capture/movement executor
  FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 |
  SPARK | FABRIC_MIRRORING | EXTERNAL_CDC | SQL | CUSTOM

Apply semantics
  APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF

Apply executor
  framework/Spark by default
  native delegate only with explicit semantic-equivalence profile

Capture progress owner
  FRAMEWORK | FABRIC_NATIVE | EXTERNAL
```

`execution.engine` describes capture/movement. `execution.apply_engine` independently describes final apply.

The immutable `ExecutionPlan` records concrete capture/apply engines and profiles before execution. `AUTO` is a source-controlled resolution request, not a runtime hidden switch.

## 3. Framework-first fallback invariant

```text
semantic contract
    +-> framework portable implementation
    +-> optional certified provider delegate
```

Native feature evolution should normally change a capability profile/adapter/plan, not force domain metadata to redefine business data semantics.

## 4. Current apply defaults

Framework reference implementations currently cover:

```text
REPLACE
UPSERT
SCD1
SCD2
SNAPSHOT_DIFF
```

APPEND identity semantics remain future work.

Generic native profiles currently do **not** claim arbitrary final-target UPSERT/SCD1/SCD2 equivalence. Unless a named apply profile explicitly certifies the strategy, the conservative apply path is framework/Spark.

## 5. Native capture services

### Copy Job

Use for supported provider-managed full/incremental/native-CDC movement where its connector/product semantics fit. Progress is commonly FABRIC_NATIVE.

Safe composition:

```text
Copy Job
  -> validated native evidence
  -> CaptureReceipt
  -> framework normalize/apply/reconcile
```

### Copy Activity

Useful when the framework computes/fixes an exact source predicate/range and Pipeline performs transport.

```text
framework freezes lower/upper range
  -> Copy Activity
  -> observed range must match request
  -> CaptureReceipt
  -> framework apply/state
```

This pattern naturally supports FRAMEWORK progress ownership.

### Dataflow Gen2

Useful for Power Query connector/folding/reshape and Fabric-native DateTime-bucket incremental behavior.

Named profile:

```text
DATAFLOW_GEN2 / dataflow_gen2_incremental_bucket_v1
```

certifies:

```text
capture strategy: WATERMARK-like incremental staging
progress owner: FABRIC_NATIVE
composite framework watermark: not certified
native generic UPSERT/SCD1/SCD2: not certified
```

Valid hybrid:

```text
Dataflow Gen2 incremental
  -> CaptureReceipt
  -> framework UPSERT/SCD1/SCD2
```

Dataflow bucket replacement is not generic SCD1.

### Spark

Spark/framework is the conservative programmable fallback for source-boundary logic, composite ordering, custom parsing, deterministic current/history correctness and complex recovery.

It is not required for every transport workload.

### Mirroring / external CDC

Provider/external service may own source replication/offset progress while framework remains responsible for canonicalization/apply/audit for non-delegated stages.

## 6. Capability profiles

Capabilities are keyed by:

```text
(engine, profile_name)
```

because provider support varies by connector, source configuration, target, runtime mode and product version.

Rules:

- defaults are conservative;
- named profile requires explicit engine;
- unsupported strategy/progress/order combination fails before mutation;
- capture certification does not imply apply certification;
- profile lacking composite ordering must reject metadata that requires it;
- native apply requires an explicit apply-strategy certification;
- provider marketing names do not establish semantic equivalence.

## 7. Progress ownership

Every physical capture has one authoritative checkpoint owner.

```text
Copy Activity with framework-defined bounds -> FRAMEWORK
Copy Job native incremental/CDC             -> FABRIC_NATIVE
Dataflow Gen2 incremental                   -> FABRIC_NATIVE
Debezium/Kafka                              -> EXTERNAL or explicit consumer owner
```

Progress ownership does not imply apply ownership.

## 8. CaptureReceipt handoff

Native/provider stages participate in the common framework through evidence rather than by importing framework code inside each activity.

`CaptureReceipt` records:

- framework dataset-run correlation;
- semantic capture strategy;
- physical engine/progress owner;
- native run ID;
- source/landing reference;
- rows read/written;
- source boundaries when meaningful;
- snapshot identity/completeness when meaningful;
- external checkpoint when meaningful;
- schema/timestamps.

## 9. Fabric adapter architecture

Current provider boundary:

```text
ExecutionPlan capture unit
    -> FabricCaptureRequest
    -> FabricCaptureTransport
    -> FabricNativeRunEvidence
    -> FabricCaptureAdapter validation
    -> CaptureReceipt
```

Concrete wrappers:

```text
CopyJobCaptureAdapter
CopyActivityCaptureAdapter
DataflowGen2CaptureAdapter
SparkJobCaptureAdapter
```

`FabricAdapterRegistry` is explicit. The framework does not silently construct credentials/workspace clients.

### Adapter fail-closed rules

- engine/kind must match the compiled unit;
- pure capture requires EXTRACT/STAGE;
- pure capture adapter may not silently own APPLY/PUBLISH/RECONCILE/COMMIT_STATE;
- FAILED/CANCELLED/UNKNOWN native runs do not produce receipt;
- wrong landing, source, snapshot or execution kind fails;
- FRAMEWORK-owned bounded movement must report exactly the requested bounds.

These are deterministic adapter-contract guarantees, not real Fabric integration evidence.

## 10. Recovery and physical execution

Provider transport errors are not automatically retried merely because an API call failed.

The generic recovery runtime distinguishes:

```text
RETRYABLE
NON_RETRYABLE
UNKNOWN_OUTCOME
```

An ambiguous target commit must be reconciled before another mutation:

```text
COMMITTED     -> converge success
NOT_COMMITTED -> retry may proceed
UNRESOLVED    -> stop
```

For native-progress capture, downstream failure recovery must use provider receipt/checkpoint semantics rather than advancing a competing framework watermark.

## 11. Many-table topology

Use metadata plus a small number of execution groups rather than one bespoke pipeline per table or one opaque giant pipeline.

Group by real operational boundaries:

- source/gateway/concurrency;
- capture engine/profile;
- schedule/SLA;
- volume/runtime class;
- dependency stage;
- criticality/blast radius;
- capacity/network boundary.

SCD1/SCD2/UPSERT are apply semantics and do not define ingestion topology.

## 12. Bounded extension points

Metadata references stable logical extension names for exceptional capture/parser/transform/DQ/specialized apply behavior.

Extensions may not bypass lineage, accounting, quarantine, reconciliation, progress authority, publication, secrets/bindings or audit.

## 13. Current implementation evidence

Latest hardening evidence before docs synchronization:

```text
commit a5da06294dfba0c5ae756dcc1d8814931feebec7
run 33179754372
139 tests passed
```

Implemented reference/contract scope now includes:

- independent capture/apply planning;
- capability registry and Dataflow incremental profile;
- framework UPSERT/SCD1/SCD2/REPLACE/SNAPSHOT_DIFF apply implementations;
- CaptureReceipt;
- provider-neutral Fabric capture request/evidence/transport boundary;
- Copy Job/Copy Activity/Dataflow/Spark capture adapter wrappers;
- recovery core and unknown-outcome safety.

Still required:

- actual Fabric REST/SDK/CLI transports;
- real Pipeline backend;
- connector/product-version real certification;
- CDC normalization/checkpoint/bootstrap;
- strategy-specific recovery completion;
- real target/native apply certification.

## 14. Acceptance rule for routine onboarding

Normal source/table onboarding should be:

```text
1. resolve logical connection/environment binding
2. declare semantic metadata
3. select/resolve certified capture profile
4. use framework apply by default unless native apply is certified
5. add domain DQ/mapping
6. add bounded extension only for genuine exception
7. deploy definitions/items
8. observe via common control plane
```

Editing framework source is reserved for a new reusable cross-domain capability.
