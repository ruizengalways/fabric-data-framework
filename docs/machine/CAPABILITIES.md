# MACHINE CAPABILITY MATRIX

Evidence vocabulary:

```text
REFERENCE / CONTRACT       deterministic semantic/runtime implementation
CI PROVEN                  static/tests/build succeeded on merged baseline
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
| Full baseline -> WATERMARK fenced bootstrap | capture bootstrap modules | REFERENCE + CI PROVEN |
| Snapshot -> CDC fenced bootstrap | capture bootstrap modules | REFERENCE + CI PROVEN |
| APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF | `apply/` | REFERENCE + CI PROVEN |
| Provider-neutral CDC order/dedupe/checkpoint | CDC modules | REFERENCE + CI PROVEN |
| Debezium/Kafka normalization/recovery | CDC adapter | ADAPTER/RECOVERY CONTRACT + CI PROVEN |
| Delta CDF bounded recovery | Delta adapter | ADAPTER/RECOVERY CONTRACT + CI PROVEN |
| Replay-stable file/API guardrails | capture modules | REFERENCE + CI PROVEN |
| Typed CaptureReceipt / progress authority | contracts/capabilities | REFERENCE + CI PROVEN |

Boundary: semantic representation or adapter support is not automatically live provider certification. Capture fidelity still upper-bounds truthful downstream history fidelity.

## Developer / customer project bootstrap and dry run

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Non-destructive customer/domain repo scaffold | `deployment/project.py` | REFERENCE + CI PROVEN |
| `project-init` CLI adapter | `cli/project.py` | PRESENTATION + CI PROVEN |
| Existing-file no-overwrite / manifest domain-match guards | `deployment/project.py` | REFERENCE + CI PROVEN fail-closed |
| Mixed FULL/WATERMARK/CDC + SCD1/SCD2 in one domain repo | DatasetConfig + scaffold/runbook | REFERENCE MODEL + CI PROVEN scaffold |
| Whole-project static dry run | `deployment/project.py` | REFERENCE + CI PROVEN |
| `project-validate` CLI adapter | `cli/project.py` | PRESENTATION + CI PROVEN |
| Dependency reference + cycle validation | `deployment/project.py` | REFERENCE + CI PROVEN fail-closed |
| Capture/apply capability validation | `deployment/project.py` + `metadata/capabilities.py` | REFERENCE + CI PROVEN |
| Exact semantic-selection coverage / unknown-selection rejection | `deployment/project.py` + `capture/onboarding.py` | REFERENCE + CI PROVEN fail-closed |
| Per-dataset semantic overclaim validation | `capture/onboarding.py` via `deployment/project.py` | REFERENCE + CI PROVEN |
| Deterministic workload summary and JSON report | `deployment/project.py` + `cli/project.py` | DEVELOPER/CI ARTIFACT + CI PROVEN |

Boundary: project validation is source-controlled/static. It does not create Fabric resources, persist secrets, validate workspace authorization, execute providers, or upgrade a project PASS to live evidence.

## Fabric/provider execution

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Fabric Data Pipeline backend | Pipeline backend | IMPLEMENTED + CI PROVEN BACKEND |
| Copy Job REST transport | Fabric Copy adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Spark Job Definition REST transport | Fabric Spark adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Provider Completed insufficient for semantic success | Pipeline/capture adapters | REFERENCE + CI PROVEN |
| Fabric Warehouse same-transaction target marker | Warehouse recovery | IMPLEMENTED + CI PROVEN PROVIDER COMMIT CONTRACT |

No row above is a live Fabric claim until retained approved exact-candidate execution exists.

## Control plane / target recovery

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Durable target-operation CAS journal | target-operation/control-plane modules | IMPLEMENTED + CI PROVEN REFERENCE |
| UNKNOWN tri-state recovery | recovery modules | IMPLEMENTED + CI PROVEN REFERENCE |
| SQLAlchemy relational runtime repository | `control_plane/sqlalchemy_repository.py` | IMPLEMENTED + CI PROVEN RELATIONAL RUNTIME |
| Control-plane backend conformance certification contract | certification modules | IMPLEMENTED + CI PROVEN CONTRACT |
| Runtime does not silently migrate production schema | repository/runtime boundary | REFERENCE + CI PROVEN GUARDRAIL |
| Exact Warehouse session absence certification contract | `recovery/fabric_warehouse_session_absence.py` | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Separate Admin authorization for session termination | approved Warehouse fault/recovery runner | IMPLEMENTED + CI PROVEN GUARDRAIL |

## Approved evidence surfaces

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Evidence spec/manifest/hash | `evidence/integration_evidence.py` | IMPLEMENTED + CI PROVEN EVIDENCE HARNESS CONTRACT |
| Credential-safe approved-run preflight | `evidence/integration_runner.py` | IMPLEMENTED + CI PROVEN APPROVED-RUN PREFLIGHT CONTRACT |
| Read-only Fabric item smoke | integration runner/checks | IMPLEMENTED + CI PROVEN READ-ONLY RUNNER CONTRACT |
| Strict staged evidence merge | `evidence/integration_evidence_merge.py` | IMPLEMENTED + CI PROVEN EVIDENCE MERGE CONTRACT |
| Retained evidence secret scanning | `evidence/safety.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Approved control-plane certification | `evidence/approved_control_plane_runner.py` | IMPLEMENTED + CI PROVEN APPROVED RUNNER CONTRACT |
| Approved Pipeline execution evidence | `evidence/approved_pipeline_runner.py` | IMPLEMENTED + CI PROVEN APPROVED RUNNER CONTRACT |
| Approved Copy/Spark capture evidence | `evidence/approved_capture_runner.py` | IMPLEMENTED + CI PROVEN APPROVED RUNNER CONTRACT |
| Approved Warehouse commit/recovery | `evidence/approved_warehouse_runner.py` | IMPLEMENTED + CI PROVEN APPROVED RUNNER CONTRACT |
| Approved real ambiguous-COMMIT drill | `evidence/approved_warehouse_fault_runner.py` | IMPLEMENTED + CI PROVEN APPROVED RUNNER CONTRACT |

The runners above are evidence-producing contracts, but this repository still has no retained exact-0.4 live run that upgrades them to FABRIC/PRODUCTION PROVEN.

## Release readiness / exact candidate identity

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Source-controlled 0.4 readiness matrix | `release/0.4.0/readiness-spec.json` | CONTRACT + CI PROVEN |
| Exact candidate source-SHA binding | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Exact artifact-SHA binding for live IntegrationEvidenceManifest | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Generic proof cannot bypass integration-backed gate | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Required `NOT_RUN` / `FAIL` / `OUT_OF_SCOPE` blocks release | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| `release_ready=true` iff all required gates PASS | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN |
| `release-readiness` / `--require-ready` CLI | `cli/release.py` | PRESENTATION + CI PROVEN |
| CI-retained intentionally blocked readiness report | `.github/workflows/ci.yml` | CI PROVEN; ordinary main has 15 blockers |
| Candidate wheel manifest binds source/run/attempt/inner SHA256 | `deployment/candidate_artifact.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Candidate manifest rejects wheel-byte/version/provenance mismatch | `deployment/candidate_artifact.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Main candidate artifact = wheel + SHA256SUMS + CANDIDATE.json | `.github/workflows/ci.yml` | IMPLEMENTED + CI PROVEN WORKFLOW CONTRACT |
| Main candidate artifact longer retention than PR artifact | `.github/workflows/ci.yml` | IMPLEMENTED + CI PROVEN WORKFLOW POLICY |
| Exact certified wheel promotion without rebuild | `.github/workflows/release.yml` | IMPLEMENTED + CI PROVEN RELEASE CONTRACT |
| Release requires certified readiness bound to exact wheel | `.github/workflows/release.yml` | IMPLEMENTED + CI PROVEN fail-closed RELEASE CONTRACT |

Latest verified candidate-capable main artifact from merged PR #84 run `33314977393`:

```text
source SHA       bb9b7ed74e2696978c546011c893fb316ffdd57c
wheel            fabric_data_framework-0.4.0-py3-none-any.whl
inner SHA256     ce78ae1bc67b0e68bca360e825d36cf6b0cb171f811de8257cd9ce0225154748
artifact ID      9733146071
archive digest   sha256:6a4d45618e64f7bf34b508652ee999b95e37a0f23cdf07927807e593bfabdde4
retention        90 days / expires 2026-11-28T13:44:16Z
selected/frozen  false
```

That artifact remains candidate-capable only. It has not been selected/frozen and has no live certification attached.

## Candidate certification aggregation — merged PR #84

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Source-controlled 0.4 integration evidence template | `release/0.4.0/integration-evidence-template.json` | CONTRACT + CI PROVEN |
| Runtime binding of template to environment/domain/exact wheel SHA | `evidence/candidate_certification.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Integration manifest must be fully certified before candidate certification | `evidence/candidate_certification.py` + `evidence/integration_evidence.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Release proof references/details reject credential-like retained text | `evidence/candidate_certification.py` + `evidence/safety.py` | IMPLEMENTED + CI PROVEN fail-closed |
| `candidate-certify` hard certification CLI | `cli/release.py` | PRESENTATION + CI PROVEN |
| Candidate CI provenance and exact wheel re-verification | `.github/workflows/candidate-certification.yml` | IMPLEMENTED + CI PROVEN WORKFLOW CONTRACT |
| Evidence run must be successful explicit workflow_dispatch at exact candidate SHA | `.github/workflows/candidate-certification.yml` | IMPLEMENTED + CI PROVEN fail-closed |
| Certified artifact uploaded only after `release_ready=true`, zero blockers, all required PASS | `.github/workflows/candidate-certification.yml` | IMPLEMENTED + CI PROVEN fail-closed |
| Certification performs no wheel rebuild/tag/release mutation | `.github/workflows/candidate-certification.yml` | IMPLEMENTED + CI PROVEN WORKFLOW BOUNDARY |
| Candidate release-proof producer | `.github/workflows/candidate-release-proofs.yml` | NOT YET IMPLEMENTED / NEXT RELEASE BLOCKER |
| Candidate integration-evidence producer | `.github/workflows/candidate-integration-evidence.yml` | NOT YET IMPLEMENTED / NEXT RELEASE BLOCKER |

PR #84 merge SHA `bb9b7ed74e2696978c546011c893fb316ffdd57c`; final PR CI `33314924064`; main CI `33314977393`. Both Python matrices, wheel and ordinary readiness jobs succeeded; merged-main Python 3.13 reported **653 passed**.

The certification workflow cannot successfully create `release-readiness-certified-<candidate SHA>` today because its two fixed upstream producer workflows do not yet exist. That is intentional fail-closed behavior, not a bypass to fill with fabricated PASS data.

## Warehouse ambiguity / session recovery boundaries

| Guarantee | Current evidence |
|---|---|
| Matching same-transaction marker -> COMMITTED | REFERENCE + CI PROVEN |
| Marker absence alone -> UNRESOLVED | REFERENCE + CI PROVEN fail-closed |
| Unknown target outcome never blind retries | REFERENCE + CI PROVEN fail-closed |
| Simulated framework ACK loss != real network/driver fault | EXPLICIT EVIDENCE BOUNDARY |
| Real-fault drill requires actual execution exception | IMPLEMENTED + CI PROVEN runner contract |
| Normal return cannot PASS real-fault drill | REFERENCE + CI PROVEN false-positive guard |
| Exact session identity = connection_id + session_id | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Session already gone before inspection -> UNRESOLVED | REFERENCE + CI PROVEN fail-closed |
| Absence proof requires open transaction + Admin KILL + disappearance + marker reread | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Marker appearing during race forbids NOT_COMMITTED | REFERENCE + CI PROVEN race guard |
| Query Insights is not immediate absence proof | EXPLICIT EVIDENCE BOUNDARY |
| NOT_COMMITTED recovery does not auto re-execute | IMPLEMENTED + CI PROVEN fail-closed |

## Extension surfaces

| Extension kind | Entry-point group | Boundary |
|---|---|---|
| Capture observer | `fabric_data_framework.capture_observers` | translate provider/item observation into bounded evidence; cannot decide framework PASS |
| Spark execution data | `fabric_data_framework.spark_execution_data` | bounded runtime execution-data resolution |
| Warehouse mutation | `fabric_data_framework.warehouse_mutations` | bounded mutation using supplied framework-owned Connection; cannot commit/write marker/journal |
| Warehouse commit fault injector | `fabric_data_framework.warehouse_commit_fault_injectors` | provider/session-specific arm/disarm/verify; cannot manufacture commit/absence truth |

## Real proof / release work still missing

| Proof / capability | State |
|---|---|
| Frozen exact 0.4 candidate source SHA + inner wheel SHA256 | NOT YET FROZEN; candidate-capable artifact exists |
| Candidate release-proof producer workflow | NOT YET IMPLEMENTED |
| Candidate integration-evidence producer workflow | NOT YET IMPLEMENTED |
| `release-readiness-certified-<candidate SHA>` artifact | NOT YET PRODUCED |
| Enterprise Fabric identity/token | NOT YET RETAINED |
| Workspace/item authorization | NOT YET RETAINED |
| Production Fabric SQL/Azure SQL certification PASS | NOT YET RETAINED |
| Live approved Pipeline | NOT YET RETAINED |
| Live Copy + verified observation/receipt | NOT YET RETAINED |
| Live bounded Spark + verified observation/receipt | NOT YET RETAINED |
| Representative live FULL -> REPLACE | NOT YET RETAINED |
| Representative live WATERMARK -> SCD1 | NOT YET RETAINED |
| Representative live WATERMARK -> SCD2 | NOT YET RETAINED |
| Real retry/rerun idempotency + progress safety drill | NOT YET RETAINED |
| Real reconciliation fail-closed drill | NOT YET RETAINED |
| Live Warehouse target+marker transaction | NOT YET RETAINED |
| Provider-specific real ambiguous COMMIT fault | NOT YET RETAINED |
| Live exact Warehouse session/Admin DMV/KILL chain where required | NOT YET RETAINED |
| Complete exact-candidate proof bundle + certified IntegrationEvidenceManifest | NOT YET RETAINED |
| Release-readiness blockers = 0 | NOT YET; ORDINARY READINESS HAS 15 REQUIRED BLOCKERS |
| Live Debezium/Kafka certification | OUT OF SCOPE UNLESS 0.4 GA SCOPE PROMOTES IT |
| Capacity/IAM/network/DR/monitoring/governance | EXTERNAL / NOT YET RETAINED |

## Historical release proof

```text
v0.3.0 immutable release artifact = RELEASE PROVEN for v0.3.0
0.4.0 development source          = NOT RELEASED / FEATURE FROZEN / READINESS BLOCKED
release_allowed                   = false
```
