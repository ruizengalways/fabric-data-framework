# Current projections from SCD2 history

This framework supports a single-authority model for entities that need both historical
SCD2 truth and a consumer-facing current representation.

```text
silver.customer_history   canonical SCD2 truth
silver.customer           derived/rebuildable current representation
```

The current object is never an independent interpretation of the original source.
History remains authoritative in every physicalization mode.

## Semantic rule

```text
original source
      ↓
SCD2 history dataset
      ↓
derived current projection dataset
```

Do not create two independent pipelines from the original source merely to maintain one
SCD2 table and one SCD1 table. That creates two independently derived truths and permits
schema, delete, replay, ordering, and repair semantics to drift.

A current projection is modeled as a downstream `DatasetConfig`. Its
`current_projection.authoritative_history_dataset_id` points at an SCD2 dataset, and its
orchestration dependencies must include that history dataset. The projection's source is
the history target, not the original source.

Preferred names express consumer semantics rather than algorithms:

```text
<entity>          current canonical representation
<entity>_history  SCD2 historical representation
```

Use names such as `_current_snapshot` only where the object is genuinely a complete
point-in-time snapshot rather than simply current state.

## Mode 1 — VIEW

`VIEW` is the default low-maintenance physicalization.

```text
customer_history
      ↓
WHERE _framework_is_current = true
      ↓
customer VIEW
```

The deployment compiler emits a stable `CREATE OR REPLACE VIEW` over the authoritative
history table. The consumer-facing schema is taken from the projection dataset's schema
contract so framework SCD2 metadata columns do not leak into the public current object.

Properties:

- no independent projection checkpoint;
- no duplicate current-state storage;
- no drift from history;
- rebuild is simply redeployment of the view definition;
- consumer name remains stable if a later release changes physicalization mode.

Use VIEW unless measured workload requirements justify maintaining another physical
object.

## Mode 2 — MATERIALIZED

`MATERIALIZED` preserves the same semantic contract and stable consumer name while
allowing a domain deployment to choose a physical implementation.

The framework exposes an implementation selector:

```text
AUTO
FABRIC_MATERIALIZED_LAKE_VIEW
DELTA_TABLE_REFRESH
```

`AUTO` currently compiles to a Fabric Materialized Lake View. The semantic mode is kept
stable so a future Fabric implementation can change without changing consumer names or
the logical configuration contract.

Current Fabric limitation: Materialized Lake View optimal incremental refresh requires
sources to be append-only during that refresh cycle and source CDF to be available.
When an update or delete is detected, Fabric falls back to full refresh. Normal SCD2
maintenance updates the previous current history row to `_framework_is_current=false`,
so a materialized current view over SCD2 history should **not** be assumed to refresh
incrementally. Treat this mode as a convenience/performance option only where full
refresh cost is acceptable, or choose the deterministic Delta-table refresh
implementation.

Official references:

- https://learn.microsoft.com/fabric/data-engineering/materialized-lake-views/refresh-materialized-lake-view
- https://learn.microsoft.com/fabric/data-engineering/materialized-lake-views/materialized-lake-view-sql-reference

The deployment plan records that incremental refresh is not expected for the MLV SCD2
pattern. Real Fabric behavior must still be certified in an approved environment.

## Mode 3 — DELTA_PROJECTION

`DELTA_PROJECTION` is for very large or high-frequency history tables where repeatedly
scanning all SCD2 history is materially expensive.

It is a downstream dataset with its own framework CDC checkpoint over the history Delta
table:

```text
customer_history committed Delta changes
      ↓
bounded CDF versions N..M
      ↓
distinct affected business keys
      ↓
read customer_history AS OF exact version M
      ↓
select authoritative rows where _framework_is_current = true
      ↓
UPSERT current rows / DELETE keys with no current history row
      ↓
reconciliation
      ↓
commit projection CDC checkpoint M
```

The second stage deliberately does **not** apply SCD1 directly to history CDF rows. An
SCD2 change normally produces mutations to both the former and the new history rows; a
history mutation is not itself a current-state mutation. CDF is used only to identify
which business keys may have changed. The current value is re-read from authoritative
history.

### Exact-version rule

The authoritative history read must be frozen at exactly the same Delta version as the
upper CDF checkpoint being applied. Reading a newer history snapshot could expose data
that is ahead of the projection checkpoint and would make retry/recovery ambiguous.
The reference executor fails closed if these versions differ.

### Failure and retry

There is no distributed transaction across `customer_history` and `customer`.

```text
history commit succeeds
current mutation succeeds
projection checkpoint commit fails
```

is recovered by replaying the same bounded history CDF range. The projection apply is
idempotent: current rows that already equal authoritative history produce no mutation,
and deletes of already absent keys produce no mutation. Only after target mutation and
required reconciliation pass may the independent projection checkpoint advance.

If current mutation fails, history remains authoritative and unchanged. The projection
resumes from the last successfully committed history version.

### Deletes and tombstones

For each affected business key:

- exactly one current history row -> insert/update the current projection;
- zero current history rows -> delete the current projection row;
- more than one current history row -> fail closed.

This means source-delete semantics are interpreted once by the authoritative SCD2
history path. The projection does not reinterpret the original source tombstone.

### Checkpoint and lag

Mode 3 reuses the existing environment-local `cdc_checkpoint` and `dataset_run` tables.
No second projection-state subsystem is introduced.

```text
history_latest_delta_version           provider observation
current_projection_processed_version   existing CDC checkpoint
projection_lag                         derived difference
last_successful_projection_run         existing dataset_run audit
projection_status                      derived health
```

Example:

```text
history version             108
projection processed         108
lag                            0
status                   HEALTHY
```

or:

```text
history version             108
projection processed         105
lag                            3
status                   LAGGING
```

`UNINITIALIZED` means no projection checkpoint exists. An optional lag error threshold
can classify larger lag as `STALE`.

### CDF retention

The existing Delta CDF resume planner remains authoritative. If the next required
history version has already fallen outside provider retention, execution raises a
retention-gap error rather than silently starting at the earliest surviving version.
Recovery then requires an explicit full rebuild of current state from authoritative
history and a governed checkpoint reset/cutover procedure.

## Configuration shape

History remains a normal SCD2 dataset. A current representation is another dataset with
explicit projection semantics, for example conceptually:

```yaml
dataset_id: crm.customer.current
source:
  system: framework_dataset
  object: silver.customer_history
target:
  layer: silver
  object: customer
load:
  capture_strategy: PROJECTION
  apply_strategy: CURRENT_PROJECTION
  business_key: [customer_id]
  merge_key: [customer_id]
  delete_policy: DERIVE_FROM_HISTORY
current_projection:
  authoritative_history_dataset_id: crm.customer_history
  mode: VIEW
orchestration:
  dependencies: [crm.customer_history]
```

Change `mode` to `MATERIALIZED` or `DELTA_PROJECTION` without changing the stable
consumer object name.

A projection dataset requires an explicit schema contract. This is the consumer-facing
column set copied/read from history and prevents SCD2 technical columns from becoming
an accidental public API.

## Rebuild and repair

All current modes are rebuildable from history:

- VIEW: redeploy the view;
- MATERIALIZED: full refresh/recreate from the current rows in history;
- DELTA_PROJECTION: rebuild the physical current table from all authoritative current
  history rows, reconcile, then establish the new projection checkpoint through a
  governed recovery path.

A repair to authoritative history must invalidate or replay affected downstream current
projection work through the ordinary dependency/rebuild model. Do not manually patch the
current representation as an alternative truth.

## DEV / UAT / PROD

Projection semantics are source-controlled and promotable. Runtime checkpoints, run
audits, provider history versions, and projection lag are environment-local and are not
promoted between environments. Environment bindings own physical Lakehouse/workspace
references as elsewhere in the framework.

## Certification boundary

Local tests can prove provider-neutral projection semantics, SQL generation, idempotent
retry behavior, checkpoint gating, and SQLite Control Plane persistence. They cannot
prove OneLake CDF retention, Delta time-travel behavior, MLV refresh selection, Spark
MERGE behavior, or Fabric operational latency. Those remain real-Fabric certification
requirements for any release that claims these physical modes.
