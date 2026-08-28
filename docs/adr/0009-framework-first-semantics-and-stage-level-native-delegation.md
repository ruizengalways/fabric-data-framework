# ADR 0009 — Framework-first semantics with stage-level native delegation

Status: Accepted
Date: 2026-08-28
Implementation status updated: 2026-08-29

## Context

`fabric-data-framework` must be a stable enterprise runtime rather than a thin wrapper around whichever Microsoft Fabric feature currently exists for a connector/workload.

Fabric-native services are valuable but product/connector/version constrained. A domain may legitimately use native movement while retaining framework-owned target semantics.

Representative pattern:

```text
Dataflow Gen2 incremental
    -> staging / Bronze
    -> framework UPSERT/SCD1
    -> reconciliation
    -> state/audit
```

The same principle applies to Copy Job, Copy Activity, Mirroring, Spark and external CDC feeds.

## Decision

The framework owns canonical semantic contracts and portable fallback implementations for mature reusable Data Engineering patterns.

Native Fabric features are **stage-level delegates**, not the architectural foundation of the semantic model.

```text
capture / movement
    -> normalize / transform
    -> apply
    -> reconcile
    -> state / audit
```

Different stages may use different engines.

Source-controlled execution therefore separates:

```text
capture engine/profile/progress owner
    !=
apply engine/profile
```

The immutable `ExecutionPlan` resolves both independently before execution.

A native stage may be selected only when a capability profile proves the requested contract. If equivalence cannot be established, planning must fail closed or select the framework fallback.

## Capture/movement delegation

Native movement is encouraged where it offers connector support, query folding, throughput, reduced source pressure or better operational visibility.

Examples:

```text
Copy Job -> Bronze -> framework apply
Copy Activity -> Bronze -> framework apply
Dataflow Gen2 -> staging -> framework apply
Mirroring -> replicated state -> framework canonicalization/apply
Debezium/Kafka -> Bronze -> framework CDC normalization/apply
```

Native/provider capture is correlated through a typed evidence boundary:

```text
ExecutionPlan capture unit
    -> provider request
    -> native run evidence
    -> validated CaptureReceipt
```

## Apply delegation

Framework-owned apply semantics remain canonical:

```text
REPLACE
UPSERT
SCD1
SCD2
SNAPSHOT_DIFF
future APPEND
```

A native final-target implementation may replace framework apply only when an explicit apply capability profile certifies semantic equivalence, including failure/retry boundaries.

Names such as `merge`, `incremental refresh`, `overwrite` or `SCD2` do not establish equivalence by themselves.

## Progress ownership

One physical capture has one authoritative checkpoint owner:

```text
FRAMEWORK
FABRIC_NATIVE
EXTERNAL
```

The framework must not maintain a competing source checkpoint against native Copy Job/Dataflow/Mirroring progress.

Progress ownership does not imply apply ownership.

## Provider adapter boundary

Implementation now includes a provider-neutral Fabric capture adapter layer:

```text
FabricCaptureRequest
FabricCaptureTransport
FabricNativeRunEvidence
FabricCaptureAdapter
```

with concrete capture wrappers for Copy Job, Copy Activity, Dataflow Gen2 and Spark.

Adapter validation is fail-closed:

- engine/kind/roles must match the compiled plan;
- unsuccessful/unknown native runs never create success receipts;
- landing/source/snapshot mismatches fail;
- FRAMEWORK-owned bounded capture must prove the requested source range;
- native run IDs are preserved in CaptureReceipt.

The transport remains injected so real REST/SDK/CLI clients can evolve without contaminating core semantics.

This is adapter-contract evidence, not yet real Fabric execution evidence.

## Recovery consequence

Provider delegation does not weaken retry correctness.

If a target mutation outcome is uncertain, the framework recovery core requires reconciliation before retry:

```text
COMMITTED     -> converge success, no duplicate write
NOT_COMMITTED -> retry may proceed
UNRESOLVED    -> stop
```

For native-progress capture, downstream recovery must use retained provider receipt/checkpoint semantics rather than inventing a second framework watermark.

## Framework fallback requirement

Loss/limitations of a native feature should not require redesigning domain semantic metadata when an equivalent framework-controlled execution path exists.

Examples:

```text
WATERMARK + SCD1/UPSERT
  native:    Copy/Dataflow capture -> framework apply
  fallback:  Spark/framework bounded capture -> same apply semantic

CDC + UPSERT
  native:    Copy Job/external CDC -> framework normalize -> UPSERT
  fallback:  framework CDC adapter -> framework normalize -> UPSERT
```

## Extension model

Finite standard patterns belong in the framework. Irregular source behavior belongs in bounded domain extensions referenced by logical names.

Extensions may not bypass accounting, reconciliation, state/progress authority, publication, secrets/bindings or durable audit.

## Consequences

Benefits:

- stable domain semantics as Fabric capabilities evolve;
- native movement where it is strong without inheriting limitations for the full lifecycle;
- consistent framework UPSERT/SCD1/SCD2 across capture mechanisms;
- provider-independent deterministic certification;
- product/version limitations isolated in profiles/adapters.

Costs:

- execution planning is explicitly multi-stage;
- adapters require evidence/correlation contracts;
- capability profiles require maintenance;
- some scenarios add landing/staging before final apply;
- real provider recovery semantics must be certified separately.

## Implemented follow-up

Completed since the original ADR acceptance:

1. framework ordered/idempotent SCD1;
2. framework ordered/idempotent UPSERT;
3. independent capture/apply executor metadata and ExecutionPlan fields;
4. named capability profiles including Dataflow incremental bucket capture;
5. CaptureReceipt;
6. Fabric capture adapter request/evidence/registry layer;
7. Copy Job/Copy Activity/Dataflow/Spark capture wrappers;
8. generic retry/attempt/reprocess/unknown-commit recovery core.

## Remaining follow-up

1. real Fabric REST/SDK/CLI transports and Pipeline backend;
2. real connector/product-version capability certification;
3. CDC canonical normalization/checkpoint/bootstrap;
4. strategy-specific native-progress replay/recovery;
5. native apply delegation only after explicit equivalence tests;
6. at least one retained real Fabric DEV hybrid execution before next release decision.
