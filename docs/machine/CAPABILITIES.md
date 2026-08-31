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
| Evidence spec/result/manifest/hash | `evidence/integration_evidence.py` | IMPLEMENTED + CI PROVEN on merged baseline; identity split currently CI PENDING |
| Approved-run preflight | `evidence/integration_runner.py` | IMPLEMENTED + CI PROVEN on merged baseline; dual identity currently CI PENDING |
| Strict staged evidence merge | `evidence/integration_evidence_merge.py` | IMPLEMENTED + CI PROVEN; domain-hash propagation currently CI PENDING |
| Read-only Fabric item smoke | integration runner/checks | IMPLEMENTED + CI PROVEN RUNNER CONTRACT |
| Control-plane certification runner | `evidence/approved_control_plane_runner.py` | IMPLEMENTED + CI PROVEN RUNNER CONTRACT |
| Pipeline runner | `evidence/approved_pipeline_runner.py` | IMPLEMENTED + CI PROVEN RUNNER CONTRACT; provider/framework retained report currently CI PENDING |
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
| Strict partial release-proof merge | `evidence/release_readiness_merge.py` | IMPLEMENTED + CI PROVEN fail-closed |
| `release-readiness` / `release-proofs-merge` | `cli/release.py` | PRESENTATION + CI PROVEN |
| Exact candidate wheel manifest | `deployment/candidate_artifact.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Main CI wheel + SHA256SUMS + CANDIDATE.json | `.github/workflows/ci.yml` | IMPLEMENTED + CI PROVEN |
| Exact certified wheel promotion without rebuild | `.github/workflows/release.yml` | IMPLEMENTED + CI PROVEN RELEASE CONTRACT |
| Candidate certification aggregation | `.github/workflows/candidate-certification.yml` | IMPLEMENTED + CI PROVEN WORKFLOW CONTRACT |
| Candidate non-integration release-proof producer | `.github/workflows/candidate-release-proofs.yml` | **MERGED + MAIN CI PROVEN PR #87** |

Latest merged baseline:

```text
PR               #87
merge SHA         5a2edffe5930e9b8a2a79f66f4580ca4d9df2b4e
PR CI             33343182775
main CI           33343223496
tests             670
wheel SHA256      e6c0cda41ebdb3c356c087a79a3e6b0fe8b353867b8c06c0e89d4381fb23db35
candidate artifact 9741187950
selected/frozen   false
```

`candidate-release-proofs.yml` directly proves only `source.tests`, `wheel.integrity`, and `customer.compatibility`; it requires a separate retained business-path artifact for the five live gates and refuses final output unless all eight required non-integration gates PASS.

## Representative live business-path evidence — current feature branch

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Five-gate semantic evidence evaluator | `evidence/business_path_evidence.py` | IMPLEMENTED / CI PENDING |
| Framework-owned Pipeline provider + durable outcome report | `evidence/approved_pipeline_runner.py` | IMPLEMENTED / CI PENDING delta |
| Mutating fixture/fault driver contract with no PASS field | `evidence/business_path_driver.py` | IMPLEMENTED / CI PENDING |
| Exact five-gate source-controlled plan | `evidence/business_path_plan.py` | IMPLEMENTED / CI PENDING |
| Explicit rerun projection from certified integration evidence | `evidence/integration_evidence_rerun.py` | IMPLEMENTED / CI PENDING |
| Approved business-path runner | `evidence/approved_business_path_runner.py` | IMPLEMENTED / CI PENDING |
| `candidate-business-path-run` CLI | `cli/business_path.py` | PRESENTATION / CI PENDING |
| Candidate business-path producer workflow | `.github/workflows/candidate-business-path-evidence.yml` | IMPLEMENTED / CI PENDING |
| Customer business-path input producer | `fabric-customer/.github/workflows/candidate-business-path-inputs.yml` | NOT YET IMPLEMENTED |
| Candidate integration-evidence producer | `.github/workflows/candidate-integration-evidence.yml` | NOT YET IMPLEMENTED |

The branch does not contain live PASS evidence. Its workflow intentionally cannot succeed until trusted integration evidence and exact customer certification inputs exist.

## Exact integration identity split — current feature branch

A release blocker was found while connecting real workflow inputs: framework binary identity and customer/domain release identity had been conflated under one hash name. The branch now defines:

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

Candidate mode must match both independently. Legacy/reference runner configs remain compatible only when the new domain identity is absent. This identity split is **IMPLEMENTED / CI PENDING** until the current branch passes PR/main CI.

## Business-path false-positive guards

Current branch contracts reject:

```text
provider Completed alone
observer/driver authored PASS
in-memory apply as live proof
failed retry that changed target/progress
retry with different execution-plan hash
reconciliation proof where provider itself failed
reconciliation failure that advanced target/progress
missing exact plan/scenario/driver/plugin fingerprints
missing explicit mutation authorization
cleanup failure after a computed PASS
framework/domain hash identity mismatch
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

The last two are current feature-branch surfaces and remain CI pending.

## Real proof / release work still missing

| Proof / capability | State |
|---|---|
| Frozen exact 0.4 candidate | NOT YET |
| Candidate business-path harness/workflow | FEATURE BRANCH IMPLEMENTED / CI PENDING |
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
