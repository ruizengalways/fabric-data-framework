# Execution Engine Strategy — fabric-data-framework

Status: Canonical design and reference implementation
Last updated: 2026-08-28

## 1. Product requirement

`fabric-data-framework` is a reusable semantic/runtime product, not a wrapper around one Fabric execution surface.

An enterprise should be able to install a released wheel and onboard ordinary datasets mainly through metadata, bindings and bounded domain extensions.

The framework therefore provides portable fallback semantics for mature Data Engineering patterns while using Fabric-native movement/apply features only where explicitly capability-certified.

ADR 0009 is the governing decision: **framework-first semantics with stage-level native delegation**.

## 2. Independent concerns

Do not collapse these concerns into one engine concept:

```text
Capture semantics
  FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM

Capture / movement executor
  FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 |
  SPARK | FABRIC_MIRRORING | EXTERNAL_CDC | SQL | CUSTOM

Apply semantics
  APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF

Apply executor
  SPARK/framework by conservative default
  native/SQL/custom only through an explicitly certified apply profile or extension

Capture progress owner
  FRAMEWORK | FABRIC_NATIVE | EXTERNAL
```

The current source-controlled policy is explicit:

```text
ExecutionPolicy.engine
ExecutionPolicy.capability_profile
ExecutionPolicy.progress_owner
    -> capture/movement

ExecutionPolicy.apply_engine
ExecutionPolicy.apply_capability_profile
    -> final-target apply
```

`AUTO` may exist in policy, but the immutable plan records concrete resolved engines.

## 3. Framework-first fallback invariant

For core reusable patterns:

```text
semantic contract
     |
     +--> framework-owned portable implementation
     |
     +--> optional native stage delegate, only when capability-certified
```

A native service becoming unavailable or insufficient should not force a domain semantic redesign where an equivalent framework path exists.

Example:

```text
WATERMARK + SCD1

native capture path
  Dataflow Gen2 / Copy -> landing -> framework SCD1

framework fallback path
  Spark/framework bounded capture -> framework SCD1
```

The semantic request is unchanged; only physical stage ownership differs.

## 4. Capture-stage executors

### Copy Job

Use for supported high-throughput multi-table/full/incremental/native-CDC movement when native checkpoint ownership and documented connector behavior fit the contract.

Typical composition:

```text
Copy Job -> Bronze/staging -> CaptureReceipt -> framework apply/reconcile
```

Do not infer universal CDC/SCD behavior from the product feature name.

### Copy Activity

Use when framework-controlled bounds, source query construction and Pipeline control flow are important:

```text
framework freezes source range
  -> Copy Activity moves bounded range
  -> CaptureReceipt
  -> framework apply/reconcile/state
```

### Dataflow Gen2

Use where Power Query connector/folding/reshape capability is valuable. It is not assumed to own current-state/history apply semantics.

Current named profile:

```text
DATAFLOW_GEN2 / dataflow_gen2_incremental_bucket_v1
```

certifies only:

```text
capture_strategy = WATERMARK
progress_owner = FABRIC_NATIVE
composite watermark = not certified
native final SCD1/UPSERT/SCD2 = not certified
```

Supported hybrid contract:

```text
Dataflow Gen2 incremental buckets
    -> landing/staging
    -> CaptureReceipt
    -> framework SCD1 / UPSERT / SCD2
    -> reconciliation/state/audit
```

### Spark/framework

Spark/framework remains the conservative programmable fallback for composite ordering, custom source-boundary logic, irregular formats, advanced dedupe/version handling, code-level correctness and recovery semantics.

Spark is not mandatory for transport that a native service can safely perform.

### Mirroring and external CDC

Mirroring may own supported replication progress while downstream semantics remain independent. A governed Debezium/Kafka or equivalent CDC feed should be consumed instead of re-polling the source; the framework still owns non-delegated normalization/apply/audit.

## 5. Apply-stage executors

Portable reference apply implementations currently include:

```text
REPLACE
UPSERT
SCD1
SCD2
SNAPSHOT_DIFF
```

`APPEND` remains required but is not yet certified.

The capability registry has an independent `apply_strategies` set per `(engine, profile)`.

Current conservative rule:

```text
apply_engine = AUTO
    -> SPARK/framework
```

Generic Fabric/SQL profiles currently certify **no final-target apply strategy**. A request such as:

```text
apply_strategy = UPSERT
apply_engine = SQL
```

fails before mutation unless a future SQL target-specific capability profile explicitly certifies UPSERT semantics and failure boundaries.

Likewise, the Dataflow incremental capture profile cannot be reused as a native SCD1 apply profile.

`CUSTOM` apply is permitted only when `extensions.apply` names a controlled domain extension.

## 6. Shared current-state semantics

SCD1 and UPSERT use the same ordered current-state correctness primitive rather than duplicating algorithms.

Ordering metadata is:

```text
(event_time_column?, version_column?, sequence_column?)
```

Certified behavior includes composite merge keys, latest-row selection, exact rerun idempotency, stale-row policy, equal-position conflict failure and duplicate/superseded/stale evidence.

This makes native capture interchangeable without changing downstream correctness:

```text
Copy/Dataflow/CDC landing
  -> same framework current-state apply contract
```

## 7. Named capability profiles

Capabilities are keyed by:

```text
(engine, profile_name)
```

rather than one optimistic capability per engine because behavior varies by feature, connector, source configuration, target and product version.

Resolver rules:

- default profiles are conservative;
- named profiles require an explicit engine;
- capture and apply are validated independently;
- unsupported combinations fail before mutation;
- a profile may certify capture without apply;
- composite watermark requires explicit support;
- `AUTO` resolves to a concrete engine before immutable planning;
- no hidden runtime fallback to a weaker engine is allowed.

## 8. Progress ownership

Every physical capture has one authoritative checkpoint owner:

```text
FRAMEWORK
FABRIC_NATIVE
EXTERNAL
```

Examples:

```text
framework-bounded Copy Activity -> FRAMEWORK
Copy Job incremental/native CDC -> FABRIC_NATIVE
Dataflow Gen2 incremental -> FABRIC_NATIVE
Debezium consumer group -> EXTERNAL or explicit framework consumer
```

The framework must not advance a competing watermark for the same native checkpoint.

**Progress ownership does not imply apply ownership.**

## 9. CaptureReceipt handoff

Native activities do not import the Python wheel. They participate through `CaptureReceipt` evidence containing/correlating:

```text
dataset_run_id / dataset_id
capture_strategy / execution_engine / progress_owner
native_run_id
landing_reference
rows_read / rows_written
source lower/upper bounds where meaningful
snapshot completeness where meaningful
external checkpoint reference where meaningful
started/completed timestamps
```

Control-plane schema v2 stores receipt evidence as environment-local runtime state.

## 10. Immutable ExecutionPlan

The compiler emits concrete stage ownership:

```text
ExecutionPlan
  capture_strategy
  apply_strategy
  capture_engine
  capture_capability_profile
  apply_engine
  apply_capability_profile
  execution units[]
```

Representative plans:

```text
SPARK capture + SPARK apply
  -> one bounded dataset_execute unit

DATAFLOW_GEN2 capture + SPARK apply
  -> capture
  -> framework_process(normalize, validate, apply, reconcile, commit-state)

native/custom certified apply in the future
  -> capture
  -> framework_prepare
  -> apply
  -> framework_finalize(reconcile, commit-state)
```

Reconciliation/state authority remains explicit even when an apply stage is delegated.

## 11. Deployed control-plane policy

Promotable semantic definitions mirror the stage split:

```text
execution_policy
  capture execution_engine
  capture progress_owner
  capture capability_profile
  controlled extensions

apply_execution_policy
  apply execution_engine
  apply capability_profile

ordering_policy
  event_time_column
  version_column
  sequence_column
```

Runtime watermarks, receipts, run state and overrides remain environment-local and are never promoted across environments.

## 12. Many-table topology

For tens/hundreds of tables, avoid one bespoke pipeline per table and one opaque giant pipeline.

Prefer metadata plus reusable execution groups, for example:

```text
pl_erp_daily
  +-- erp_full_reference
  +-- erp_incremental_current
  +-- erp_incremental_history
  +-- erp_cdc_transactional
  +-- erp_custom_complex
```

Useful grouping dimensions include source/gateway limits, capture engine/profile, schedule/SLA, volume, criticality, dependency stage, network boundary and Fabric capacity.

SCD1/SCD2/UPSERT are apply semantics, not ingestion architectures.

## 13. Bounded extension points

Metadata stores logical names rather than arbitrary Python import/call expressions:

```yaml
extensions:
  capture: vendor_api_v2
  parser: weird_csv_v1
  transform: normalize_position_v3
  quality: null
  apply: vendor_current_state_v1
```

Extensions may customize true exceptions but may not bypass row accounting, quarantine, reconciliation, progress/state authority, publication, secrets/bindings or durable audit.

## 14. Current executable evidence

Representative proof:

```text
tests/test_execution_engines.py
tests/test_stage_execution_policy.py
tests/test_upsert.py
tests/test_scd1.py
tests/test_apply_execution_policy.py
```

Latest green coherent code/control-plane slice before docs synchronization:

```text
commit 60d4d1362f504a51b3ecedfcb93c7c6ceb3d4578
GitHub Actions 33175724889
106 tests passed
```

This is reference/portable proof, not real Fabric adapter evidence.

## 15. Remaining work

- concrete Copy Job / Copy Activity / Dataflow Gen2 / Spark adapter contracts and native run correlation;
- recovery/attempt semantics and unknown-outcome handling;
- CDC normalization/bootstrap/checkpoint correctness;
- APPEND identity/collision semantics;
- real connector/product-version capability certification;
- real approved Fabric DEV execution evidence.

## 16. Product acceptance rule

Routine source onboarding should normally be:

```text
1. register/resolve connection binding
2. declare semantic metadata
3. select or resolve capture profile
4. keep framework apply AUTO unless a certified delegate is justified
5. add domain DQ/mapping
6. add bounded extension only for genuine exceptions
7. deploy semantic definitions/items
8. observe through the common control plane
```

Editing the framework package is reserved for a new reusable cross-domain capability, not an ordinary table/source variation.
