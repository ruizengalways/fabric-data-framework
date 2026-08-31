# MACHINE CAPABILITY MATRIX

Evidence vocabulary:

```text
REFERENCE / CONTRACT       deterministic semantic/runtime implementation
CI PROVEN                  tests/build succeeded on merged baseline
RELEASE PROVEN             immutable published artifact/checksum evidence
FABRIC/PRODUCTION PROVEN   retained approved real-service evidence for exact release
EXTERNAL                   enterprise/platform control outside this repository
```

## Semantic / runtime guarantees

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Immutable DatasetConfig / effective config hashing | `metadata/config.py` | REFERENCE + CI PROVEN |
| Exact 14 capture/Bronze semantic presets | `capture/semantic_contracts.py` | REFERENCE + CI PROVEN |
| Semantic onboarding overclaim guardrails | `capture/onboarding.py` | REFERENCE + CI PROVEN |
| FULL/WATERMARK/CDC and SCD1/SCD2 orthogonality | metadata/capture/apply | REFERENCE + CI PROVEN |
| APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF | `apply/` | REFERENCE + CI PROVEN |
| Provider-neutral CDC order/dedupe/checkpoint | capture/data-plane CDC modules | REFERENCE + CI PROVEN |
| Debezium/Kafka normalization/recovery | CDC adapter | ADAPTER/RECOVERY CONTRACT + CI PROVEN |
| Delta CDF bounded recovery | Delta adapter | ADAPTER/RECOVERY CONTRACT + CI PROVEN |
| Typed CaptureReceipt / progress authority | contracts/capabilities | REFERENCE + CI PROVEN |

Semantic or adapter support is not live provider certification. Capture fidelity still upper-bounds truthful downstream history fidelity.

## Customer/domain project contract

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Non-destructive project scaffold | `deployment/project.py` | REFERENCE + CI PROVEN |
| `project-init` | `cli/project.py` | PRESENTATION + CI PROVEN |
| Whole-project static validation | `deployment/project.py` | REFERENCE + CI PROVEN |
| `project-validate` | `cli/project.py` | PRESENTATION + CI PROVEN |
| Dependency/cycle/capability validation | `deployment/project.py` | REFERENCE + CI PROVEN fail-closed |
| Exact semantic-selection coverage / overclaim guard | deployment + capture onboarding | REFERENCE + CI PROVEN fail-closed |
| Mixed FULL/WATERMARK/CDC + SCD1/SCD2 in one domain repo | DatasetConfig + project contract | REFERENCE MODEL + CI PROVEN |

Project validation is static/local. It does not create Fabric resources, validate workspace authorization, execute providers, or upgrade a project PASS to live evidence.

## Fabric/provider execution

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Fabric Data Pipeline backend | execution backend | IMPLEMENTED + CI PROVEN BACKEND |
| Copy Job REST transport | Fabric Copy adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Spark Job Definition REST transport | Fabric Spark adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Provider Completed insufficient for semantic success | Pipeline/capture adapters | REFERENCE + CI PROVEN |
| Fabric Warehouse same-transaction target marker | Warehouse recovery | IMPLEMENTED + CI PROVEN PROVIDER COMMIT CONTRACT |

No row above is a live Fabric claim until retained exact-candidate execution evidence exists.

## Control plane / recovery

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Durable target-operation CAS journal | control-plane/target-operation modules | IMPLEMENTED + CI PROVEN REFERENCE |
| UNKNOWN tri-state recovery | recovery modules | IMPLEMENTED + CI PROVEN REFERENCE |
| SQLAlchemy relational runtime repository | `control_plane/sqlalchemy_repository.py` | IMPLEMENTED + CI PROVEN |
| Control-plane backend certification contract | certification modules | IMPLEMENTED + CI PROVEN CONTRACT |
| Exact Warehouse session absence contract | `recovery/fabric_warehouse_session_absence.py` | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Separate Admin authorization for session termination | approved Warehouse fault runner | IMPLEMENTED + CI PROVEN GUARDRAIL |

## Approved integration evidence surfaces

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Evidence spec/result/manifest/hash | `evidence/integration_evidence.py` | IMPLEMENTED + CI PROVEN; framework/domain identity split merged in PR #88 |
| Approved-run preflight | `evidence/integration_runner.py` | IMPLEMENTED + CI PROVEN; dual exact-release identity merged in PR #88 |
| Strict staged evidence merge | `evidence/integration_evidence_merge.py` | IMPLEMENTED + CI PROVEN; domain hash propagated fail-closed |
| Explicit Pipeline rerun projection | `evidence/integration_evidence_rerun.py` | IMPLEMENTED + CI PROVEN; source must already be fully certified |
| Read-only Fabric item smoke | integration runner/checks | IMPLEMENTED + CI PROVEN RUNNER CONTRACT |
| Control-plane certification runner | `evidence/approved_control_plane_runner.py` | IMPLEMENTED + CI PROVEN RUNNER CONTRACT |
| Pipeline runner | `evidence/approved_pipeline_runner.py` | IMPLEMENTED + CI PROVEN; provider/native status retained separately from durable framework outcome |
| Copy/Spark runner | `evidence/approved_capture_runner.py` | IMPLEMENTED + CI PROVEN RUNNER CONTRACT |
| Warehouse commit runner | `evidence/approved_warehouse_runner.py` | IMPLEMENTED + CI PROVEN RUNNER CONTRACT |
| Real ambiguous-COMMIT runner contract | `evidence/approved_warehouse_fault_runner.py` | IMPLEMENTED + CI PROVEN RUNNER CONTRACT |
| Retained text secret scanning | `evidence/safety.py` | IMPLEMENTED + CI PROVEN fail-closed |

No retained exact-0.4 real-service run currently upgrades these to FABRIC/PRODUCTION PROVEN.

## Release readiness / exact candidate

| Capability | Implementation owner | Current evidence |
|---|---|---|
| 0.4 source-controlled readiness matrix | `release/0.4.0/readiness-spec.json` | CONTRACT + CI PROVEN |
| Exact candidate source/wheel binding | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Generic proof cannot bypass integration-backed gate | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Strict partial release-proof merge | `evidence/release_readiness_merge.py` | IMPLEMENTED + CI PROVEN fail-closed; merged PR #86 |
| `release-readiness` / `release-proofs-merge` | `cli/release.py` | PRESENTATION + CI PROVEN |
| Exact candidate wheel manifest | `deployment/candidate_artifact.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Main CI wheel + SHA256SUMS + CANDIDATE.json | `.github/workflows/ci.yml` | IMPLEMENTED + CI PROVEN |
| Exact certified wheel promotion without rebuild | `.github/workflows/release.yml` | IMPLEMENTED + CI PROVEN RELEASE CONTRACT |
| Candidate certification aggregation | `.github/workflows/candidate-certification.yml` | IMPLEMENTED + CI PROVEN WORKFLOW CONTRACT |
| Candidate non-integration release-proof producer | `.github/workflows/candidate-release-proofs.yml` | MERGED + MAIN CI PROVEN PR #87 |
| Candidate representative business-path producer | `.github/workflows/candidate-business-path-evidence.yml` | MERGED + MAIN CI PROVEN PR #88 workflow contract |

Latest merged baseline:

```text
PR                #88
merge SHA          1632aefe8c1fd71098200c434a1648d0385f4967
PR CI              33346419772
main CI            33346470401
tests              717
wheel SHA256       9c813a2c23344c55409ac5f4f7e879d4515196987835bee6473d54ff3a1e027f
candidate artifact 9742145456
selected/frozen    false
```

The main artifact is candidate-capable only. It is not frozen, certified, or release-proven.

`candidate-release-proofs.yml` directly proves only `source.tests`, `wheel.integrity`, and `customer.compatibility`; it requires a separate retained business-path artifact for the five live gates and refuses final output unless all eight required non-integration gates PASS.

## Representative live business-path evidence

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Five-gate semantic evidence evaluator | `evidence/business_path_evidence.py` | IMPLEMENTED + CI PROVEN PR #88 |
| Framework-owned Pipeline provider + durable outcome report | `evidence/approved_pipeline_runner.py` | IMPLEMENTED + CI PROVEN PR #88 delta |
| Mutating fixture/fault driver contract with no PASS field | `evidence/business_path_driver.py` | IMPLEMENTED + CI PROVEN PR #88 |
| Exact five-gate source-controlled plan | `evidence/business_path_plan.py` | IMPLEMENTED + CI PROVEN; unsafe/noncanonical paths fail closed |
| Explicit rerun projection from certified integration evidence | `evidence/integration_evidence_rerun.py` | IMPLEMENTED + CI PROVEN PR #88 |
| Approved business-path runner | `evidence/approved_business_path_runner.py` | IMPLEMENTED + CI PROVEN PR #88 |
| `candidate-business-path-run` CLI | `cli/business_path.py` | PRESENTATION + CI PROVEN PR #88 |
| Candidate business-path producer workflow | `.github/workflows/candidate-business-path-evidence.yml` | IMPLEMENTED + CI PROVEN WORKFLOW CONTRACT PR #88 |
| Customer business-path input producer | `fabric-customer/.github/workflows/candidate-business-path-inputs.yml` | NOT YET IMPLEMENTED |
| Candidate integration-evidence producer | `.github/workflows/candidate-integration-evidence.yml` | NOT YET IMPLEMENTED |

The merged framework contains no live PASS evidence. The business-path workflow intentionally cannot succeed until trusted exact-candidate integration evidence and exact customer certification inputs exist.

## Exact integration identity split

PR #88 permanently separates framework binary identity from customer/domain release identity:

```text
IntegrationEvidence.release_hash
  = exact framework candidate wheel SHA256

IntegrationEvidence.domain_release_hash
  = exact customer/domain ReleaseManifest.bundle.release_hash

ApprovedIntegrationRunnerConfig.framework_artifact_sha256
  = exact framework candidate wheel SHA256 in candidate mode

ApprovedIntegrationRunnerConfig.release_hash
  = exact customer/domain ReleaseManifest.bundle.release_hash
```

Candidate mode must match both independently. These hashes are not interchangeable. Legacy/reference runner configs remain compatible only when `domain_release_hash` is absent.

## Business-path false-positive guards

Merged contracts reject:

```text
provider Completed alone
observer/driver authored PASS
in-memory apply as live proof
failed retry that changed target/progress
retry with different execution-plan hash
reconciliation proof where provider itself failed
reconciliation failure that advanced target/progress
missing exact plan/scenario/driver/plugin fingerprints
unsafe or noncanonical plan paths
missing explicit Pipeline or scenario mutation authorization
cleanup failure after a computed PASS
framework/domain hash identity mismatch
uncertified source integration evidence for explicit Pipeline rerun
```

See `docs/machine/BUSINESS_PATH_EVIDENCE.md` for the exact evidence contract.

## Extension surfaces

| Extension kind | Entry-point group | Boundary |
|---|---|---|
| Capture observer | `fabric_data_framework.capture_observers` | bounded provider observation; cannot decide framework PASS |
| Spark execution data | `fabric_data_framework.spark_execution_data` | bounded execution data |
| Warehouse mutation | `fabric_data_framework.warehouse_mutations` | cannot commit/write framework marker/journal |
| Warehouse commit fault injector | `fabric_data_framework.warehouse_commit_fault_injectors` | cannot manufacture commit truth |
| Business-path observer | `fabric_data_framework.business_path_observers` | read-only semantic state facts; no PASS/status |
| Business-path driver | `fabric_data_framework.business_path_drivers` | bounded fixture/fault mutation + receipt; no PASS/status |

All extension surfaces above are portable contracts. None is automatically live provider proof.

## Real proof / release work still missing

| Proof / capability | State |
|---|---|
| Frozen exact 0.4 candidate | NOT YET |
| Candidate business-path harness/workflow | MERGED + MAIN CI PROVEN; no live retained run |
| Candidate integration-evidence workflow | NOT YET IMPLEMENTED |
| Customer business-path input workflow/artifacts | NOT YET IMPLEMENTED / NOT RETAINED |
| `release-readiness-certified-<candidate SHA>` | NOT YET PRODUCED |
| Enterprise Fabric identity/workspace authorization | NOT YET RETAINED |
| Production control-plane certification | NOT YET RETAINED |
| Live approved Pipeline/Copy/Spark | NOT YET RETAINED |
| Live FULL/REPLACE, WATERMARK/SCD1, WATERMARK/SCD2 | NOT YET RETAINED |
| Live retry/idempotency and reconciliation fail-closed drills | NOT YET RETAINED |
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
