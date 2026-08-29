# Cheatsheet Pattern Alignment — fabric-data-framework

Status: Canonical recovery/design checkpoint  
Last updated: 2026-08-29

## 1. External acceptance specification

Use these as the semantic reference for mainstream data-engineering patterns:

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

Provider/transport names such as Debezium, Kafka, Delta CDF, API or files do not silently define source semantics, Bronze meaning or history fidelity.

## 2. Current merged baseline

Public release remains:

```text
v0.3.0
```

Source remains:

```text
0.4.0 development / unreleased
```

Latest capture-semantics baselines:

```text
PR #34 -> 1c7d67bedd125f5fb5e983be791085fd1eaa9b0e
orthogonal capture semantic contracts + exact 14 cheatsheet presets
Actions 33253215030
419 tests

PR #35 -> bf215fcb3538f9806b4002d2f154dbd46ae19412
semantic onboarding selection/validation + CLI gate
Actions 33253394201
430 tests

PR #36 -> 95b070159aa5efe705a752da737ab483439c6b1f
canonical docs checkpoint
Actions 33253488946

PR #37 -> d69b2ff49f984331b6753bcd9274ea9a298ce798
full-baseline -> WATERMARK bootstrap evidence contract
Actions 33253581049
441 tests
Python 3.11 / 3.13 / static / wheel SUCCESS
```

Correct evidence label for #34/#35/#37:

```text
IMPLEMENTED + CI PROVEN REFERENCE
```

None of these commits is live Fabric/provider proof.

## 3. Why the capture model changed

The original fourteen `CapturePattern` values mixed independent dimensions:

```text
FULL_SNAPSHOT             source semantics
WATERMARK_LOOKBACK        read-safety strategy
CDC_NET_CURRENT           change granularity + Bronze choice
TRANSACTION_LOG_CDC       capture mechanism
DEBEZIUM_KAFKA            provider + transport
DELTA_CDF                 provider technology
API_CURSOR_INCREMENTAL    delivery + cursor
FILE_INCREMENTAL          delivery shape
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

Pre-alignment assessment was:

```text
10 supported
2 partial
2 gaps
```

The missing/partial combinations were:

```text
Full Snapshot -> Snapshot Bronze
Watermark + Lookback -> Raw Append Bronze
Watermark + Lookback + Soft Delete -> Raw Append Bronze
Full Changes -> Current Bronze (intentionally lossy)
```

## 4. Current semantic model

`src/fabric_data_framework/capture/semantic_contracts.py` separates:

```text
SourceSemantics
ChangeGranularity
ReadStrategy
DeleteSemantics
BronzeContract
HistoryFidelity
CaptureProviderFamily
```

`CaptureSemanticContract` also carries Bronze write mode, retry/replay identity intent, SCD compatibility, intentional-loss marker and guidance.

Exact cheatsheet presets are represented by `CheatsheetPattern`:

```text
FULL_SNAPSHOT_CURRENT
FULL_SNAPSHOT_HISTORY
WATERMARK_CURRENT
WATERMARK_LOOKBACK_CURRENT
WATERMARK_LOOKBACK_RAW
WATERMARK_SOFT_DELETE_CURRENT
WATERMARK_LOOKBACK_SOFT_DELETE_RAW
NET_CHANGES_CURRENT
NET_CHANGES_APPEND
FULL_CHANGES_EVENT
FULL_CHANGES_CURRENT_LOSSY
BUSINESS_EVENTS
SNAPSHOT_DIFF_CURRENT
SNAPSHOT_DIFF_APPEND
```

At the **semantic-contract + onboarding-validation level, all fourteen cheatsheet rows are now first-class and tested**.

This statement does not mean every physical execution path is live-provider proven.

## 5. Backward compatibility

Legacy `CapturePattern` remains supported.

```text
project_legacy_capture_pattern()
```

projects the combined legacy preset into:

```text
orthogonal semantic contract
+
CaptureProviderFamily
```

Examples:

```text
DEBEZIUM_KAFKA
  semantics = CHANGE_FEED / FULL
  read = PARTITION_OFFSET
  provider = DEBEZIUM_KAFKA

DELTA_CDF
  semantics = CHANGE_FEED / FULL
  read = COMMIT_VERSION
  provider = DELTA_CDF

API_CURSOR_INCREMENTAL
  semantics/fidelity = SOURCE_DEFINED
  read = CURSOR
  provider = API
```

Do not remove or rename the legacy enum until domain repositories have a deliberate migration path.

## 6. Semantic onboarding contract

Domain repositories can use:

```text
DatasetSemanticCaptureSelection
```

Example:

```json
{
  "dataset_id": "crm.customer",
  "cheatsheet_pattern": "WATERMARK_LOOKBACK_RAW",
  "history_claim": "OBSERVED_CHANGES",
  "delete_claim": "NONE",
  "rationale": "Keep extraction observations and collapse rereads in Silver.",
  "known_limitations": ["Hard deletes are not visible."]
}
```

CI command:

```bash
fabric-framework capture-semantic-onboarding-validate \
  --config-dir config/datasets \
  --selections config/capture-semantic-selections.json \
  --require-all \
  --output evidence/capture-semantic-onboarding.json
```

Validation fails closed for semantic/config mismatch, missing lookback overlap, strict-watermark config with positive overlap, overstated history/delete claims, unknown datasets and `--require-all` omissions.

## 7. Full-baseline -> WATERMARK bootstrap is now implemented

PR #37 added:

```text
src/fabric_data_framework/capture/bootstrap_watermark.py
```

Main contracts:

```text
WatermarkBootstrapEvidence
WatermarkBootstrapPlan
plan_watermark_bootstrap()
plan_first_watermark_batch()
assert_same_watermark_bootstrap()
```

A safe handoff requires explicit evidence that:

```text
baseline is complete and authoritative
baseline is consistent through exact boundary W
watermark ordering is deterministic
future/post-W changes remain visible after W is committed
```

The framework intentionally does **not** assume a generic `updated_at` column proves those properties.

Strict mode:

```text
complete baseline through composite W
  -> commit W
  -> first incremental reads positions > W
```

Strict mode requires deterministic tie-breaker semantics.

Lookback mode:

```text
complete baseline through W
  -> commit W
  -> first incremental intentionally rereads overlap
```

The plan records that baseline rows may be reread and that downstream processing must be idempotent.

Retry/replay must reuse the exact bootstrap fence evidence; silently changing snapshot/boundary/source epoch is rejected.

This closes the reusable provider-neutral watermark bootstrap contract. A specific source/provider still has to prove that it can satisfy the evidence fields.

## 8. Current scope truth

```text
14 cheatsheet semantic combinations             IMPLEMENTED + CI PROVEN reference
semantic onboarding / overclaim guardrails       IMPLEMENTED + CI PROVEN reference
snapshot -> CDC bootstrap                        IMPLEMENTED + CI PROVEN reference
full baseline -> watermark bootstrap             IMPLEMENTED + CI PROVEN reference
UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF             broad reference implementation
provider-specific capture/runtime                varies by provider
real approved DEV Fabric execution               NOT YET PROVEN
real production SQL backend                      NOT YET PROVEN
enterprise IAM/network/DR/governance              EXTERNAL / NOT YET RETAINED
```

Capture fidelity remains an upper bound on history fidelity.

## 9. Intentionally unresolved boundaries

### Retroactive SCD2

Automatic back-dated business-effective history rewrite remains intentionally unsupported. If newer captured data would require rewriting already committed earlier valid-time history, normal execution remains fail-closed unless a separate explicit rewrite policy is introduced.

### Provider-specific runtime clients

API/file/Kafka/Delta semantic and recovery contracts are not equivalent to having every possible connector/client embedded in this package. Add provider integrations only where product scope requires them.

### Real provider proof

Passing deterministic tests does not prove Fabric, Kafka, Delta CDF or production SQL service behavior. Real evidence remains governed by `PRODUCTION_READINESS_AUDIT.md` and `DEV_INTEGRATION_EVIDENCE.md`.

## 10. Parallel unfinished evidence work — preserve and resume next

The earlier staged integration-evidence merge implementation remains on:

```text
codex/integration-evidence-merge
```

Known commit:

```text
d50769f3926e07d291c950199c1fa2e74b82c59c
```

It contains `integration_evidence_merge.py` with strict conflict semantics:

```text
NOT_RUN behaves as absence
one substantive result is retained
identical duplicate substantive results are allowed
different substantive results for the same check -> conflict
no latest/PASS-wins/FAIL-wins arbitration
```

Still required:

```text
port/rebase the implementation onto current main
tests
CLI integration-evidence-merge
docs
PR / full CI / merge
```

Do not discard the original branch while porting it.

## 11. Recommended continuation order

1. finish and merge staged integration-evidence accumulation/merge on top of current main;
2. update `CURRENT_STATUS.md`, `GUARANTEE_COVERAGE.md` and `PRODUCTION_READINESS_AUDIT.md` with the #34-#37 baselines;
3. add environment-variable-driven real control-plane certification runner;
4. run exact-release approved DEV read-only item evidence;
5. run real control-plane certification;
6. only after prerequisites pass, explicitly authorize representative Pipeline/Copy/Spark/Warehouse runs and failure drills;
7. prove live Kafka/Delta only if included in the `0.4.0` public promise;
8. do not publish `0.4.0` until code/tests/docs and retained approved real evidence agree.

## 12. Evidence language

Use:

```text
IMPLEMENTED reference
CI PROVEN reference
ADAPTER CONTRACT
IMPLEMENTED + CI PROVEN ... CONTRACT
```

Do not call semantic/bootstrap CI `FABRIC PROVEN`, `PRODUCTION DB PROVEN`, `KAFKA PROVEN` or equivalent.
