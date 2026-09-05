# MACHINE CAPABILITY MATRIX

Evidence vocabulary:

```text
REFERENCE / CONTRACT       deterministic semantic/runtime implementation
CI PROVEN                  tests/build succeeded for the stated source baseline
RELEASE PROVEN             immutable published artifact/checksum evidence
FABRIC/PRODUCTION PROVEN   retained approved real-service evidence for exact release
EXTERNAL                   enterprise/platform control outside this repository
```

## Semantic / runtime guarantees

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Immutable DatasetConfig / effective config hashing | `metadata/config.py` | REFERENCE + CI PROVEN PR #107 |
| Capture/Bronze semantic presets | `capture/semantic_contracts.py` | REFERENCE + CI PROVEN |
| FULL/WATERMARK/CDC and SCD1/SCD2 orthogonality | metadata/capture/apply | REFERENCE MODEL + CI PROVEN |
| APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF | `apply/` | REFERENCE + CI PROVEN |
| Provider-neutral CDC order/dedupe/checkpoint | capture/data-plane CDC modules | REFERENCE + CI PROVEN |
| Debezium/Kafka and Delta CDF recovery contracts | CDC adapters | ADAPTER/RECOVERY CONTRACT + CI PROVEN |
| Typed CaptureReceipt / progress authority | contracts/capabilities | REFERENCE + CI PROVEN |
| Parent Pipeline fault isolation + fail-at-end aggregation | orchestration planner/dispatcher | REFERENCE + CI PROVEN PR #107 |
| Source-controlled execution-group defaults + per-dataset DQ patch | `contracts/group_policy.py` + planner | REFERENCE + CI PROVEN PR #107 |
| DQ enable/quarantine switches + absolute/fraction quarantine budgets | metadata + dataset runner | REFERENCE + CI PROVEN PR #107 |
| Governed detailed quarantine payload + replay reference | `quality/quarantine_store.py` + recovery replay | REFERENCE + CI PROVEN PR #107 |
| Conservative Pipeline recovery recommendation plan | `recovery/pipeline.py` | REFERENCE + CI PROVEN PR #107 |
| Bounded retry / immutable attempt lineage / unknown-commit reconcile-before-retry | `recovery/runtime.py` | REFERENCE + CI PROVEN; composed by PR #107 recovery guidance |

PR #107 exact executable checkpoint:

```text
merge/main SHA       4c8ad9994f3800e901c146b919f85454d78f080e
final PR CI          33967940246 SUCCESS
independent main CI  33968014547 SUCCESS
Python 3.11          SUCCESS
Python 3.13          SUCCESS
build-wheel          SUCCESS
readiness contract   SUCCESS / release_ready=false
```

Semantic support is not live provider certification. Capture fidelity still upper-bounds truthful downstream history fidelity.

## Normal runtime failure/recovery contract

```text
independent dataset failure
  -> record dataset_run failure
  -> continue independent siblings
  -> block only dependents
  -> aggregate parent after terminal states

explicit retryable transient
  -> bounded retry + backoff + attempt lineage

DQ threshold exceeded
  -> retain quarantine detail
  -> fail dataset before target/state commit
  -> fix data/rule then audited REPLAY

reconciliation failed
  -> no state advance
  -> investigate before reprocess

unknown/ambiguous commit
  -> no blind retry
  -> reconcile operation/target evidence first

bounded source gap
  -> BACKFILL

authoritative reset only
  -> FULL_REBUILD
```

Execution-group policy precedence is:

```text
DatasetConfig
-> group defaults
-> group per-dataset patch
-> audited RuntimeOverride
```

When group policies are supplied to release/config bundle construction, their exact content participates in config-bundle identity. Dataset-only projects preserve the historical hash algorithm.

## Customer/domain project contract

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Non-destructive project scaffold | `deployment/project.py` | REFERENCE + CI PROVEN |
| `project-init` / `project-validate` | CLI + deployment project | PRESENTATION/REFERENCE + CI PROVEN |
| Dependency/cycle/capability validation | `deployment/project.py` | REFERENCE + CI PROVEN fail-closed |
| Exact semantic-selection coverage / overclaim guard | deployment + capture onboarding | REFERENCE + CI PROVEN fail-closed |
| Mixed FULL/WATERMARK/CDC + SCD1/SCD2 in one domain repo | DatasetConfig + project contract | REFERENCE MODEL + CI PROVEN |
| Execution-group policy file loading / release identity | deployment delivery | REFERENCE + CI PROVEN PR #107 |
| Customer 100-table product Pipeline examples | `fabric-customer` PR #25 | CUSTOMER PR + MAIN CI PROVEN; production pin remains v0.3.0 |

Customer PR #25 reference identity:

```text
customer merge/main     1d70fe26baf3ceef1be7c0b0cd359f330316e0ee
customer PR CI          33969274525 SUCCESS
customer cert PR CI     33969274509 SUCCESS
customer main CI        33969382068 SUCCESS
customer cert main CI   33969382063 SUCCESS
framework compat SHA    4c8ad9994f3800e901c146b919f85454d78f080e
production dependency   fabric-data-framework==0.3.0
```

Project validation is static/local. Customer 0.4 execution-group examples are forward-looking compatibility/reference inputs; they are not production migration evidence.

## Fabric/provider execution

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Fabric Data Pipeline backend | execution backend | IMPLEMENTED + CI PROVEN BACKEND |
| Copy Job REST transport | Fabric Copy adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Spark Job Definition REST transport | Fabric Spark adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Provider Completed insufficient for semantic success | Pipeline/capture adapters | REFERENCE + CI PROVEN |
| Fabric Warehouse same-transaction target marker | Warehouse recovery | IMPLEMENTED + CI PROVEN PROVIDER COMMIT CONTRACT |
| Exact-session absence / ambiguous-COMMIT recovery | Warehouse recovery + approved fault runner | IMPLEMENTED + CI PROVEN CONTRACT |

No row above is a live Fabric claim until retained exact-candidate execution evidence exists.

## Approved integration evidence

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Evidence spec/result/manifest/hash | `evidence/integration_evidence.py` | IMPLEMENTED + CI PROVEN; framework/domain identity split |
| Approved-run preflight | `evidence/integration_runner.py` | IMPLEMENTED + CI PROVEN |
| Strict staged evidence merge | `evidence/integration_evidence_merge.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Explicit Pipeline rerun projection | `evidence/integration_evidence_rerun.py` | IMPLEMENTED + CI PROVEN |
| Approved Pipeline / Copy / Spark / Warehouse runners | `evidence/approved_*_runner.py` | IMPLEMENTED + CI PROVEN RUNNER CONTRACTS |
| Retained text secret scanning | `evidence/safety.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Exact candidate integration-evidence producer | `.github/workflows/candidate-integration-evidence.yml` | MERGED; no live selected-candidate run |

Exact integration identity split:

```text
IntegrationEvidence.release_hash
  = exact framework candidate wheel SHA256

IntegrationEvidence.domain_release_hash
  = exact customer/domain ReleaseManifest.bundle.release_hash
```

These hashes must never be assumed equal.

## Release readiness / exact candidate

| Capability | Implementation owner | Current evidence |
|---|---|---|
| 0.4 source-controlled readiness matrix | `release/0.4.0/readiness-spec.json` | CONTRACT + CI PROVEN |
| Exact candidate source/wheel readiness binding | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Exact customer/domain readiness binding | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN |
| Generic proof cannot bypass integration-backed gate | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Strict partial release-proof merge | `evidence/release_readiness_merge.py` | IMPLEMENTED + CI PROVEN |
| `release-readiness` / `release-proofs-merge` | `cli/release.py` | PRESENTATION + CI PROVEN |
| Exact candidate wheel manifest | `deployment/candidate_artifact.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Main CI wheel + SHA256SUMS + CANDIDATE.json | `.github/workflows/ci.yml` | IMPLEMENTED + CI PROVEN |
| Candidate certification aggregation | `evidence/candidate_certification.py` + workflow | IMPLEMENTED + CI PROVEN |
| Exact certified wheel promotion without rebuild | `.github/workflows/release.yml` | IMPLEMENTED + CI PROVEN |

Ordinary CI remains intentionally `release_ready=false` with 15 required blockers. PR #107 CI success does not select/freeze/release 0.4.

## Current candidate-capable executable artifact

```text
source SHA       4c8ad9994f3800e901c146b919f85454d78f080e
main CI          33968014547
wheel SHA256     06d4a9ca948693c87a658a34e8c4fccb42439a7f9f67c44985ac726dedb4e04d
artifact ID      9970044954
archive digest   sha256:7c297a36eb3146356f2ba7a39e87e9fee3f2ea53bc9a9711cbebe9031ec00a97
selected/frozen  false
real Fabric run  none for these bytes
```

This is candidate-capable only. It is not a selected/frozen candidate and carries no real-Fabric PASS yet.

## Real proof / release work still missing

| Proof / capability | State |
|---|---|
| Frozen exact 0.4 candidate | NOT YET |
| Selected-candidate customer input artifact | NOT YET RETAINED |
| Candidate integration evidence | NO SELECTED-CANDIDATE LIVE RUN |
| Candidate business-path evidence | NO SELECTED-CANDIDATE LIVE RUN |
| Complete release proof | NOT YET RETAINED |
| Enterprise Fabric identity/workspace authorization | NOT YET RETAINED |
| Production control-plane certification | NOT YET RETAINED |
| Live approved Pipeline/Copy/Spark for current bytes | NOT YET RETAINED |
| Live Warehouse ambiguous-COMMIT proof for current bytes | NOT YET RETAINED |
| Release-readiness blockers = 0 | NOT YET; ordinary CI has 15 blockers |
| Capacity/IAM/network/DR/monitoring/governance | EXTERNAL / NOT YET RETAINED |

## Historical release truth

```text
v0.3.0 immutable release = RELEASE PROVEN for v0.3.0
0.4.0 source             = UNRELEASED / FEATURE FROZEN / READINESS BLOCKED
release_allowed          = false
candidate_status          = not_frozen
```

`docs/machine/STATE.md` owns the exact current executable checkpoint. A later docs/test-only Git SHA does not replace PR #107 as executable identity; the exact PR #107 wheel remains the next real-Fabric artifact unless `src/` changes.
