# Cheatsheet Pattern Alignment — fabric-data-framework

Status: Canonical recovery/design checkpoint  
Last updated: 2026-08-29

## 1. External acceptance specification

Use these as the semantic reference when evaluating mainstream data-engineering patterns:

- `https://github.com/ruizengalways/data-engineering-cheetsheet/blob/main/README.md`
- `https://github.com/ruizengalways/data-engineering-cheetsheet/blob/main/docs/pipeline-design-walkthrough.md`

Governing mental model:

```text
data semantics
  -> capture / delivery
  -> cursor / source position
  -> Bronze meaning
  -> Silver meaning
  -> fidelity / recovery
```

Provider/transport names such as Debezium, Kafka, Delta CDF, API or files are not allowed to silently define source semantics, Bronze meaning or history fidelity.

## 2. Baseline and merged implementation

Alignment work started from:

```text
main = 8ce4048bf69fe6c729ae6218995331e26ca60b78
public release = v0.3.0
source version = 0.4.0 development / unreleased
```

Merged semantic alignment slices:

```text
PR #34 -> 1c7d67bedd125f5fb5e983be791085fd1eaa9b0e
orthogonal capture semantic contracts + 14 cheatsheet acceptance presets
Actions 33253215030
Python 3.11 / 3.13 / static / wheel SUCCESS
expected 419 tests (407 baseline + 12 new acceptance tests)

PR #35 -> bf215fcb3538f9806b4002d2f154dbd46ae19412
cheatsheet semantic onboarding validation + CLI gate
Actions 33253394201
Python 3.11 / 3.13 / static / wheel SUCCESS
expected 430 tests (419 post-#34 baseline + 11 new tests)
```

Correct evidence label for both slices:

```text
IMPLEMENTED + CI PROVEN REFERENCE
```

They are not live Fabric/provider evidence.

## 3. Why this alignment was needed

Before PR #34 the framework had fourteen `CapturePattern` enum members, but that enum mixed several independent dimensions:

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

The cheatsheet fourteen rows instead describe semantic combinations such as:

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

Therefore the previous statement “framework has 14 patterns” did not mean “framework exactly models the cheatsheet 14 rows”.

## 4. Pre-alignment assessment

| # | Cheatsheet semantic pattern | Pre-alignment status |
|---:|---|---|
| 1 | Full Snapshot -> Current Bronze | SUPPORTED |
| 2 | Full Snapshot -> Snapshot Bronze | GAP |
| 3 | Watermark -> Current Bronze | SUPPORTED |
| 4 | Watermark + Lookback -> Current Bronze | SUPPORTED |
| 5 | Watermark + Lookback -> Raw Append Bronze | GAP |
| 6 | Watermark + Soft Delete -> Current Bronze | SUPPORTED |
| 7 | Watermark + Lookback + Soft Delete -> Raw Append Bronze | PARTIAL |
| 8 | Net Changes -> Current Bronze | SUPPORTED |
| 9 | Net Changes -> Append Bronze | SUPPORTED |
| 10 | Full / All Changes -> Event Bronze | SUPPORTED |
| 11 | Full Changes -> Current Bronze, intentionally lossy | PARTIAL |
| 12 | Business Events -> Event Bronze | SUPPORTED semantic contract |
| 13 | Snapshot Diff -> Current | SUPPORTED |
| 14 | Snapshot Diff -> Append Changes | SUPPORTED |

Pre-alignment summary:

```text
10 supported
2 partial
2 gaps
```

## 5. What PR #34 changed

New module:

```text
src/fabric_data_framework/capture/semantic_contracts.py
```

New orthogonal dimensions:

```text
SourceSemantics
  CURRENT_STATE
  CHANGE_FEED
  BUSINESS_EVENT
  SOURCE_DEFINED

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
  CHANGE_WINDOW
  SOURCE_POSITION
  PARTITION_OFFSET
  COMMIT_VERSION
  CURSOR
  FILE_MANIFEST
  SOURCE_DEFINED

DeleteSemantics
  NONE
  SNAPSHOT_ABSENCE
  SOFT_DELETE
  EXPLICIT_EVENT
  SOURCE_DEFINED

BronzeContract
  CURRENT
  RAW_OBSERVATION
  SNAPSHOT_HISTORY
  EVENT
```

`CaptureSemanticContract` also carries:

```text
BronzeWriteMode
HistoryFidelity
retry identity intent
SCD1/SCD2 compatibility flags
intentional-loss marker
guidance
```

All fourteen cheatsheet rows are now executable named presets through `CheatsheetPattern` and `cheatsheet_pattern_contract()`.

The four previous semantic gaps are now expressible directly:

```text
FULL_SNAPSHOT_HISTORY
WATERMARK_LOOKBACK_RAW
WATERMARK_LOOKBACK_SOFT_DELETE_RAW
FULL_CHANGES_CURRENT_LOSSY
```

This closes the **semantic-contract representation gap**. It does not by itself prove every physical runtime path in Fabric.

## 6. Backward compatibility

Legacy `CapturePattern` remains supported.

PR #34 added:

```text
project_legacy_capture_pattern()
```

which projects the existing combined preset into:

```text
orthogonal semantic contract
+
separate CaptureProviderFamily
```

Examples:

```text
DEBEZIUM_KAFKA
  -> source semantics = CHANGE_FEED
  -> granularity = FULL
  -> read strategy = PARTITION_OFFSET
  -> provider family = DEBEZIUM_KAFKA

DELTA_CDF
  -> source semantics = CHANGE_FEED
  -> granularity = FULL
  -> read strategy = COMMIT_VERSION
  -> provider family = DELTA_CDF

API_CURSOR_INCREMENTAL
  -> semantics/fidelity = SOURCE_DEFINED
  -> read strategy = CURSOR
  -> provider family = API
```

Do not remove or rename legacy `CapturePattern` until downstream domain repositories have a deliberate migration path.

## 7. What PR #35 changed

New source-controlled onboarding model:

```text
DatasetSemanticCaptureSelection
```

A domain repo can now declare an exact cheatsheet semantic preset instead of being forced into the legacy combined enum.

Example:

```json
{
  "dataset_id": "crm.customer",
  "cheatsheet_pattern": "WATERMARK_LOOKBACK_RAW",
  "history_claim": "OBSERVED_CHANGES",
  "delete_claim": "NONE",
  "rationale": "Keep extraction observations and collapse rereads in Silver.",
  "known_limitations": [
    "Hard deletes are not visible."
  ]
}
```

Validation now fails closed when:

```text
semantic preset and DatasetConfig.capture_strategy disagree
WATERMARK_LOOKBACK has no positive overlap
strict WATERMARK is selected while overlap_window_seconds > 0
history claim contradicts the semantic ceiling
delete claim contradicts the semantic contract
selection references an unknown dataset
--require-all finds an unclassified DatasetConfig
```

Review warnings include:

```text
bounded/source-defined history without documented limitations
soft-delete semantics selected while delete_policy=IGNORE
current-only/lossy Full Changes collapse
```

New CLI:

```bash
fabric-framework capture-semantic-onboarding-validate \
  --config-dir config/datasets \
  --selections config/capture-semantic-selections.json \
  --require-all \
  --output evidence/capture-semantic-onboarding.json
```

The legacy command remains available:

```text
capture-onboarding-validate
```

## 8. Current truth about the cheatsheet 14 rows

At the **semantic-contract + onboarding-validation level**, all fourteen cheatsheet rows are now first-class expressible/tested presets.

That means the old `10 supported / 2 partial / 2 gap` assessment is no longer the current semantic-model result.

However, do not translate that into the stronger claim “every row has been proven end-to-end on every physical provider”.

Current distinction:

```text
semantic representation / validation    YES for all 14 cheatsheet rows
portable/reference apply primitives      broad existing coverage
provider-specific transport/runtime      varies by provider/path
real approved DEV service proof          still incomplete
production enterprise proof              still external/incomplete
```

## 9. Next release-significant semantic/runtime gap: watermark bootstrap

CDC already has a first-class no-gap/no-double-apply snapshot-fence bootstrap contract.

The next reusable semantic gap is the equivalent initial full baseline -> watermark incremental handoff.

Target evidence shape:

```text
establish/freeze initial source high watermark W
        ↓
obtain complete baseline proven consistent through W
        ↓
commit baseline
        ↓
start steady-state incremental after the defined W boundary
```

The implementation must not assume every timestamp watermark can prove this safely. It should make source isolation/version evidence explicit and fail closed when no-gap proof is unavailable.

Expected work:

```text
WatermarkBootstrapEvidence
WatermarkBootstrapPlan
boundary/tie-breaker semantics
complete-baseline evidence
source-consistency evidence
safe first incremental lower bound
retry/replay identity
negative tests for gap/double-apply ambiguity
```

## 10. Other intentionally unresolved boundaries

### Retroactive SCD2

Normal deterministic SCD2 exists. Automatic back-dated business-effective history rewrite remains intentionally unsupported. Newer captured source data that would require rewriting committed earlier valid-time history should remain fail-closed unless an explicit rewrite policy is introduced.

### Physical provider proof

Semantic support does not imply live provider proof. Real Fabric, Kafka, Delta CDF and production SQL evidence remain governed by:

```text
PRODUCTION_READINESS_AUDIT.md
DEV_INTEGRATION_EVIDENCE.md
```

### Provider-specific runtime clients

API/file/Kafka/Delta semantics and recovery contracts are not the same thing as having every possible provider connector/client embedded in the package. Provider integrations should be added only where product scope requires them.

## 11. Parallel unfinished evidence work — do not lose

The earlier partial integration-evidence merge implementation remains on:

```text
codex/integration-evidence-merge
```

Known commit on that branch:

```text
d50769f3926e07d291c950199c1fa2e74b82c59c
```

It contains `integration_evidence_merge.py` with strict staged-manifest conflict semantics.

Still required there:

```text
tests
CLI integration-evidence-merge
docs
PR/CI/merge
```

Do not overwrite or forget that branch while doing capture semantics.

## 12. Current recommended continuation order

1. implement full-baseline -> watermark bootstrap evidence contract and tests;
2. synchronize `CAPTURE_PATTERN_CATALOG.md`, `GUARANTEE_COVERAGE.md`, `CURRENT_STATUS.md` and readiness docs with the new merged semantic baseline;
3. finish/merge `codex/integration-evidence-merge`;
4. continue exact-release approved DEV read-only evidence and real control-plane certification;
5. only then authorize representative real Pipeline/Copy/Spark/Warehouse mutation/failure drills;
6. keep Kafka/Delta live proof conditional on `0.4.0` release scope;
7. do not publish `0.4.0` until exact-candidate code/tests/docs and retained approved real evidence agree.

## 13. Evidence language

Use:

```text
IMPLEMENTED reference
CI PROVEN reference
ADAPTER CONTRACT
IMPLEMENTED + CI PROVEN ... CONTRACT
```

Do not call these semantic/onboarding changes `FABRIC PROVEN`, `PRODUCTION DB PROVEN`, `KAFKA PROVEN` or equivalent merely because deterministic CI is green.
