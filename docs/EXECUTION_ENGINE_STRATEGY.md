# Execution Engine Strategy — fabric-data-framework

Status: Canonical design
Last updated: 2026-08-28

## 1. Product requirement

`fabric-data-framework` is intended to be installed as a released wheel into an enterprise Fabric estate and then consumed mainly through source-controlled metadata, environment bindings and bounded extension points. Domain teams should not need to edit the framework package for routine datasets.

The framework must therefore model the finite, well-known production data-engineering problem space explicitly and choose or validate an execution mechanism for each dataset without confusing data semantics with the physical tool that executes them.

The framework does **not** require every dataset to be ingested by Python, Notebook or Spark.

## 2. Three independent axes

A dataset execution is described by at least three independent concerns:

```text
Capture semantics
  FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM

Physical movement/execution engine
  FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 |
  SPARK | MIRROR | EXTERNAL_CDC | SQL | CUSTOM

Apply semantics
  APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF
```

Examples:

```text
FULL      + COPY_JOB          + REPLACE
FULL      + COPY_ACTIVITY     + REPLACE
WATERMARK + COPY_JOB          + UPSERT
WATERMARK + COPY_ACTIVITY     + SCD2
WATERMARK + SPARK             + SCD2
CDC       + COPY_JOB          + SCD1/SCD2 where native capability is sufficient
CDC       + EXTERNAL_CDC      + UPSERT/SCD2
SNAPSHOT  + SPARK/COPY        + SNAPSHOT_DIFF
MIRROR    + FABRIC_MIRRORING  + downstream canonicalization
```

The metadata compiler/planner validates that the selected physical engine can satisfy the requested semantic guarantees.

## 3. Native Fabric movement is first-class

A production framework should use Fabric-native data movement where it is the best fit rather than reimplementing all transport in Python.

### Copy Job

Prefer Copy Job for straightforward high-throughput movement/replication when the connector and required semantics are supported, especially:

- multi-table ingestion;
- full copy;
- watermark-based incremental copy;
- supported native CDC;
- simple append/merge/override behavior;
- operational cases where Fabric-native progress ownership is acceptable.

A Copy Job may own its own incremental checkpoint. The framework must not invent a second independent watermark for the same physical movement operation.

### Copy Activity

Prefer Copy Activity when pipeline-level orchestration and framework-controlled bounds are important, for example:

- metadata lookup + ForEach/Invoke Pipeline patterns;
- framework-owned source lower/upper bounds;
- custom bounded source query;
- composite watermark behavior not directly represented by the chosen native copy mechanism;
- explicit framework state/reconciliation gates around the movement step.

### Dataflow Gen2

Treat Dataflow Gen2 as a supported low-code ingestion/transformation engine, not the universal default for a hundred-table technical ingestion framework.

Good fits include:

- Power Query is the natural connector/transformation surface;
- substantial low-code cleansing/reshape logic is valuable;
- business/data-integration teams need visual maintainability;
- reusable parameterized transformation logic fits current Dataflow capabilities.

Do not force Dataflow Gen2 where parameterization, incremental behavior, state ownership or source/target dynamism is weaker than Copy/Spark for the workload.

### Spark / framework executor

Prefer Spark/framework-owned execution when correctness or transformation requirements exceed native movement capabilities, including:

- composite watermark ordering such as `(modified_at, business_key)`;
- custom source consistency/freeze logic;
- complex parsing or irregular files;
- micro-batch logic;
- heavy transformations;
- custom deduplication/version ordering;
- late/out-of-order correction;
- advanced SCD2 behavior;
- cross-batch idempotency/recovery semantics;
- source/target logic requiring code-level tests.

Spark should be a deliberate execution engine, not a mandatory transport layer.

### External CDC / Debezium

If a reliable enterprise CDC feed already exists, such as Debezium/Kafka or another governed change-log service, consume that feed rather than polling the operational database again.

The framework normalizes the external CDC envelope into the Bronze contract, validates ordering/event identity/delete semantics and then applies the configured target strategy.

## 4. Progress ownership is explicit

Every dataset must declare or resolve one authoritative progress owner:

```text
FRAMEWORK
FABRIC_NATIVE
EXTERNAL
```

Examples:

```text
Copy Activity with framework-generated bounded query
  -> FRAMEWORK owns watermark/checkpoint

Copy Job incremental/CDC
  -> FABRIC_NATIVE owns movement checkpoint
  -> framework records native run/checkpoint evidence but does not advance a competing watermark

Debezium/Kafka consumer group
  -> EXTERNAL or framework consumer owns offset according to the selected adapter contract
```

One physical capture operation must not have two independent authorities for progress.

## 5. Capture receipt / handoff contract

Native Fabric tools do not import the Python wheel themselves. They integrate with the framework through a typed handoff contract.

Conceptually every capture engine produces a `CaptureReceipt`:

```text
CaptureReceipt
  dataset_run_id
  execution_engine
  native_run_id
  source_reference
  landing_reference
  rows_read / rows_written
  source_lower_bound
  source_upper_bound
  snapshot_id
  complete_snapshot
  progress_owner
  external_checkpoint_reference
  schema/version evidence
  started_at / completed_at
```

The downstream framework execution can then perform:

```text
capture receipt / Bronze landing
  -> normalization
  -> DQ/quarantine
  -> domain transform
  -> apply
  -> reconciliation
  -> framework state commit where framework is authoritative
  -> audit/lineage
```

This is how Copy Activity, Copy Job or Dataflow Gen2 can participate in the same product without pretending that those activities execute the Python wheel.

## 6. Metadata-driven 100-table source pattern

For a source with many tables, do not create one bespoke pipeline per table and do not force all tables through one giant execution path.

Use dataset metadata plus a small number of reusable operational execution groups.

Example:

```yaml
dataset: erp.customer
capture_strategy: WATERMARK
apply_strategy: SCD2
execution_group: erp_incremental_history
execution_engine: COPY_ACTIVITY
progress_owner: FRAMEWORK
watermark:
  column: modified_at
  tie_breaker: [customer_id]
ordering:
  event_time_column: modified_at
  version_column: null
merge_key: [customer_id]
business_key: [customer_id]
```

```yaml
dataset: erp.country
capture_strategy: FULL
apply_strategy: REPLACE
execution_group: erp_full_reference
execution_engine: COPY_JOB
progress_owner: FABRIC_NATIVE
merge_key: [country_code]
```

```yaml
dataset: erp.order
capture_strategy: CDC
apply_strategy: UPSERT
execution_group: erp_cdc_transactional
execution_engine: EXTERNAL_CDC
progress_owner: EXTERNAL
merge_key: [order_id]
ordering:
  version_column: source_lsn
```

A realistic orchestration layout is therefore closer to:

```text
pl_erp_daily                       parent/source orchestration
   |
   +-- execution_group=erp_full_reference
   |       -> reusable native-copy path
   |
   +-- execution_group=erp_incremental_current
   |       -> reusable watermark path
   |
   +-- execution_group=erp_incremental_history
   |       -> capture + framework SCD2 path
   |
   +-- execution_group=erp_cdc_transactional
   |       -> CDC normalization/apply path
   |
   +-- execution_group=erp_custom_complex
           -> Spark/custom extension path
```

The exact number of pipelines is an operational design decision. `execution_group` is metadata, so groups can reflect source load limits, SLA, schedule, capacity, engine, criticality and failure blast radius.

## 7. Do not make SCD2 the ingestion architecture

SCD2 is an apply/history semantic, not a source extraction method.

The same SCD2 engine may consume:

```text
WATERMARK -> SCD2
CDC       -> SCD2
SNAPSHOT  -> SNAPSHOT_DIFF -> SCD2
```

Therefore a separate `*_scd2` Fabric pipeline is acceptable when it creates a useful operational boundary, but the framework must not require that topology. The metadata compiler chooses SCD2 from `apply_strategy`, independent of how rows arrived.

## 8. Native versus framework SCD2

If a native Fabric capability offers SCD2 and its documented behavior satisfies the dataset contract, the framework may delegate execution to it.

If the dataset requires guarantees beyond that native capability — for example custom effective dating, composite event ordering, late-history repair, conflict handling or stronger audit/recovery semantics — use the framework SCD2 executor.

The planner must make this delegation explicit in the immutable `ExecutionPlan`. There is no hidden runtime fallback from one engine to another.

## 9. Bounded custom extension points

Production metadata-driven frameworks still need an escape hatch for irregular sources and genuinely custom transformations.

Custom logic is allowed through typed, source-controlled extension references, conceptually:

```yaml
extensions:
  capture_handler: null
  transform_handler: "customer_domain.handlers.weird_feed:transform"
  apply_handler: null
```

Allowed extension classes include:

- custom capture adapter;
- batch/micro-batch parser;
- pre-apply transformation;
- custom DQ rule provider;
- specialized apply adapter where no standard strategy is sufficient.

Extensions receive typed execution context and batch/landing references and return typed results/evidence.

Extensions may **not** silently:

- mutate framework watermark/state directly;
- mark reconciliation successful;
- bypass row accounting;
- publish outside the declared target transaction/publication boundary;
- read secrets from source-controlled metadata;
- change semantic strategy at runtime.

The framework remains the lifecycle and correctness owner around the extension.

## 10. Engine capability registry

The framework will maintain an explicit capability registry instead of scattering engine-specific `if` statements.

Conceptually:

```text
EngineCapability
  connectors / source types
  capture strategies
  supported apply modes
  native checkpoint ownership
  delete support
  schema-evolution support
  multi-table support
  parameterization constraints
  execution mode
  known service limitations
```

Planning becomes:

```text
Dataset semantic metadata
       +
Environment/source capabilities
       +
Explicit execution policy
       |
       v
Capability validation/resolution
       |
       v
Immutable ExecutionPlan
       |
       +--> Fabric Copy backend
       +--> Copy Job backend
       +--> Dataflow backend
       +--> Spark backend
       +--> external CDC backend
```

`AUTO` selection, if supported, must resolve to a concrete engine before execution and be captured in the immutable plan/provenance. A production run must never silently switch engines because service capability changed.

## 11. Pipeline grouping guidance

Do not group tables only because they share a database connection. Do not group them only because they share SCD2 either.

Useful grouping dimensions are:

- source system and source-side concurrency limit;
- movement engine;
- capture semantics;
- SLA/schedule;
- data volume/runtime class;
- criticality/blast radius;
- dependency stage;
- capacity pool;
- special network/gateway requirements.

For a 100-table ERP source, 3–8 reusable execution groups is often more maintainable than 100 pipelines or one giant pipeline, but the framework does not encode a magic number.

## 12. Control-plane metadata target

The deployed semantic/control metadata should eventually express at least:

```text
dataset identity
source/target reference
capture_strategy
apply_strategy
execution_engine / execution_profile
progress_owner
business_key
merge_key
watermark column + composite tie-breaker
source event time
source version/sequence columns
delete policy
schema contract/evolution policy
DQ policy
reconciliation policy
execution_group
criticality/dependencies
retry/timeout/concurrency
custom extension references
```

Operational overrides remain limited to safe operational values. Engine, merge keys, SCD mode, schema contract or custom handler identity are semantic/deployment changes, not ad-hoc production overrides.

## 13. Product acceptance rule

The framework is successful when a new ordinary enterprise source can be onboarded mainly by:

```text
1. register connection/binding
2. declare dataset metadata
3. choose/resolve supported execution profile
4. provide optional domain DQ/mapping
5. provide custom handler only for true exceptions
6. deploy metadata + Fabric items
7. run and observe through common control plane
```

Routine onboarding must not require editing `fabric-data-framework` itself.
