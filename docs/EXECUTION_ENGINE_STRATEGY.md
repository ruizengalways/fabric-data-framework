# Execution Engine Strategy — fabric-data-framework

Status: Canonical design
Last updated: 2026-08-28

## 1. Product requirement

`fabric-data-framework` is a reusable semantic/runtime product, not a wrapper around one Fabric execution surface.

An enterprise should be able to install a released wheel and onboard ordinary datasets mainly through metadata, bindings and bounded domain extensions.

The framework therefore must provide portable fallback implementations for mature Data Engineering semantics while using Fabric-native movement/apply features where they are explicitly capability-certified.

ADR 0009 is the governing decision: **framework-first semantics with stage-level native delegation**.

## 2. Independent concerns

Do not collapse these concerns into one `engine` concept:

```text
Capture semantics
  FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM

Capture / movement executor
  FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 |
  SPARK | FABRIC_MIRRORING | EXTERNAL_CDC | SQL | CUSTOM

Normalize / transform executor
  framework/Spark | SQL | Dataflow | bounded extension | future certified delegate

Apply semantics
  APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF

Apply executor
  framework implementation by default
  native delegate only when semantic equivalence is certified

Capture progress owner
  FRAMEWORK | FABRIC_NATIVE | EXTERNAL
```

The current 0.4.0-development metadata field `execution.engine` represents the **capture/movement boundary**. It must not be interpreted as lifecycle-wide ownership.

Future execution metadata will make apply-executor/native-delegation choice explicit.

## 3. Framework-first fallback invariant

For core reusable patterns:

```text
semantic contract
     |
     +--> framework-owned portable implementation (required)
     |
     +--> optional native stage delegate (capability-certified)
```

A native service becoming unavailable/insufficient should not require rewriting the domain semantic model where an equivalent framework-controlled path is technically possible.

Example:

```text
WATERMARK + SCD1

native capture path
  Dataflow Gen2 / Copy -> landing -> framework SCD1

framework fallback path
  Spark/framework bounded capture -> framework SCD1
```

The semantic request remains `WATERMARK + SCD1`; only the physical capture plan changes.

## 4. Native Fabric services are first-class stage executors

### 4.1 Copy Job

Use Copy Job where the connector/mode and required source semantics are supported and Fabric-native progress ownership is desirable, especially for straightforward multi-table/full/incremental/native-CDC movement.

Do not assume Copy Job provides a universal semantic layer. Connector support and CDC/SCD behavior are product/version constrained. A named capability profile must represent the actual certified scope.

A common safe composition is:

```text
Copy Job
  -> Bronze/staging
  -> CaptureReceipt/native run correlation
  -> framework normalization/apply/reconcile
```

### 4.2 Copy Activity

Use Copy Activity where framework-controlled bounds/source queries and Pipeline control flow are useful:

```text
framework computes/fixes source range
  -> Copy Activity moves bounded range
  -> CaptureReceipt
  -> framework apply/reconcile/state
```

This is a natural option for composite watermark/source-query scenarios if the activity can execute the framework-defined predicate while the framework owns progress.

### 4.3 Dataflow Gen2

Dataflow Gen2 is a first-class low-code movement/transformation surface, especially where Power Query connector/folding/reshape support is advantageous.

It is **not** assumed to own final current-state/history semantics.

Current named profile:

```text
DATAFLOW_GEN2 / dataflow_gen2_incremental_bucket_v1
```

certifies the current Fabric DateTime-bucket incremental behavior only as a capture/staging mechanism:

```text
capture_strategy = WATERMARK
progress_owner = FABRIC_NATIVE
composite watermark = not certified
native final SCD1/UPSERT/SCD2 = not implied
```

Required supported hybrid:

```text
Dataflow Gen2 incremental buckets
    -> landing/staging
    -> CaptureReceipt
    -> framework SCD1 / future UPSERT / SCD2
    -> reconciliation/audit
```

The bucket `replace` destination behavior must not be mislabeled as generic SCD1.

### 4.4 Spark/framework

Spark/framework execution is the conservative programmable fallback and is preferred when native movement cannot prove required semantics, including:

- composite watermark ordering;
- custom source-boundary logic;
- irregular files/protocols;
- micro-batch parsing;
- custom dedupe/order/version behavior;
- advanced current/history correction;
- deterministic recovery/idempotency requirements;
- code-level tests are required for correctness.

Spark is not mandatory for every transport workload.

### 4.5 Mirroring

Mirroring can own replication progress when a supported source/governance model fits. Downstream canonicalization/apply semantics remain separate decisions.

### 4.6 External CDC

When a governed Debezium/Kafka or other reliable CDC service already exists, consume it rather than re-polling the source.

External CDC owns/participates in offset authority according to the adapter contract. The framework still owns canonical CDC normalization, target apply and audit for the non-delegated stages.

## 5. Named capability profiles

Physical engine capabilities vary by:

```text
product feature
connector/source type
source configuration
runtime mode
target type
Fabric product version/status
```

Therefore capabilities are keyed by:

```text
(engine, profile_name)
```

rather than a single optimistic global capability per engine.

Current behavior:

- default profiles are conservative;
- `AUTO` resolves conservatively (normally framework/Spark when source-specific native certification is unknown);
- named profiles require an explicit engine;
- unsupported combinations fail before data mutation;
- a profile may certify capture without certifying apply;
- a profile that cannot prove composite watermark ordering must reject composite watermark metadata.

Future profiles should be connector/product-version specific where materially necessary.

## 6. Progress ownership

Every physical capture has one authoritative checkpoint owner:

```text
FRAMEWORK
FABRIC_NATIVE
EXTERNAL
```

Examples:

```text
Copy Activity with framework-bounded predicate
  -> FRAMEWORK

Copy Job incremental/native CDC
  -> FABRIC_NATIVE

Dataflow Gen2 incremental bucket refresh
  -> FABRIC_NATIVE

Debezium consumer group
  -> EXTERNAL or explicitly selected framework consumer
```

The framework must never advance a competing independent watermark for the same native capture checkpoint.

**Progress ownership does not imply apply ownership.**

Valid example:

```text
capture progress = FABRIC_NATIVE (Dataflow)
apply semantics  = framework SCD1
```

## 7. CaptureReceipt handoff

Native Fabric activities do not import the Python wheel. They participate through an evidence contract.

`CaptureReceipt` records/correlates at least:

```text
dataset_run_id
dataset_id
capture_strategy
execution_engine
progress_owner
native_run_id
landing_reference
rows_read / rows_written
source lower/upper boundary when meaningful
snapshot_id / complete_snapshot when meaningful
external checkpoint reference when meaningful
started/completed timestamps
```

The downstream framework consumes landing data plus receipt evidence and performs the non-delegated stages.

Control-plane schema v2 persists `capture_receipt` as environment-local runtime evidence.

## 8. Apply semantics and delegation

The framework canonical apply families are:

```text
APPEND
REPLACE
UPSERT
SCD1
SCD2
SNAPSHOT_DIFF
```

Implemented reference fallbacks currently include:

```text
REPLACE
SCD1
SCD2
SNAPSHOT_DIFF
```

UPSERT and APPEND remain P0/P1 gaps.

Native apply delegation is allowed only when a profile explicitly certifies equivalence for the requested contract and failure/retry boundary.

Do not infer equivalence from native names such as:

```text
merge
incremental refresh
overwrite
SCD2
```

The planner must record the concrete executor in the immutable plan; there is no hidden runtime engine switch.

## 9. Ordered SCD1 example

A common enterprise pattern:

```yaml
dataset_id: erp.customer

load:
  capture_strategy: WATERMARK
  apply_strategy: SCD1
  merge_key: [tenant_id, customer_id]
  watermark:
    column: modified_at
    overlap_window_seconds: 60
  event_time_column: modified_at
  version_column: source_version

execution:
  engine: DATAFLOW_GEN2
  progress_owner: FABRIC_NATIVE
  capability_profile: dataflow_gen2_incremental_bucket_v1
```

Physical/reference plan:

```text
Dataflow Gen2 capture/stage
  -> CaptureReceipt
  -> framework SCD1 using ordered current-state semantics
```

If the source requires `(modified_at, customer_id)` composite capture ordering that the Dataflow profile cannot prove, that profile is rejected and a framework-bounded capture engine must be selected instead.

## 10. Many-table source topology

For a source with tens/hundreds of tables, avoid:

```text
one bespoke pipeline per table
one giant opaque pipeline for every pattern
```

Prefer metadata + a small number of reusable execution groups:

```text
pl_erp_daily
  +-- erp_full_reference
  +-- erp_incremental_current
  +-- erp_incremental_history
  +-- erp_cdc_transactional
  +-- erp_custom_complex
```

Group by meaningful operational boundaries such as:

- source/gateway/concurrency limit;
- capture engine/profile;
- schedule/SLA;
- volume/runtime class;
- dependency stage;
- criticality/blast radius;
- capacity/network constraints.

SCD1/SCD2 may influence operational grouping but do not define ingestion architecture.

## 11. Bounded extension points

Metadata stores logical extension names, for example:

```yaml
extensions:
  capture: vendor_api_v2
  parser: weird_csv_v1
  transform: normalize_position_v3
  quality: null
  apply: null
```

The domain package registers implementations in a controlled registry/entry-point layer.

Metadata must **not** contain arbitrary Python module paths/call expressions.

Extensions may implement:

- custom capture adapter;
- special batch/micro-batch parser;
- pre-apply transform;
- DQ provider;
- specialized apply adapter when no standard semantic contract fits.

Extensions may not bypass:

- source/run lineage;
- row accounting;
- quarantine policy;
- reconciliation gates;
- state/progress authority;
- publication boundary;
- secret/binding policy;
- durable audit.

## 12. Capability resolver acceptance rules

Before execution the resolver/compiler must know enough to answer:

```text
Can this engine/profile produce the requested capture semantics?
Who owns capture progress?
Can it prove required ordering/completeness?
What landing/receipt evidence is required?
Which downstream semantics remain framework-owned?
Is any native apply delegate explicitly certified?
```

If the answer is uncertain, fail closed or use a framework fallback. Do not silently weaken correctness.

## 13. Current implementation status

Reference implementation currently includes:

- `ExecutionEngine`, `ProgressOwner`, `ExecutionPolicy.capability_profile`;
- capability registry keyed by engine + profile;
- conservative `AUTO`;
- Dataflow Gen2 incremental bucket profile;
- native-capture/framework-process `ExecutionPlan` splitting;
- `CaptureReceipt` contracts/persistence;
- SCD1 framework fallback;
- logical extension registry.

Latest green reference suite before final docs audit: 91 tests (`33172961692`).

Still required:

- explicit apply executor/native-apply metadata;
- UPSERT and APPEND framework implementations;
- concrete Fabric adapter calls for Copy Job/Copy Activity/Dataflow/SJD;
- product/connector-specific capability certification from real runs;
- recovery/CDC/schema-evolution hardening.

## 14. Product acceptance rule

Routine source onboarding should normally be:

```text
1. register/resolve connection binding
2. declare semantic metadata
3. select or resolve a certified capture profile
4. use framework apply semantic by default
5. add domain DQ/mapping
6. add bounded extension only for genuine exceptions
7. deploy metadata/items
8. observe through common control plane
```

Editing the framework package should be reserved for a new reusable cross-domain capability, not an ordinary table/source variation.
