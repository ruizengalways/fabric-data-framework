# Execution Engine Strategy — fabric-data-framework

Status: Canonical design
Last updated: 2026-08-29

## 1. Product requirement

`fabric-data-framework` is a reusable semantic/runtime product, not a wrapper around one Microsoft Fabric execution surface.

Core DE semantics have provider-neutral framework implementations. Fabric-native features are stage delegates when a capability profile proves the requested scope.

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

The immutable `ExecutionPlan` records concrete engines/profiles before execution. `AUTO` is a source-controlled resolution request, not a hidden runtime switch.

## 3. Framework-first fallback invariant

```text
semantic contract
    +-> framework portable implementation
    +-> optional certified provider delegate
```

Native product evolution should normally change a capability profile/adapter/plan, not redefine business semantics.

## 4. Current apply defaults

Framework reference implementations cover:

```text
REPLACE
UPSERT
SCD1
SCD2
SNAPSHOT_DIFF
```

CDC is a capture/change contract and feeds UPSERT/SCD1/SCD2 independently.

APPEND identity semantics remain future work.

Generic native profiles do **not** claim arbitrary UPSERT/SCD1/SCD2 equivalence. Unless an apply profile explicitly certifies the strategy, the conservative apply path is framework/Spark.

## 5. Native capture services

### Copy Job

Use for provider-managed full/incremental/native-CDC movement where connector/product semantics fit.

```text
Copy Job
  -> validated native evidence
  -> CaptureReceipt
  -> framework normalize/apply/reconcile
```

Native CDC must still be mapped into canonical `CDCEvent`/`CDCCheckpoint` before CDC semantic logic.

### Copy Activity

Useful when framework freezes an exact source predicate/range and Pipeline performs transport.

```text
framework freezes lower/upper
  -> Copy Activity
  -> observed range == requested range
  -> CaptureReceipt
  -> framework apply/state
```

### Dataflow Gen2

Useful for Power Query connector/folding/reshape and Fabric-native DateTime-bucket incremental behavior.

Named profile:

```text
DATAFLOW_GEN2 / dataflow_gen2_incremental_bucket_v1
```

certifies WATERMARK-like incremental staging with FABRIC_NATIVE progress, but not composite framework watermark or generic native UPSERT/SCD1/SCD2.

Valid hybrid:

```text
Dataflow Gen2 incremental
  -> CaptureReceipt
  -> framework UPSERT/SCD1/SCD2
```

### Spark

Spark/framework is conservative programmable fallback for source-boundary logic, composite ordering, parsing, deterministic current/history correctness and complex recovery. It is not required for every transport workload.

### Mirroring / external CDC

Provider/external service may own source replication/offset progress while framework remains responsible for canonicalization/apply/audit for non-delegated stages.

For CDC:

```text
native/external source cursor authority
  -> CaptureReceipt/native checkpoint correlation
  -> canonical CDC normalization
  -> downstream framework semantic apply checkpoint
```

The downstream checkpoint is not a competing source cursor.

## 6. Capability profiles

Capabilities are keyed by:

```text
(engine, profile_name)
```

because support varies by connector, source configuration, target, runtime mode and product version.

Rules:

- defaults conservative;
- named profile requires explicit engine;
- unsupported strategy/progress/order fails before mutation;
- capture certification does not imply apply certification;
- profile lacking composite ordering rejects metadata that requires it;
- native apply requires explicit apply-strategy certification;
- provider marketing names do not establish semantic equivalence.

Future CDC provider profiles must additionally state what native position/checkpoint evidence they can normalize and whether source offset commit/resume semantics are certified.

## 7. Progress ownership

Every physical capture has one authoritative source checkpoint owner.

```text
Copy Activity with framework-defined bounds -> FRAMEWORK
Copy Job native incremental/CDC             -> FABRIC_NATIVE
Dataflow Gen2 incremental                   -> FABRIC_NATIVE
Debezium/Kafka                              -> EXTERNAL or explicit consumer owner
```

Progress ownership does not imply apply ownership.

Framework downstream CDC semantic application progress is persisted separately only to track what has been safely applied/reconciled; it does not make the framework owner of an external/native source cursor.

## 8. CaptureReceipt handoff

`CaptureReceipt` records framework run correlation, capture strategy, engine/progress owner, native run ID, source/landing reference, rows, boundaries, snapshot evidence and external checkpoint references.

It is immutable handoff evidence, not proof that downstream apply/state succeeded.

## 9. Fabric adapter architecture

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

`FabricAdapterRegistry` is explicit. Framework semantic code does not construct credentials/workspace clients.

Fail-closed rules include engine/kind/role validation, unsuccessful/unknown native status rejection, evidence matching and exact bounded-range verification for FRAMEWORK-owned movement.

These are adapter-contract guarantees, not real Fabric integration evidence.

## 10. CDC execution boundary

Canonical CDC detail: `CDC_DESIGN.md`.

Provider adapter responsibility:

```text
provider envelope/coordinate
  -> canonical partition + integer position tuple
  -> CDCEvent / CDCCheckpoint
```

Semantic core responsibility:

```text
bounded completeness
identity/dedupe/conflict
ordering proof
overlap handling
UPSERT/SCD1/SCD2 apply
reconciliation
downstream checkpoint
```

A provider adapter that cannot prove unique event order must fail rather than pass ambiguous events to apply logic.

## 11. Recovery and physical execution

Generic recovery distinguishes:

```text
RETRYABLE
NON_RETRYABLE
UNKNOWN_OUTCOME
```

Ambiguous target commit is reconciled before another mutation:

```text
COMMITTED     -> converge success
NOT_COMMITTED -> retry may proceed
UNRESOLVED    -> stop
```

For native/external capture, source offset resume/commit behavior is provider-adapter responsibility and remains a current gap.

## 12. Many-table topology

Use metadata plus a small number of execution groups rather than one bespoke pipeline per table or one opaque giant pipeline.

Group by real operational boundaries: source/gateway, capture engine/profile, schedule/SLA, volume, dependency, criticality/blast radius and capacity/network boundary.

SCD1/SCD2/UPSERT are apply semantics and do not define ingestion topology.

## 13. Bounded extension points

Metadata references stable logical extension names for exceptional capture/parser/transform/DQ/specialized apply behavior.

Extensions may not bypass lineage, accounting, quarantine, reconciliation, progress authority, publication, secrets/bindings or audit.

A provider-specific CDC parser extension must still emit canonical CDC contracts and inherits all downstream framework guarantees.

## 14. Current implementation evidence

Latest coherent CDC head before docs synchronization:

```text
465a2c1e9ddf25b0ace2293f578c2c5bb3a653ae
Actions 33216281126
171 tests passed
```

Implemented reference/contract scope includes:

- independent capture/apply planning;
- capability registry and Dataflow incremental profile;
- framework UPSERT/SCD1/SCD2/REPLACE/SNAPSHOT_DIFF;
- CaptureReceipt;
- Fabric capture request/evidence/transport boundary;
- Copy Job/Copy Activity/Dataflow/Spark capture wrappers;
- recovery core/unknown-outcome safety;
- canonical CDC I/U/D, identity/order/dedupe/bounded checkpoints;
- CDC -> UPSERT/SCD1/SCD2;
- durable optimistic CDC downstream checkpoint;
- snapshot/bootstrap -> CDC handoff.

Still required:

- selected provider CDC envelope/capability adapters;
- provider source-offset resume/commit recovery;
- actual Fabric REST/SDK/CLI transports;
- real Pipeline backend;
- connector/product-version real certification;
- strategy-specific replay/rebuild completion;
- real target/native apply certification.

## 15. Acceptance rule for routine onboarding

Normal source/table onboarding should be:

```text
1. resolve logical connection/environment binding
2. declare semantic metadata
3. select/resolve certified capture profile
4. use framework apply by default unless native apply is certified
5. configure provider CDC mapping/profile if capture=CDC
6. add domain DQ/mapping
7. add bounded extension only for genuine exception
8. deploy definitions/items
9. observe via common control plane
```

Editing framework source is reserved for a new reusable cross-domain capability.
