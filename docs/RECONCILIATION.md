# Reconciliation

This is the canonical guide for configuring and operating reconciliation in `fabric-data-framework`.

Reconciliation is a correctness gate between planned target mutation and durable state/checkpoint advancement. Provider completion is not reconciliation authority, and a generic `source count == target count` rule is not sufficient across FULL, incremental, APPEND, SCD, snapshot-diff, and CDC-shaped workloads.

## 1. Mental model

```text
capture / Bronze / DQ / transform / apply plan
                |
                v
        strategy invariants
                +
        provider observations
                |
                v
   framework reconciliation policy
                |
        +-------+-------+
        |       |       |
       PASS    WARN     FAIL
        |       |       |
        |       |       +-- blocking only when
        |       |           required_for_state_commit=true
        |       |
        |       +-- retain warning evidence; publish may continue
        |
        +-- publish / state advance allowed when all other gates pass
```

The framework owns policy semantics, tolerance, PASS/WARN/FAIL classification, and state-gate authority. SQL, Spark, Fabric-native, or project adapters collect bounded observations only.

## 2. Mandatory separation of concerns

Keep these responsibilities distinct:

```text
implementation/project or provider adapter
  collect source/target scalar observations
  push down count/sum/min/max/duplicate/null/checksum work
  emit ReconciliationObservation values

framework
  validate observation identity
  combine strategy-specific invariant metrics
  evaluate tolerance
  classify warning vs blocking error
  create ReconciliationResult
  decide whether reconciliation may block publication/state
```

This prevents provider `Completed` from becoming semantic PASS and lets large datasets reconcile using pushed-down aggregates instead of materializing whole tables in the Python process.

## 3. Source-controlled policy

`DatasetConfig.reconciliation` owns the released reconciliation policy.

Conceptually:

```python
from fabric_data_framework.contracts.reconciliation import ReconciliationSeverity
from fabric_data_framework.metadata.config import (
    ReconciliationAggregate,
    ReconciliationCheck,
    ReconciliationCheckKind,
    ReconciliationPolicy,
)

policy = ReconciliationPolicy(
    policy_name="orders_standard",
    required_for_state_commit=True,
    include_row_accounting=True,
    checks=(
        ReconciliationCheck(
            check_id="daily_count",
            kind=ReconciliationCheckKind.ROW_COUNT_MATCH,
            partition_by=("business_date",),
        ),
        ReconciliationCheck(
            check_id="order_key_unique",
            kind=ReconciliationCheckKind.UNIQUE_KEY,
            columns=("order_id",),
            max_count=0,
        ),
        ReconciliationCheck(
            check_id="amount_total",
            kind=ReconciliationCheckKind.AGGREGATE_MATCH,
            column="amount",
            aggregate=ReconciliationAggregate.SUM,
            partition_by=("business_date",),
            absolute_tolerance=0.01,
        ),
        ReconciliationCheck(
            check_id="optional_comment_null_rate",
            kind=ReconciliationCheckKind.NULL_RATE,
            column="comment",
            max_fraction=0.20,
            severity=ReconciliationSeverity.WARNING,
        ),
    ),
)
```

The complete policy participates in `DatasetConfig.config_hash` and is materialized into the existing Control Plane `reconciliation_policy.definition` JSON column. This feature does not require a new Control Plane schema version.

## 4. Portable check kinds

### `ROW_COUNT_MATCH`

Compares a numeric source-side expectation with a numeric target/candidate observation. Use it only where both counts represent the same semantic grain.

Allowed settings:

```text
partition_by
absolute_tolerance
relative_tolerance
severity
```

Do not use whole-table row count equality for an incremental batch against a cumulative SCD2 table.

### `UNIQUE_KEY`

Asks the provider to return a duplicate count for the configured columns.

```text
columns    required
max_count  required
partition_by optional
```

Typical production setting:

```text
max_count = 0
```

Use this for candidate/current-key uniqueness. Apply-specific identity invariants such as APPEND identity conflict handling remain strategy-owned and are not replaced by this generic check.

### `NULL_RATE`

Provider returns a null fraction between 0 and 1 for one column.

```text
column        required
max_fraction  required
partition_by  optional
```

This is often a warning for optional attributes and an error for business-critical fields.

### `AGGREGATE_MATCH`

Compares source and target numeric aggregates.

Supported aggregates:

```text
SUM
MIN
MAX
```

Required configuration:

```text
column
aggregate
```

It supports absolute and relative tolerance and may be partitioned.

### `CHECKSUM_MATCH`

Compares exact provider-produced checksum values over configured columns. The framework does not dictate the provider's hashing implementation; the source and target observations must be produced under one reviewed, deterministic contract.

Required configuration:

```text
columns
```

Checksum mismatch is exact; numeric tolerance is not accepted for this check kind.

### `CUSTOM`

Use only when a business control cannot be represented by the portable checks.

```text
extension = "health.claims_balance"
```

The implementation extension supplies a typed observation decision. The framework still owns check identity, severity, result aggregation, persistence, and state-gate semantics.

Do not move ordinary count/uniqueness/null/aggregate logic into custom extensions.

## 5. Row accounting is different from source-vs-target matching

By default:

```text
include_row_accounting = true
```

The framework verifies the dataset-run accounting invariant:

```text
rows_read
=
rows_accepted
+ rows_quarantined
+ rows_filtered
```

This answers **where every captured row went**. It is not the same as asserting that an incremental source batch and a cumulative target have equal row counts.

APPEND and other strategies add their own accounting. For example, accepted APPEND rows must be explained by inserted/replayed/duplicate outcomes.

## 6. Strategy-specific invariants remain mandatory

Declarative checks extend, but never replace, strategy correctness.

Current reusable paths compose these base metrics:

```text
FULL -> REPLACE
  source snapshot row count accounted
  candidate count matches accepted rows
  snapshot completeness

APPEND
  every accepted row is inserted/replayed/duplicate-accounted
  identity conflict remains fail-closed in apply semantics

WATERMARK -> SCD2
  row accounting
  one current row per business key

SNAPSHOT -> SNAPSHOT_DIFF
  accepted candidate count
  valid target-after structural count
```

Future provider/native paths must preserve the same rule: generic reconciliation must not weaken apply/capture invariants.

## 7. Tolerance

For numeric row-count or aggregate checks, the framework accepts a difference when:

```text
abs(actual - expected)
<=
absolute_tolerance
+ relative_tolerance * abs(expected)
```

Examples:

```text
expected = 100000
actual   = 99995
absolute_tolerance = 10
relative_tolerance = 0
=> PASS
```

```text
expected = 100000
actual   = 99950
absolute_tolerance = 0
relative_tolerance = 0.001
allowed difference = 100
=> PASS
```

Tolerance is part of released semantic configuration. Do not introduce an ad-hoc runtime tolerance merely to make a failed load green.

## 8. Partitioned reconciliation

Whole-table aggregates can hide local defects. Prefer partitioned controls when the business/source grain supports them.

Example:

```text
check_id = amount_total
partition_by = (business_date, country)
```

Then the provider emits one observation for every observed partition:

```python
ReconciliationObservation(
    check_id="amount_total",
    expected=125000.50,
    actual=125000.50,
    partition={"business_date": "2026-09-08", "country": "AU"},
)
```

For one configured check, partition identity must match the exact configured `partition_by` keys. Duplicate observations for the same partition fail closed.

The current engine validates evidence it receives; it does not infer an exhaustive expected partition universe. If a project requires proof that specific partitions must exist, the provider/project contract must produce that expected partition set or a bounded `CUSTOM` control that proves completeness.

## 9. Evidence failures fail closed

The following are framework reconciliation failures, not ignorable provider quirks:

```text
configured check has no observation
observation references unknown check_id
multiple observations supplied for an unpartitioned check
partition keys do not match policy
same partition supplied more than once
numeric check receives missing/non-numeric evidence
UNIQUE_KEY receives invalid duplicate count
NULL_RATE receives a fraction outside [0, 1]
CHECKSUM_MATCH lacks either checksum
CUSTOM lacks an explicit provider decision
```

Do not silently drop malformed observations.

## 10. PASS, WARN, FAIL, and blocking authority

`ReconciliationSeverity` has two values:

```text
ERROR
WARNING
```

A failed `WARNING` metric is non-blocking and produces an overall `WARN` when there is no failed blocking metric.

A failed `ERROR` metric produces `FAIL`.

Blocking authority is separately controlled by:

```text
required_for_state_commit
```

Production default:

```text
required_for_state_commit = true
```

Meaning:

```text
PASS -> reconciliation gate passed
WARN -> warning retained; reconciliation gate may pass
FAIL -> publication/state/checkpoint must not advance
```

If a dataset explicitly sets:

```text
required_for_state_commit = false
```

then reconciliation is observability-only. An ERROR failure is still recorded as `FAIL`, but that result does not own publication/state blocking authority. This setting should be exceptional and reviewed; do not use it to bypass a known correctness requirement.

Other independent gates such as DQ, target commit proof, snapshot completeness, apply identity conflicts, or rebuild/cutover gates remain authoritative regardless of this reconciliation flag.

## 11. Recommended enterprise baseline

For most current-state tables:

```text
include_row_accounting = true
ERROR unique business/current key
ERROR source-vs-candidate row count when grains are actually comparable
ERROR important financial/control aggregate(s)
WARNING optional-field null-rate trend
partition important counts/aggregates by business date or source partition when practical
```

For APPEND/event tables:

```text
framework APPEND identity/accounting invariant
+ optional partitioned event counts
+ optional critical aggregate/checksum controls
```

For SCD2:

```text
framework one-current-row invariant
+ run accounting
+ candidate/current-business-key controls
+ source-vs-target aggregates only at a semantically comparable grain
```

For finance or regulated domains, business balancing controls usually belong in project-owned `CUSTOM` extensions only when they cannot be expressed as ordinary aggregates.

## 12. Example: orders

```python
reconciliation=ReconciliationPolicy(
    policy_name="orders_daily",
    checks=(
        ReconciliationCheck(
            check_id="source_candidate_count",
            kind=ReconciliationCheckKind.ROW_COUNT_MATCH,
            partition_by=("business_date",),
        ),
        ReconciliationCheck(
            check_id="order_id_unique",
            kind=ReconciliationCheckKind.UNIQUE_KEY,
            columns=("order_id",),
            max_count=0,
        ),
        ReconciliationCheck(
            check_id="gross_amount",
            kind=ReconciliationCheckKind.AGGREGATE_MATCH,
            column="gross_amount",
            aggregate=ReconciliationAggregate.SUM,
            partition_by=("business_date",),
            absolute_tolerance=0.01,
        ),
    ),
)
```

A SQL/Fabric adapter might push down:

```sql
SELECT business_date, COUNT(*) AS row_count, SUM(gross_amount) AS gross_amount
FROM ...
GROUP BY business_date
```

and convert those bounded results into `ReconciliationObservation` objects. The framework then evaluates the released policy.

## 13. Operational response

On `FAIL` with blocking reconciliation:

```text
1. do not advance watermark/checkpoint/state
2. do not call provider Completed a success
3. retain exact ReconciliationResult metrics
4. identify whether the problem is source, capture, DQ, mapping, target apply, or observation collection
5. fix the actual cause
6. use RETRY / REPLAY / BACKFILL / FULL_REBUILD according to docs/OPERATIONS.md and docs/REPAIR_AND_REBUILD.md
```

Do not change a threshold/tolerance without source-controlled review and redeployment.

On repeated `WARN`, treat the trend as an operational signal; a non-blocking warning is not permission to ignore deteriorating data quality.

## 14. Ownership in a real implementation project

The framework owns:

```text
ReconciliationPolicy and typed checks
ReconciliationObservation contract
central evaluation/tolerance/severity
PASS/WARN/FAIL result contract
state-gate semantics
persistence/audit identity
strategy-specific reusable invariants
```

The implementation/domain repo owns:

```text
which business controls matter
project-specific check configuration
provider query/observation adapters when generic collection is insufficient
CUSTOM business controls
UAT/business interpretation
```

`fabric-customer` remains framework-agnostic and supplies deterministic source/business truth for testing; it does not become the framework's reconciliation policy owner.

## 15. Code map

```text
src/fabric_data_framework/contracts/reconciliation.py
  observation / metric / status / severity / result contracts

src/fabric_data_framework/metadata/config.py
  ReconciliationPolicy / ReconciliationCheck / check kinds

src/fabric_data_framework/quality/reconciliation/engine.py
  portable policy evaluation

src/fabric_data_framework/quality/reconciliation/scd2.py
  SCD2 base invariants + engine composition

src/fabric_data_framework/quality/reconciliation/full_replace.py
src/fabric_data_framework/quality/reconciliation/append.py
src/fabric_data_framework/quality/reconciliation/snapshot_diff.py
  strategy-specific base metrics + engine composition

src/fabric_data_framework/execution/
  publication/state gate integration

src/fabric_data_framework/deployment/delivery.py
  complete released policy materialization into Control Plane
```

Tests:

```text
tests/test_reconciliation_engine.py
tests/test_reconciliation_execution_gate.py
tests/test_reconciliation_metadata.py
```

## 16. Evidence boundary

Source tests and installed-wheel CI prove the portable framework contract only. They do not prove that every real Fabric SQL/Spark/provider observation adapter returns correct live evidence.

```text
source/CI reconciliation proof
!=
real Fabric reconciliation proof
```

Real Fabric status remains governed by the exact candidate certification lifecycle in `docs/TESTING_AND_CERTIFICATION.md` and `docs/internal/STATE.md`.
