# Architecture

This is the canonical architecture document for `fabric-data-framework`.

## 1. Core design rule

The framework separates **data semantics** from **physical execution**.

```text
1. Semantics
   What does the source actually deliver?
   What fidelity, delete behavior and history can be proven?

2. Execution
   Which Fabric mechanism performs the work?
   Pipeline, Copy, Spark, SQL, provider-native change feed, etc.

3. Evidence and recovery
   How do we prove semantic success?
   How do we recover safely from partial/ambiguous outcomes?
```

`Spark`, `Copy` and `Pipeline` are execution choices, not source semantics.

A truthful dataset description looks more like:

```text
source       = current-state relational table
capture      = watermark + bounded lookback
ordering     = updated_at + stable key
delete       = soft-delete signal
Bronze       = raw observations
Silver       = SCD2
```

## 2. Repository ownership

```text
fabric-data-framework
  reusable semantics/contracts/planning/runtime/adapters/recovery/evidence
  framework wheel lifecycle
  installed-wheel and real-Fabric framework certification

fabric-customer
  Fabric-native, framework-agnostic source-system simulator/testbed
  deterministic source facts and source delivery behavior
  expected source/business truth
  workload_digest
  NO framework dependency

implementation/domain repo
  one real project/data product, e.g. fabric-health
  DatasetConfig and source-to-target mappings
  business DQ/reconciliation rules
  execution groups/dependencies
  environment bindings and deployment content
  project-specific bounded adapters
  physical v1/v2 target names and provider-specific logical binding
  UAT/business validation and approval
  may depend on an approved/released framework wheel

fabric-infra
  capacity/workspace/permission infrastructure lifecycle
```

Dependency invariant:

```text
implementation/domain repo -> approved fabric-data-framework wheel

fabric-customer -X-> fabric-data-framework
fabric-data-framework -X-> fabric-customer
```

A simulator workload can be used by an implementation for regression testing, but it does not become part of framework release identity.

## 3. Framework flow

```text
DatasetConfig
  -> semantic validation / onboarding
  -> capability resolution
  -> immutable ExecutionPlan
  -> capture / orchestration / provider execution
  -> verified CaptureReceipt / durable child outcome
  -> normalization + DQ
  -> apply to target
  -> commit proof / reconciliation
  -> downstream semantic checkpoint
```

The important boundary is that provider completion is not semantic completion.

```text
Fabric/provider Completed
!=
framework semantic success
```

Framework success requires the relevant durable framework outcome, target evidence and reconciliation to agree.

## 4. Capture and apply are orthogonal

Capture answers:

```text
What did the source actually give us this run?
```

Apply answers:

```text
How should those captured facts change the target?
```

Examples:

```text
FULL snapshot          + REPLACE
WATERMARK changes      + UPSERT / SCD1
WATERMARK + LOOKBACK   + APPEND
ordered CDC events     + SCD2
business events        + APPEND
FULL snapshots         + SNAPSHOT_DIFF
```

Do not describe a source as “SCD2”; SCD2 is a target representation. Do not describe a Silver strategy as “watermark”; watermark is a capture strategy.

## 5. Fidelity ceiling

The framework never manufactures source history.

```text
truthful downstream history fidelity
<=
captured source fidelity
```

If the source provides one full snapshot per day, downstream history can truthfully identify changes only at snapshot grain unless the source also carries stronger effective-time evidence.

If a provider collapses multiple changes into one net change, downstream SCD2 cannot recreate the missing intermediate states.

For append/audit histories, a missing database PK is not itself fatal; the important requirement is a defensible stable event identity. Exact replay under the same identity is a no-op, while the same identity with different business payload must fail closed. If two legitimate events are indistinguishable under every available source field, the framework cannot invent their distinctness.

This fidelity rule is enforced during semantic onboarding and apply validation to prevent downstream overclaim.

## 6. Bronze meanings

Bronze is not one mandatory physical shape.

### Current Bronze

Stores latest/current state. Appropriate when observation history is not required.

### Snapshot Bronze

Stores each complete snapshot. Appropriate when the source has no reliable change feed and snapshot-grain history or snapshot diff is required.

### Raw append / event Bronze

Stores observations or ordered events. Appropriate for CDC, application change logs, replay/audit, or history where source fidelity supports it.

Bronze may legitimately retain repeated source observations caused by bounded lookback. Silver APPEND may deduplicate those observations under a declared stable `append_identity`.

The correct choice follows source semantics; it is not selected merely because a downstream model is called SCD2.

## 7. Provider cursor vs framework checkpoint

A provider cursor/offset says how far the provider consumed.

A framework semantic checkpoint says the framework has proven the corresponding capture, target apply, commit/reconciliation and downstream state are safe to advance.

They are not automatically equivalent.

## 8. Unknown commit is fail-closed

A target may commit successfully while the client loses the acknowledgement. Blind retry can then double-write.

Framework target-operation identity, journal state and target-side proof distinguish:

```text
COMMITTED
NOT_COMMITTED
UNRESOLVED
```

Rules:

```text
COMMITTED     -> converge to success; do not mutate again
NOT_COMMITTED -> a bounded retry may be allowed
UNRESOLVED    -> stop; no blind retry
```

This boundary protects append, merge and SCD history from duplicate mutation.

## 9. Data repair and versioned cutover boundary

Transient runtime recovery and data-correctness repair are intentionally separate operator lifecycles.

```text
RETRY / REPLAY / BACKFILL / unknown commit
  -> transient operational recovery
  -> docs/OPERATIONS.md

FULL_REBUILD / contaminated descendants / v1-v2 / UAT / cutover / rollback
  -> data-correctness repair
  -> docs/REPAIR_AND_REBUILD.md
```

`FULL_REBUILD` has exactly three scopes:

```text
TARGET_ONLY
CAPTURE_AND_TARGET
AUTHORITATIVE_RESET
```

The requested scope must match the physical completed scope exactly. Target commit and required reconciliation must pass before runtime state cutover. The framework does not automate permanent business-data purge, and blue/green cutover never automatically deletes the old physical target version.

## 10. Enterprise Fabric topology

DEV, UAT and PROD use the same logical architecture. They differ in resource IDs, credentials, capacity, scale and data, not in fundamental framework storage roles.

Canonical profile:

```text
control_plane_profile = fabric_sql_database_v1
environments          = DEV / UAT / PROD
```

Recommended split:

```text
CONTROL PLANE                         DATA PLANE
Fabric SQL Database                  OneLake / Lakehouse
-------------------                  -------------------
dataset/runtime definitions          Bronze source-faithful data
pipeline_run                         Silver normalized/current/SCD
 dataset_run                         quarantine payloads
 step_run                            large reconciliation detail
 watermark / CDC checkpoint          Gold analytical data
 retry/reprocess lineage                    |
 target operation journal                  +--> optional Fabric Warehouse
 reconciliation state                      for SQL-first Gold serving
 quarantine metadata
```

### Fabric SQL Database

Use for small, frequently changing operational state requiring relational transaction/CAS semantics and concurrent writers.

Typical framework state includes:

```text
pipeline_run
dataset_run
step_run
watermark / CDC checkpoint
reprocess_request
target_operation journal
reconciliation summary
quarantine metadata/reference
```

### Lakehouse / OneLake

Use for scalable business/data-engineering workloads:

```text
Bronze
Silver
Gold when Lakehouse serving is suitable
quarantine row payloads
large reconciliation/detail history
```

### Fabric Warehouse

Optional SQL-first analytical serving engine, commonly for facts, dimensions and dimensional Gold models. Medallion architecture does not require Warehouse.

## 11. Promotion contract

Promote definitions; do not promote runtime state.

Promoted through Git/CI/CD:

```text
framework/implementation code
DatasetConfig
execution-group policy
DQ/reconciliation rules
Notebook/Pipeline definitions
control-plane schema/migrations
non-secret logical bindings/templates
```

Environment-local and never copied from DEV to UAT/PROD:

```text
pipeline/dataset run rows
watermarks/checkpoints
retry/reprocess history
operation journal state
credentials/tokens
physical Fabric item IDs
business data
```

## 12. When to change which repository

Use this decision rule:

- reusable data-engineering behavior used across domains -> `fabric-data-framework`;
- realistic source behavior/scenario generation -> `fabric-customer`;
- project table configs/mappings/DQ/environment deployment/physical target binding -> implementation/domain repo;
- capacity/workspace/permissions -> `fabric-infra`.

A project-specific field rename, table exception or business SQL fragment is not automatically a framework feature.

## 13. Related docs

- Source-level runtime reading order: [`CODE_READING_GUIDE.md`](CODE_READING_GUIDE.md)
- New source/table decisions and APPEND identity: [`DATA_PATTERNS.md`](DATA_PATTERNS.md)
- Real project repo: [`IMPLEMENTATION_PROJECT.md`](IMPLEMENTATION_PROJECT.md)
- Transient runtime recovery: [`OPERATIONS.md`](OPERATIONS.md)
- Data correctness repair, dependency impact, v1/v2 cutover and rollback: [`REPAIR_AND_REBUILD.md`](REPAIR_AND_REBUILD.md)
- Exact-wheel certification: [`TESTING_AND_CERTIFICATION.md`](TESTING_AND_CERTIFICATION.md)
- Candidate/release lifecycle: [`RELEASE.md`](RELEASE.md)
