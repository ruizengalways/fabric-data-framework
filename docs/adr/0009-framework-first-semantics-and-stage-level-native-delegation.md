# ADR 0009 — Framework-first semantics with stage-level native delegation

Status: Accepted
Date: 2026-08-28

## Context

`fabric-data-framework` must be usable as a stable enterprise wheel rather than a thin wrapper around whichever Microsoft Fabric feature happens to exist for a particular connector or workload.

Fabric-native capabilities are valuable but do not provide one universal semantic implementation across all sources and targets.

Examples verified against Microsoft Learn on 2026-08-28 include:

- Copy Job CDC supports a bounded connector set and currently has limitations including mixed CDC/non-CDC behavior, net-change-only capture and no custom capture instances;
- Copy Job SCD2 remains Preview and has source/schema restrictions;
- Dataflow Gen2 incremental refresh works through DateTime buckets and replaces changed destination buckets;
- Dataflow Gen2 incremental refresh currently exposes `replace` as the destination update method rather than a generic SCD1/UPSERT/SCD2 apply contract.

A domain may therefore legitimately want to use a native tool for source movement while still requiring framework-owned current-state/history semantics afterward.

Representative example:

```text
Dataflow Gen2 incremental refresh
    -> staging / Bronze
    -> framework SCD1
    -> reconciliation
    -> state/audit
```

The same pattern applies to Copy Job, Copy Activity, Mirroring and external CDC feeds.

## Decision

The framework owns the canonical semantic contracts and must provide portable fallback implementations for mature reusable Data Engineering patterns.

Native Fabric features are **stage-level delegates**, not the architectural foundation of the semantic model.

The execution lifecycle is decomposed conceptually into independent physical ownership boundaries:

```text
capture / movement
    -> normalize / transform
    -> apply
    -> reconcile
    -> state / audit
```

Different stages may use different engines.

The current 0.4.0-development `execution.engine` field is interpreted as the capture/movement execution boundary. It must not be interpreted as granting that engine ownership of all downstream semantics.

A native stage may be selected only when a capability profile can prove that it satisfies the requested contract. If equivalence cannot be established, the compiler must fail closed or select the framework fallback.

## Native delegation rules

### Capture/movement delegation

Native capture is encouraged where it provides a clear advantage in connector support, query folding, throughput, operational visibility or reduced source pressure.

Examples:

```text
Copy Job -> Bronze -> framework apply
Copy Activity -> Bronze -> framework apply
Dataflow Gen2 -> staging -> framework apply
Mirroring -> replicated source state -> framework canonicalization/apply
Debezium/Kafka -> Bronze -> framework CDC normalization/apply
```

Native capture returns or is correlated to a typed `CaptureReceipt` so the common control plane can retain source boundary, run identity, landing reference, row counts and progress ownership.

### Apply delegation

Framework-owned `APPEND`, `REPLACE`, `UPSERT`, `SCD1`, `SCD2` and `SNAPSHOT_DIFF` remain canonical semantic implementations.

A native target-side implementation may replace the framework apply stage only when a registered capability profile explicitly certifies semantic equivalence for the relevant connector/source/target/product version and limitations.

Generic native capability profiles must not assume that marketing names such as `merge`, `incremental refresh` or `SCD2` are automatically equivalent to the framework contract.

### Progress ownership

Each physical capture has one authoritative checkpoint owner:

```text
FRAMEWORK
FABRIC_NATIVE
EXTERNAL
```

The framework must not maintain a competing watermark against a native Copy Job/Dataflow/Mirroring checkpoint.

Progress ownership does not imply apply ownership.

For example:

```text
Dataflow Gen2 owns incremental bucket progress
framework owns SCD1 target semantics
```

is valid.

## Framework fallback requirement

For core production patterns, loss of a native Fabric feature must not require redesigning domain metadata or forking the framework.

The planner should be able to move from a certified native adapter to a framework-controlled executor while retaining the same semantic contract where the source/target capabilities permit it.

Examples:

```text
WATERMARK + SCD1
  native path: Copy/Dataflow capture -> framework SCD1
  fallback:    Spark/framework bounded capture -> framework SCD1

CDC + UPSERT
  native path: Copy Job/External CDC -> framework CDC normalization -> UPSERT
  fallback:    framework CDC adapter -> framework normalization -> UPSERT
```

## Extension model

Finite standard patterns belong in the framework. Irregular source behavior belongs in bounded domain extensions.

Metadata references logical extension names rather than arbitrary import paths. Extensions may customize capture/parsing/transform/DQ/specialized apply behavior, but they may not bypass row accounting, reconciliation, state commit rules, secret/binding policy or durable audit.

## Consequences

Positive consequences:

- domain metadata remains stable even as Fabric native capabilities evolve;
- native features can be used where they are strong without inheriting their limitations for the whole pipeline;
- Dataflow Gen2/Copy Job can be used as ingestion accelerators while framework SCD1/SCD2/UPSERT remains consistent across sources;
- correctness can be certified outside Fabric and then separately proven through Fabric adapters;
- product/version-specific limitations live in capability profiles instead of leaking into semantic strategy definitions.

Costs:

- execution planning becomes explicitly multi-stage;
- native adapters require receipt/correlation contracts;
- capability certification must be maintained as Microsoft Fabric features evolve;
- some scenarios perform an additional landing/staging step before final apply.

## Follow-up implementation

1. Treat framework SCD1 and UPSERT as P0 core implementations.
2. Make capture/movement executor and apply executor/native-delegation choice explicit in execution planning/metadata.
3. Add connector/product-version capability profiles rather than one optimistic global native profile.
4. Add native capture adapter contracts for Copy Job, Copy Activity and Dataflow Gen2 using `CaptureReceipt`.
5. Add at least one certification scenario proving `native capture -> framework SCD1`.
6. Add native apply delegation only after explicit equivalence tests exist.
