# ADR 0009 — Framework-first semantics with stage-level native delegation

Status: Accepted and partially implemented
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
    -> framework SCD1 or UPSERT
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

`ExecutionPolicy.engine` and `capability_profile` describe the capture/movement boundary. `ExecutionPolicy.apply_engine` and `apply_capability_profile` independently describe the final-target apply boundary. Neither field grants an engine ownership of the complete lifecycle.

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

Framework-owned `REPLACE`, `UPSERT`, `SCD1`, `SCD2` and `SNAPSHOT_DIFF` are currently certified portable apply semantics. `APPEND` remains required but is not yet certified.

A native target-side implementation may replace the framework apply stage only when a registered capability profile explicitly certifies semantic equivalence for the relevant connector/source/target/product version and limitations.

Generic native capability profiles must not assume that marketing names such as `merge`, `incremental refresh` or `SCD2` are automatically equivalent to the framework contract.

The current generic registry therefore certifies SPARK/framework apply for the implemented strategies and deliberately certifies no generic native final-target apply. `CUSTOM` is allowed only through the controlled domain extension contract.

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
framework owns SCD1/UPSERT target semantics
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

WATERMARK/CDC + UPSERT
  native path: native/external capture -> framework normalization -> UPSERT
  fallback:    framework capture -> framework normalization -> UPSERT
```

## Current implementation

The 0.4.0 development branch now implements the stage separation described by this ADR:

```text
ExecutionPolicy
  engine / capability_profile                 capture/movement policy
  progress_owner                              capture checkpoint authority
  apply_engine / apply_capability_profile     independent apply policy

ExecutionPlan
  capture_engine / capture_capability_profile
  apply_engine / apply_capability_profile
  concrete execution units
```

`AUTO` is allowed in source-controlled policy but must resolve to concrete engines before an immutable execution plan is emitted.

The default apply resolver chooses SPARK/framework semantics. A native or SQL apply request fails closed unless its named profile explicitly lists the requested `ApplyStrategy`.

The deployed control plane mirrors the separation:

```text
execution_policy        capture/movement engine + progress owner + capture profile
apply_execution_policy  apply engine + apply profile
ordering_policy         event/version/sequence ordering fields
```

Representative executable proof includes:

```text
tests/test_upsert.py
tests/test_stage_execution_policy.py
tests/test_apply_execution_policy.py
tests/test_execution_engines.py
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

- execution planning is explicitly multi-stage;
- native adapters require receipt/correlation contracts;
- capability certification must be maintained as Microsoft Fabric features evolve;
- some scenarios perform an additional landing/staging step before final apply.

## Remaining follow-up

1. Add native capture adapter contracts for Copy Job, Copy Activity, Dataflow Gen2 and Spark using `CaptureReceipt`.
2. Add real DEV proof for at least one `native capture -> CaptureReceipt -> framework SCD1/UPSERT` execution.
3. Add native apply delegation only after explicit equivalence tests exist.
4. Implement recovery/attempt semantics so stage retries and unknown outcomes preserve the same contract.
5. Implement CDC normalization/bootstrap and reuse the current-state UPSERT/SCD1 primitives downstream.
