# Cheatsheet Pattern Alignment — fabric-data-framework

Status: Canonical recovery/design checkpoint  
Last updated: 2026-08-29

## 1. External acceptance specification

Semantic reference:

- `https://github.com/ruizengalways/data-engineering-cheetsheet/blob/main/README.md`
- `https://github.com/ruizengalways/data-engineering-cheetsheet/blob/main/docs/pipeline-design-walkthrough.md`

Governing model:

```text
data semantics
  -> capture / delivery
  -> cursor / source position
  -> Bronze meaning
  -> Silver meaning
  -> fidelity / recovery
```

Provider names do not silently define source semantics, Bronze meaning or history fidelity.

## 2. Current baseline

```text
public release = v0.3.0
source         = 0.4.0 development / unreleased
current main   = 014cd334105de6f867b6320509b94147a444a2fa
latest CI      = Actions 33253817758
full tests     = 455
```

Relevant merged slices:

```text
PR #34 -> 1c7d67bedd125f5fb5e983be791085fd1eaa9b0e
  exact 14 cheatsheet semantic presets
  Actions 33253215030 / 419 tests

PR #35 -> bf215fcb3538f9806b4002d2f154dbd46ae19412
  semantic onboarding validation + CLI
  Actions 33253394201 / 430 tests

PR #37 -> d69b2ff49f984331b6753bcd9274ea9a298ce798
  full-baseline -> WATERMARK bootstrap
  Actions 33253581049 / 441 tests

PR #39 -> 014cd334105de6f867b6320509b94147a444a2fa
  staged integration evidence merge + CLI/runbook
  Actions 33253817758 / 455 tests
```

## 3. Original taxonomy problem

The original framework `CapturePattern` enum mixed orthogonal dimensions:

```text
FULL_SNAPSHOT             source semantics
WATERMARK_LOOKBACK        read strategy
CDC_NET_CURRENT           change granularity + Bronze choice
TRANSACTION_LOG_CDC       capture mechanism
DEBEZIUM_KAFKA            provider + transport
DELTA_CDF                 provider technology
API_CURSOR_INCREMENTAL    delivery + cursor
FILE_INCREMENTAL          delivery shape
```

The cheatsheet's fourteen rows are semantic combinations such as:

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

Pre-alignment assessment:

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

## 4. Current orthogonal semantic model

`capture/semantic_contracts.py` separates:

```text
SourceSemantics
ChangeGranularity
ReadStrategy
DeleteSemantics
BronzeContract
HistoryFidelity
CaptureProviderFamily
```

`CheatsheetPattern` provides exact presets:

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

At the **semantic-contract + onboarding-validation level, all fourteen cheatsheet rows are first-class and tested**.

Legacy `CapturePattern` remains supported through `project_legacy_capture_pattern()` and must not be removed until domain repositories have a deliberate migration path.

## 5. Semantic onboarding

Domain repos can declare:

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

CI:

```bash
fabric-framework capture-semantic-onboarding-validate \
  --config-dir config/datasets \
  --selections config/capture-semantic-selections.json \
  --require-all
```

Validation fails closed for semantic/config mismatch, invalid overlap choice, overstated history/delete claims, unknown datasets and missing classifications.

## 6. Bootstrap contracts

### Snapshot -> CDC

Existing CDC bootstrap requires complete snapshot consistency through a retained CDC boundary and applies only changes strictly beyond the snapshot-covered fence.

### Full baseline -> WATERMARK

PR #37 adds provider-neutral evidence requiring:

```text
complete authoritative baseline
baseline consistent through exact boundary W
verified deterministic watermark ordering
post-W changes remain visible after W is committed
```

Strict mode reads composite positions `> W` and requires deterministic tie-breaker semantics. Lookback mode intentionally rereads overlap and requires idempotent downstream processing.

A generic `updated_at` column is not automatically sufficient bootstrap proof.

## 7. Current scope truth

```text
14 cheatsheet semantic combinations             IMPLEMENTED + CI PROVEN reference
semantic onboarding / overclaim guardrails       IMPLEMENTED + CI PROVEN reference
snapshot -> CDC bootstrap                        IMPLEMENTED + CI PROVEN reference
full baseline -> watermark bootstrap             IMPLEMENTED + CI PROVEN reference
staged integration evidence merge                IMPLEMENTED + CI PROVEN evidence merge contract
UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF             broad reference implementation
provider-specific runtime                        varies
real approved DEV Fabric execution               NOT YET PROVEN
real production SQL backend                      NOT YET PROVEN
enterprise controls                              EXTERNAL / NOT YET RETAINED
```

Capture fidelity remains an upper bound on history fidelity.

## 8. Staged evidence merge is now complete

The original experimental work was preserved on `codex/integration-evidence-merge` at `d50769f3926e07d291c950199c1fa2e74b82c59c` and then ported onto current main in PR #39.

Canonical runbook:

```text
INTEGRATION_EVIDENCE_MERGE.md
```

Command:

```bash
fabric-framework integration-evidence-merge \
  --spec evidence-spec.json \
  --input evidence/item-read.json \
  --input evidence/control-plane.json \
  --output evidence/merged.json
```

Rules:

```text
NOT_RUN = absence
one substantive result = retain unchanged
identical substantive duplicate = allowed
different substantive rerun evidence = conflict
no latest/PASS-wins/FAIL-wins arbitration
```

Merge/certification validation happens before output write, so conflicts and failed `--require-certified` gates do not overwrite retained output.

## 9. Intentionally unresolved boundaries

### Retroactive SCD2

Automatic back-dated business-effective rewrite of already committed history remains intentionally unsupported/fail-closed unless an explicit rewrite policy is introduced.

### Provider-specific clients

API/file/Kafka/Delta semantics and recovery contracts do not imply every possible connector/client is embedded. Add integrations only when product scope requires them.

### Real provider proof

Deterministic CI does not prove Fabric, Kafka, Delta CDF or production SQL service behavior.

## 10. Recommended continuation order

1. add environment-variable-driven approved-run control-plane certification runner;
2. synchronize/read `CURRENT_STATUS.md`, `GUARANTEE_COVERAGE.md`, `PRODUCTION_READINESS_AUDIT.md` before real execution;
3. replace placeholder DEV release hash/item UUIDs with exact candidate values;
4. run approved read-only item preflight + live item smoke;
5. run real selected control-plane backend certification;
6. merge retained partial evidence;
7. only then authorize representative Pipeline/Copy/Spark/Warehouse mutation/failure drills;
8. prove Kafka/Delta live only if included in `0.4.0` public scope;
9. do not publish `0.4.0` until exact-candidate code/tests/docs and retained real evidence agree.

## 11. Evidence language

Use:

```text
IMPLEMENTED reference
CI PROVEN reference
ADAPTER CONTRACT
IMPLEMENTED + CI PROVEN ... CONTRACT
```

Do not promote semantic/bootstrap/evidence-merge CI to real-service evidence labels.
