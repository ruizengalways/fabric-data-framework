# Cheatsheet Pattern Alignment — fabric-data-framework

Status: Canonical design / active implementation checkpoint  
Last updated: 2026-08-29

## 1. Why this document exists

The external design reference used as the acceptance specification is:

- `https://github.com/ruizengalways/data-engineering-cheetsheet/blob/main/README.md`
- `https://github.com/ruizengalways/data-engineering-cheetsheet/blob/main/docs/pipeline-design-walkthrough.md`

The cheatsheet's governing mental model is:

```text
data semantics
  -> capture / delivery
  -> cursor / source position
  -> Bronze meaning
  -> Silver meaning
  -> fidelity / recovery
```

Those dimensions are intentionally orthogonal. A provider or transport name such as Debezium, Kafka, Delta CDF, API or file delivery must not silently define source semantics, Bronze meaning or history fidelity.

This document records the alignment gap discovered on 2026-08-29 and is the recovery point for future conversations.

## 2. Current baseline

At the time this alignment work started:

```text
main = 8ce4048bf69fe6c729ae6218995331e26ca60b78
public release = v0.3.0
source version = 0.4.0 development / unreleased
```

The approved-DEV evidence work remains separate. The unfinished evidence-merge work is retained on:

```text
codex/integration-evidence-merge
```

Do not discard or overwrite that branch when continuing capture-semantics work.

The capture-semantics alignment work starts on:

```text
codex/cheatsheet-capture-semantics
```

## 3. Important discovery: the two “14 pattern” lists are not the same taxonomy

The framework currently has fourteen `CapturePattern` enum members, but they mix several dimensions:

```text
FULL_SNAPSHOT             source/data semantics
WATERMARK_LOOKBACK        read-safety strategy
CDC_NET_CURRENT           change granularity + Bronze choice
CDC_FULL                  change granularity
TRANSACTION_LOG_CDC       capture mechanism
DEBEZIUM_KAFKA            capture + transport technology
DELTA_CDF                 provider technology
API_CURSOR_INCREMENTAL    delivery + cursor strategy
FILE_INCREMENTAL          delivery shape
EVENT_SOURCE              source semantics
```

The cheatsheet's fourteen rows instead describe semantic combinations such as:

```text
Full Snapshot -> Current Bronze
Full Snapshot -> Snapshot Bronze
Watermark + Lookback -> Current Bronze
Watermark + Lookback -> Raw Append Bronze
Net Changes -> Current Bronze
Net Changes -> Append Bronze
Full Changes -> Event Bronze
Full Changes -> Current Bronze (intentionally lossy)
```

Therefore “framework has 14 patterns” must not be interpreted as “framework exactly implements every cheatsheet row”.

## 4. Exact cheatsheet-row assessment before this work

| # | Cheatsheet semantic pattern | Current framework mapping | Assessment before alignment |
|---:|---|---|---|
| 1 | Full Snapshot -> Current Bronze | `FULL_SNAPSHOT` + `OVERWRITE` | SUPPORTED |
| 2 | Full Snapshot -> Snapshot Bronze | no first-class current mapping | GAP |
| 3 | Watermark -> Current Bronze | `WATERMARK_INCREMENTAL` + `MERGE` | SUPPORTED |
| 4 | Watermark + Lookback -> Current Bronze | `WATERMARK_LOOKBACK` + `MERGE` | SUPPORTED |
| 5 | Watermark + Lookback -> Raw Append Bronze | current pattern allows only `MERGE` | GAP |
| 6 | Watermark + Soft Delete -> Current Bronze | `WATERMARK_TOMBSTONE` | SUPPORTED |
| 7 | Watermark + Lookback + Soft Delete -> Raw Append Bronze | primitives exist but no exact combined contract | PARTIAL |
| 8 | Net Changes -> Current Bronze | `CDC_NET_CURRENT` | SUPPORTED |
| 9 | Net Changes -> Append Bronze | `CDC_NET_OBSERVATION` | SUPPORTED |
| 10 | Full / All Changes -> Event Bronze | `CDC_FULL` and provider variants | SUPPORTED |
| 11 | Full Changes -> Current Bronze, intentionally lossy | current state can be derived, but `CDC_FULL` Bronze is APPEND-only | PARTIAL |
| 12 | Business Events -> Event Bronze | `EVENT_SOURCE` | SUPPORTED semantic contract |
| 13 | Snapshot Diff -> Current | `SNAPSHOT_DIFF` + `MERGE` | SUPPORTED |
| 14 | Snapshot Diff -> Append Changes | `SNAPSHOT_DIFF` + `APPEND` | SUPPORTED |

Pre-alignment summary:

```text
10 supported
2 partial
2 gaps
```

This is a semantic-product assessment, not a real-provider evidence claim.

## 5. Four release-significant semantic gaps

### Gap A — recurring Full Snapshot -> Snapshot Bronze

The framework must represent periodic complete source pictures as immutable Bronze observations:

```text
snapshot_id | snapshot_time | business columns...
```

This is distinct from `SNAPSHOT_DIFF`. Snapshot Bronze stores the complete pictures; snapshot diff stores derived N-vs-N-1 changes.

Required contract properties:

```text
source semantics = CURRENT_STATE / complete snapshot
Bronze meaning   = SNAPSHOT_HISTORY
Bronze write     = APPEND
retry identity   = snapshot_id
history ceiling  = SNAPSHOT_GRAIN
```

### Gap B — Watermark + Lookback -> Raw Append Bronze

The framework must preserve intentionally repeated extraction observations:

```text
batch_001 | id=100 | source_version=501
batch_002 | id=100 | source_version=501   # lookback reread
batch_002 | id=100 | source_version=502
```

Bronze retains delivery/observation lineage. Silver collapses rereads using business key + source version/order and then materializes current state or observed history.

Required contract properties:

```text
source semantics = CURRENT_STATE
read strategy    = WATERMARK_LOOKBACK
Bronze meaning   = RAW_OBSERVATION
Bronze write     = APPEND
history ceiling  = OBSERVED_CHANGES
physical delete  = not visible unless another delete signal exists
```

### Gap C — Watermark + Lookback + Soft Delete -> Raw Append Bronze

This combines three independent concerns:

```text
lookback protects against late/missed reads
soft-delete/tombstone row makes delete observable
raw append preserves every extraction observation
```

The model must not require a combinatorial enum such as `WATERMARK_LOOKBACK_TOMBSTONE_RAW_APPEND`.

### Gap D — Full Changes -> Current Bronze (intentionally lossy)

A full ordered change feed may intentionally be collapsed before current Bronze:

```text
ordered full changes
  -> collapse/apply per business key
  -> final state in bounded window
  -> MERGE current Bronze
```

This must be explicitly labelled lossy. It must never claim Event Bronze or full replay history after the collapse.

## 6. Target model: orthogonal semantic dimensions

The framework should move toward a composition model rather than adding more large combined enum names.

Target dimensions:

```text
SourceSemantics
  CURRENT_STATE
  CHANGE_FEED
  BUSINESS_EVENT

ChangeGranularity
  CURRENT
  SNAPSHOT
  NET
  FULL
  EVENT
  SOURCE_DEFINED

ReadStrategy
  FULL
  WATERMARK
  WATERMARK_LOOKBACK
  CURSOR
  LOG_POSITION
  OFFSET
  COMMIT_VERSION
  FILE_MANIFEST
  SOURCE_DEFINED

DeleteSemantics
  NONE
  SNAPSHOT_ABSENCE
  SOFT_DELETE
  TOMBSTONE_EVENT
  EXPLICIT_EVENT
  SOURCE_DEFINED

BronzeContract
  CURRENT
  RAW_OBSERVATION
  SNAPSHOT_HISTORY
  EVENT

HistoryFidelity
  NONE
  OBSERVED_CHANGES
  BATCH_GRAIN
  SNAPSHOT_GRAIN
  FULL_EVENT
  SOURCE_DEFINED
```

Provider/execution selection stays separate:

```text
DB_QUERY
FABRIC_COPY_JOB
FABRIC_COPY_ACTIVITY
DATAFLOW_GEN2
SPARK
NATIVE_CDC
DEBEZIUM_KAFKA
DELTA_CDF
API
FILE
KAFKA
...
```

A provider cannot increase source fidelity.

## 7. Backward compatibility rule

Do not break existing `CapturePattern` consumers in the first slice.

Implementation strategy:

```text
new orthogonal semantic contract
        ^
        |
legacy CapturePattern -> compatibility projection / preset
```

`CapturePattern` becomes a convenience/onboarding preset over the orthogonal contract rather than the only semantic truth.

New combinations should be expressible without adding one enum member for every Cartesian-product combination.

## 8. Cheatsheet acceptance specification

The cheatsheet fourteen-row table becomes an executable acceptance specification.

For every row the framework tests must assert at least:

```text
source semantics
change granularity
read strategy / progress coordinate class
physical-delete visibility
delete semantics
Bronze contract
Bronze write mode
retry/replay identity intent
Silver current / SCD1 compatibility
SCD2/history fidelity ceiling
intentional-loss warning where applicable
```

A future cheatsheet mainstream pattern addition must produce an explicit framework status:

```text
SUPPORTED
PARTIAL
UNSUPPORTED
```

Documentation and code must not silently drift.

## 9. Related non-pattern gaps that remain important

### Watermark bootstrap

CDC already has a first-class snapshot-fence bootstrap contract. The equivalent full-baseline -> watermark handoff is not yet at the same evidence level and should be added after the semantic model stabilizes.

Expected shape:

```text
freeze/capture initial high watermark W
obtain complete baseline proven consistent through W
commit baseline
start incremental strictly after the defined W boundary
```

Exact ordering depends on the source isolation/version contract and must fail closed if no-gap proof is unavailable.

### Retroactive SCD2

Normal deterministic SCD2 exists. Automatic retroactive/back-dated business-effective history rewrite remains intentionally unsupported. A newer captured source event with an earlier valid-time that requires rewriting committed history should continue to fail closed unless an explicit rewrite policy is introduced.

### Provider runtime evidence

Semantic support does not imply live provider proof. Real Fabric, Kafka, Delta CDF and production SQL evidence remain governed by `PRODUCTION_READINESS_AUDIT.md` and `DEV_INTEGRATION_EVIDENCE.md`.

## 10. Implementation order from this checkpoint

1. add orthogonal capture semantic models without breaking legacy `CapturePattern`;
2. encode all fourteen cheatsheet rows as named semantic presets / acceptance cases;
3. add executable tests for all fourteen rows;
4. close the four semantic gaps listed above at contract level;
5. wire legacy pattern projection and onboarding validation to the new semantic truth;
6. add full-baseline -> watermark bootstrap evidence contract;
7. update `CAPTURE_PATTERN_CATALOG.md`, `GUARANTEE_COVERAGE.md`, `CURRENT_STATUS.md` and readiness docs with exact CI evidence;
8. resume approved-DEV evidence execution and the separate integration-evidence merge work;
9. do not release `0.4.0` until exact-candidate semantic/docs/CI state and retained real evidence agree.

## 11. Evidence language

Until real service evidence exists, the correct labels remain:

```text
IMPLEMENTED reference
CI PROVEN reference
ADAPTER CONTRACT
IMPLEMENTED + CI PROVEN ... CONTRACT
```

Do not call these changes `FABRIC PROVEN`, `PRODUCTION DB PROVEN`, `KAFKA PROVEN` or equivalent merely because deterministic tests pass.
