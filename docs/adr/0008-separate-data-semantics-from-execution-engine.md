# ADR 0008 — Separate data semantics from physical execution engine

Status: Accepted
Date: 2026-08-28

## Context

The framework must support enterprise Fabric estates where data movement may be performed by Fabric Copy Job, Pipeline Copy Activity, Dataflow Gen2, Spark, Mirroring or an external CDC platform such as Debezium/Kafka.

Requiring all datasets to be extracted by a Notebook/Spark Python implementation would duplicate mature Fabric-native movement capabilities and would make the reusable wheel a transport monolith.

Conversely, delegating all state/correctness to native movement tools would prevent the framework from providing stronger composite watermark, reconciliation, late-data, custom SCD and recovery guarantees where those are required.

## Decision

Model the following as independent axes:

1. capture semantics — FULL, WATERMARK, CDC, SNAPSHOT, MIRROR, STREAM;
2. physical execution/movement engine — Fabric Copy Job, Copy Activity, Dataflow Gen2, Spark, Mirroring, external CDC, SQL or bounded custom adapter;
3. apply semantics — APPEND, REPLACE, UPSERT, SCD1, SCD2, SNAPSHOT_DIFF;
4. authoritative progress owner — FRAMEWORK, FABRIC_NATIVE or EXTERNAL.

A capability resolver/compiler validates the selected combination and emits one immutable `ExecutionPlan` before execution.

Native tools integrate with framework-controlled downstream behavior through a typed capture/landing receipt rather than pretending that Copy/Dataflow activities import the Python wheel.

## Consequences

- Fabric-native Copy capabilities may be used directly where they satisfy the dataset contract.
- Framework-owned Spark execution remains available for stronger/custom correctness requirements.
- SCD2 is not treated as an ingestion method.
- Copy Job/native CDC state is not duplicated by an independent framework watermark.
- Composite watermark ordering can remain framework-owned when a native movement primitive cannot express the required ordering contract.
- A source with many tables can be divided into a small number of metadata-selected execution groups without one pipeline per table.
- Dataflow Gen2 is supported but not mandated as the generic many-table ingestion mechanism.
- External Debezium/Kafka CDC is a first-class capture source when already governed by the enterprise.
- Custom logic is exposed through typed, source-controlled extension points and may not bypass framework state/reconciliation/audit boundaries.
- Any future `AUTO` engine selection must resolve to a concrete engine in the immutable execution plan; execution must not silently change engines at runtime.

## Operational topology

A representative source with many tables may use:

```text
source parent pipeline
  -> full/reference execution group
  -> watermark/current-state execution group
  -> history/SCD execution group
  -> CDC execution group
  -> custom Spark/micro-batch execution group
```

The exact grouping is driven by source limits, engine, volume, SLA, criticality and blast radius rather than a fixed pipeline count.

## Documentation

See `docs/EXECUTION_ENGINE_STRATEGY.md` for the full product policy and metadata model.
