# Execution Engine Strategy — fabric-data-framework

Status: Canonical design
Last updated: 2026-08-29

## 1. Product requirement

`fabric-data-framework` is a reusable semantic/runtime product, not a wrapper around one Microsoft Fabric execution surface.

Core DE semantics have provider-neutral framework implementations. Native/provider features are stage delegates when a capability profile proves the requested scope.

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

## 5. Native and external capture services

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

### Mirroring

Provider-native replication may own source progress while framework remains responsible for non-delegated canonicalization/apply/audit.

### External CDC — Debezium on Kafka

Built-in profile:

```text
EXTERNAL_CDC / debezium_kafka_v1
capture = CDC
progress owner = EXTERNAL
apply = independently resolved; framework/Spark by default
```

The framework adapter consumes already-received Debezium Kafka records and normalizes them using Kafka physical order:

```text
topic + partition + offset
   -> CDCSourcePosition
```

Database LSN/binlog values stay provider metadata. The profile does not claim that the framework owns or commits the external Kafka consumer cursor.

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

Current named profiles include:

```text
DATAFLOW_GEN2 / dataflow_gen2_incremental_bucket_v1
EXTERNAL_CDC  / debezium_kafka_v1
```

The Debezium/Kafka profile certifies provider envelope normalization and external progress ownership at reference/adapter-contract level. It does not certify a real Kafka client, consumer group or broker interaction.

## 7. Progress ownership

Every physical capture has one authoritative source checkpoint owner.

```text
Copy Activity with framework-defined bounds -> FRAMEWORK
Copy Job native incremental/CDC             -> FABRIC_NATIVE
Dataflow Gen2 incremental                   -> FABRIC_NATIVE
Debezium/Kafka                              -> EXTERNAL
```

Progress ownership does not imply apply ownership.

For Debezium/Kafka there are intentionally two coordinates:

```text
external consumer/source cursor
        !=
framework downstream CDC apply checkpoint
```

If a consumer cursor advances to 500 but downstream apply commits only through 420, safe replay starts from 421 if retention still covers it. The external cursor is not accepted as downstream-success evidence.

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

These are adapter-contract guarantees, not real Fabric integration evidence.

## 10. CDC provider adapter architecture

Canonical CDC detail: `CDC_DESIGN.md`.

```text
ExecutionPolicy(engine/profile)
        |
        v
CapabilityRegistry
        |
        v
ExecutionPlan
        |
        v
CDCProviderAdapterRegistry
        |
        v
provider envelope -> CDCEvent/CDCCheckpoint
        |
        v
framework CDC semantic apply
```

Current default provider registry maps:

```text
(EXTERNAL_CDC, debezium_kafka_v1)
    -> DebeziumKafkaCDCAdapter
```

The adapter layer owns provider translation and recovery-range evidence. It does not own UPSERT/SCD1/SCD2 algorithms.

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

Debezium/Kafka now has retention-aware resume planning:

```text
framework committed CDC apply offset
  -> next_required = committed + 1
  -> compare with earliest retained / latest available
  -> safe seek window OR explicit retention-gap failure
```

This is reference planning only. Real Kafka seek/consume/commit behavior remains transport integration work.

Other native/external capture engines still require their own strategy-specific downstream-failure resume proofs.

## 12. Many-table topology

Use metadata plus a small number of execution groups rather than one bespoke pipeline per table or one opaque giant pipeline.

Group by real operational boundaries: source/gateway, capture engine/profile, schedule/SLA, volume, dependency, criticality/blast radius and capacity/network boundary.

SCD1/SCD2/UPSERT are apply semantics and do not define ingestion topology.

## 13. Bounded extension points

Metadata references stable logical extension names for exceptional capture/parser/transform/DQ/specialized apply behavior.

Extensions may not bypass lineage, accounting, quarantine, reconciliation, progress authority, publication, secrets/bindings or audit.

A provider-specific CDC parser extension must still emit canonical CDC contracts and inherits all downstream framework guarantees.

## 14. Current implementation evidence

Latest provider CDC evidence:

```text
1087ab9231b9cb638a87bc2f78ef0c1b1fe32beb
Actions 33219601375
179 tests passed
Debezium/Kafka envelope + safe resume

ecdca38099a4f21c6f40701dc14889b464c20608
Actions 33219783325
183 tests passed
Debezium/Kafka capability profile + provider registry
```

Implemented reference/contract scope includes:

- independent capture/apply planning;
- Dataflow incremental profile;
- framework UPSERT/SCD1/SCD2/REPLACE/SNAPSHOT_DIFF;
- CaptureReceipt;
- Fabric capture request/evidence boundary;
- recovery core/unknown-outcome safety;
- canonical CDC I/U/D, identity/order/dedupe/bounded checkpoints;
- CDC -> UPSERT/SCD1/SCD2;
- durable optimistic CDC downstream checkpoint;
- snapshot/bootstrap -> CDC handoff;
- Debezium/Kafka provider normalization;
- Debezium tombstone/snapshot-read policy;
- Kafka retention-aware safe resume planning;
- explicit provider adapter registry and capability profile.

Still required:

- real Kafka/Debezium transport + consumer-group commit/correlation;
- additional CDC provider profiles only where product scope requires;
- actual Fabric REST/SDK/CLI transports;
- real Pipeline backend;
- strategy-specific quarantine replay/FULL_REBUILD/native-progress recovery completion;
- real target/native apply certification.

## 15. Acceptance rule for routine onboarding

Normal source/table onboarding should be:

```text
1. resolve logical connection/environment binding
2. declare semantic metadata
3. select/resolve certified capture profile
4. use framework apply by default unless native apply is certified
5. configure provider CDC profile if capture=CDC
6. add domain DQ/mapping
7. add bounded extension only for genuine exception
8. deploy definitions/items
9. observe via common control plane
```

Editing framework source is reserved for a new reusable cross-domain capability.
