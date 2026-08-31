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
| Immutable DatasetConfig / effective config hashing | `metadata/config.py` | REFERENCE + CI PROVEN |
| Capture/Bronze semantic presets | `capture/semantic_contracts.py` | REFERENCE + CI PROVEN |
| FULL/WATERMARK/CDC and SCD1/SCD2 orthogonality | metadata/capture/apply | REFERENCE MODEL + CI PROVEN |
| APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF | `apply/` | REFERENCE + CI PROVEN |
| Provider-neutral CDC order/dedupe/checkpoint | capture/data-plane CDC modules | REFERENCE + CI PROVEN |
| Debezium/Kafka and Delta CDF recovery contracts | CDC adapters | ADAPTER/RECOVERY CONTRACT + CI PROVEN |
| Typed CaptureReceipt / progress authority | contracts/capabilities | REFERENCE + CI PROVEN |

Semantic support is not live provider certification. Capture fidelity still upper-bounds truthful downstream history fidelity.

## Customer/domain project contract

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Non-destructive project scaffold | `deployment/project.py` | REFERENCE + CI PROVEN |
| `project-init` / `project-validate` | CLI + deployment project | PRESENTATION/REFERENCE + CI PROVEN |
| Dependency/cycle/capability validation | `deployment/project.py` | REFERENCE + CI PROVEN fail-closed |
| Exact semantic-selection coverage / overclaim guard | deployment + capture onboarding | REFERENCE + CI PROVEN fail-closed |
| Mixed FULL/WATERMARK/CDC + SCD1/SCD2 in one domain repo | DatasetConfig + project contract | REFERENCE MODEL + CI PROVEN |

Project validation is static/local. It does not create Fabric resources or become live evidence.

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
| Exact candidate integration-evidence producer | `.github/workflows/candidate-integration-evidence.yml` | MERGED + MAIN CI PROVEN PR #90; no live run |

PR #90 regression provenance:

```text
merge SHA      7e12a320e73aa06f3e80f57e3deed14a6cc7add0
final PR CI    33349005817
main CI        33349064335
tests          728
```

Exact integration identity split:

```text
IntegrationEvidence.release_hash
  = exact framework candidate wheel SHA256

IntegrationEvidence.domain_release_hash
  = exact customer/domain ReleaseManifest.bundle.release_hash

ApprovedIntegrationRunnerConfig.framework_artifact_sha256
  = exact framework candidate wheel SHA256

ApprovedIntegrationRunnerConfig.release_hash
  = exact customer/domain release hash
```

These hashes must never be assumed equal.

## Release readiness / exact candidate

| Capability | Implementation owner | Current evidence |
|---|---|---|
| 0.4 source-controlled readiness matrix | `release/0.4.0/readiness-spec.json` | CONTRACT + CI PROVEN |
| Exact candidate source/wheel readiness binding | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Exact customer/domain readiness binding | `evidence/release_readiness.py` | MERGED + MAIN CI PROVEN PR #92 |
| Generic proof cannot bypass integration-backed gate | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Strict partial release-proof merge | `evidence/release_readiness_merge.py` | MERGED PR #86; exact domain identity extension MAIN CI PROVEN PR #92 |
| `release-readiness` / `release-proofs-merge` | `cli/release.py` | PRESENTATION + CI PROVEN |
| Exact candidate wheel manifest | `deployment/candidate_artifact.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Main CI wheel + SHA256SUMS + CANDIDATE.json | `.github/workflows/ci.yml` | IMPLEMENTED + CI PROVEN |
| Candidate certification aggregation | `evidence/candidate_certification.py` + workflow | MERGED + MAIN CI PROVEN PR #92 domain identity hardening |
| Exact certified wheel promotion without rebuild | `.github/workflows/release.yml` | MERGED + MAIN CI PROVEN PR #92 pre-tag domain identity re-check |
| Candidate non-integration release-proof producer | `.github/workflows/candidate-release-proofs.yml` | MERGED baseline PR #87; domain hardening MAIN CI PROVEN PR #92 |
| Candidate representative business-path producer | `.github/workflows/candidate-business-path-evidence.yml` | MERGED + MAIN CI PROVEN PR #88; no live run |
| Candidate integration-evidence producer | `.github/workflows/candidate-integration-evidence.yml` | MERGED + MAIN CI PROVEN PR #90; no live run |

Regression context:

```text
strict proof merge PR #86:
  merge SHA 0f70e037806482c677fccae0ce9432504f2a9885
  main CI   33342806854

candidate release-proof PR #87:
  merge SHA 5a2edffe5930e9b8a2a79f66f4580ca4d9df2b4e
  main CI   33343223496

exact domain binding PR #92:
  merge SHA d5eed17f2ec2f869b4e3a448597e6d8d600568ea
  final PR CI 33356959856
  main CI     33357032461
  tests       734
```

Ordinary CI remains intentionally `release_ready=false` with 15 required blockers.

## Representative live business-path evidence

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Five-gate semantic evidence evaluator | `evidence/business_path_evidence.py` | IMPLEMENTED + CI PROVEN PR #88 |
| Mutating fixture/fault driver with no PASS field | `evidence/business_path_driver.py` | IMPLEMENTED + CI PROVEN PR #88 |
| Exact five-gate source-controlled plan | `evidence/business_path_plan.py` | IMPLEMENTED + CI PROVEN |
| Approved business-path runner | `evidence/approved_business_path_runner.py` | IMPLEMENTED + CI PROVEN PR #88 |
| Exact domain-bound business-path proof packaging | `evidence/business_path_release_proof.py` | MERGED + MAIN CI PROVEN PR #92 |
| `candidate-business-path-run` CLI | `cli/business_path.py` | PRESENTATION + CI PROVEN |
| Candidate business-path producer workflow | `.github/workflows/candidate-business-path-evidence.yml` | MERGED + MAIN CI PROVEN PR #88; no live run |
| Customer business-path/integration input producer | `fabric-customer/.github/workflows/candidate-business-path-inputs.yml` | MERGED + CUSTOMER MAIN CI PROVEN PR #10/#11; no selected-candidate artifact retained |

PR #88 regression context:

```text
source SHA 1632aefe8c1fd71098200c434a1648d0385f4967
main CI    33346470401
```

Customer input contract context:

```text
PR #10 merge                 cda90f1c02fc9606aa64d2d1bd13f2ab89628aab
PR #11 checkpoint            31f3f506bc1c16a445652de2ad48fe512cfec10a
customer main CI             33353960915
customer certification CI    33353960906
production runtime pin       fabric-data-framework==0.3.0
```

The framework contains no retained live business-path PASS evidence.

## Exact domain-release identity chain — PR #92

Candidate evidence uses independent framework and domain machine identities all the way to promotion:

```text
framework identity:
  candidate_git_sha
  artifact_sha256 / IntegrationEvidence.release_hash

domain identity:
  ReleaseManifest.bundle.release_hash
  ReleaseReadinessProofBundle.domain_release_hash
  ReleaseReadinessReport.domain_release_hash
  IntegrationEvidence.domain_release_hash
```

`candidate-release-proofs` cannot accept domain identity directly from workflow input. It authenticates `customer-release-manifest.json` retained by the business-path producer, then creates static proof with that same hash. Candidate certification rejects mismatch, and release promotion re-checks report/proofs/integration equality before tag creation.

Latest candidate-capable main wheel after PR #92:

```text
source SHA       d5eed17f2ec2f869b4e3a448597e6d8d600568ea
main CI          33357032461
wheel SHA256     5aa82d6befa3d5abe5d212d875721e6ae9e3e4bc4d67fd5b4cdd1a32d9e16701
artifact ID      9745451533
selected/frozen  false
```

## Real proof / release work still missing

| Proof / capability | State |
|---|---|
| Frozen exact 0.4 candidate | NOT YET |
| Selected-candidate customer input artifact | NOT YET RETAINED |
| Candidate integration evidence | workflow merged; NO LIVE RUN / artifact |
| Candidate business-path evidence | workflow merged; NO LIVE RUN / artifact |
| Complete release proof | NOT YET RETAINED |
| `release-readiness-certified-<candidate SHA>` | NOT YET PRODUCED |
| Enterprise Fabric identity/workspace authorization | NOT YET RETAINED |
| Production control-plane certification | NOT YET RETAINED |
| Live approved Pipeline/Copy/Spark | NOT YET RETAINED |
| Live Warehouse marker/ambiguous-COMMIT proof | NOT YET RETAINED |
| Release-readiness blockers = 0 | NOT YET; ordinary CI has 15 blockers |
| Debezium/Kafka live certification | OUT OF REQUIRED 0.4 SCOPE unless promoted |
| Capacity/IAM/network/DR/monitoring/governance | EXTERNAL / NOT YET RETAINED |

## Historical release truth

```text
v0.3.0 immutable release = RELEASE PROVEN for v0.3.0
0.4.0 source             = UNRELEASED / FEATURE FROZEN / READINESS BLOCKED
release_allowed          = false
```
