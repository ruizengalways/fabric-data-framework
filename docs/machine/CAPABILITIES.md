# MACHINE CAPABILITY MATRIX

Evidence vocabulary:

```text
REFERENCE / CONTRACT       deterministic semantic/runtime implementation
CI PROVEN                  static/tests/build succeeded
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

## Developer / customer project bootstrap and dry run

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Non-destructive customer/domain repo scaffold | `deployment/project.py` | REFERENCE + CI PROVEN |
| `project-init` CLI adapter | `cli/project.py` | PRESENTATION + CI PROVEN |
| Existing-file no-overwrite guard | `deployment/project.py` | REFERENCE + CI PROVEN |
| Existing manifest domain-match guard | `deployment/project.py` | REFERENCE + CI PROVEN |
| Mixed FULL/WATERMARK/CDC + SCD1/SCD2 datasets in one domain repo | DatasetConfig + scaffold/runbook | REFERENCE MODEL + CI PROVEN scaffold |
| Dataset inventory before semantic configuration | generated `docs/dataset-inventory.csv` | DEVELOPER WORKFLOW CONTRACT + CI PROVEN |
| Whole-project static dry run | `deployment/project.py` | REFERENCE + CI PROVEN |
| `project-validate` CLI adapter | `cli/project.py` | PRESENTATION + CI PROVEN |
| Dependency reference validation | `deployment/project.py` | REFERENCE + CI PROVEN fail-closed |
| Dependency cycle detection | `deployment/project.py` | REFERENCE + CI PROVEN fail-closed |
| Capture/apply engine capability validation across project | `deployment/project.py` + `metadata/capabilities.py` | REFERENCE + CI PROVEN |
| Exact semantic-selection coverage for every DatasetConfig | `deployment/project.py` + `capture/onboarding.py` | REFERENCE + CI PROVEN fail-closed |
| Unknown semantic-selection dataset rejection | `deployment/project.py` | REFERENCE + CI PROVEN fail-closed |
| Per-dataset semantic overclaim validation in project dry run | `capture/onboarding.py` via `deployment/project.py` | REFERENCE + CI PROVEN |
| Deterministic workload summary by capture/apply/group/engine | `deployment/project.py` | REFERENCE + CI PROVEN |
| Retained JSON project-validation report | `cli/project.py` | DEVELOPER/CI ARTIFACT + CI PROVEN |

Boundary: project init/validation operates on source-controlled structure and metadata only. It does not infer source semantics, create Fabric resources, mutate live environments, persist secrets, validate workspace authorization, execute providers, or prove target/recovery behavior. A PASS means the source-controlled project is internally valid under portable framework contracts; it does not raise any live Fabric evidence claim.

## Fabric/provider execution

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Fabric Data Pipeline backend | Pipeline backend | IMPLEMENTED + CI PROVEN BACKEND |
| Copy Job REST transport | Fabric Copy adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Spark Job Definition REST transport | Fabric Spark adapter | IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT |
| Provider Completed insufficient for semantic success | Pipeline/capture adapters | REFERENCE + CI PROVEN |
| Fabric Warehouse same-transaction target marker | Warehouse recovery | IMPLEMENTED + CI PROVEN PROVIDER COMMIT CONTRACT |

## Control plane / target recovery

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Durable target-operation CAS journal | target operations + IO | IMPLEMENTED + CI PROVEN REFERENCE |
| UNKNOWN tri-state recovery | recovery modules | IMPLEMENTED + CI PROVEN REFERENCE |
| SQLAlchemy relational runtime repository | `control_plane/sqlalchemy_repository.py` | IMPLEMENTED + CI PROVEN RELATIONAL RUNTIME |
| Control-plane backend conformance certification | certification modules | IMPLEMENTED + CI PROVEN CONTRACT |
| Runtime does not silently migrate production schema | repository/runtime boundary | REFERENCE + CI PROVEN GUARDRAIL |

## Approved evidence surfaces

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Evidence spec/manifest/hash | `evidence/integration_evidence.py` | IMPLEMENTED + CI PROVEN EVIDENCE HARNESS CONTRACT |
| Credential-safe approved-run preflight | `evidence/integration_runner.py` | IMPLEMENTED + CI PROVEN APPROVED-RUN PREFLIGHT CONTRACT |
| Read-only Fabric item smoke | integration runner/checks | IMPLEMENTED + CI PROVEN READ-ONLY RUNNER CONTRACT |
| Strict staged evidence merge | `evidence/integration_evidence_merge.py` | IMPLEMENTED + CI PROVEN EVIDENCE MERGE CONTRACT |
| Approved control-plane certification | `evidence/approved_control_plane_runner.py` | IMPLEMENTED + CI PROVEN APPROVED CONTROL-PLANE CERTIFICATION RUNNER CONTRACT |
| Approved Pipeline execution evidence | `evidence/approved_pipeline_runner.py` | IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT |
| Approved Copy/Spark capture evidence | `evidence/approved_capture_runner.py` | IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT |
| Approved Warehouse commit/recovery | `evidence/approved_warehouse_runner.py` | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT |
| Approved real ambiguous-COMMIT drill | `evidence/approved_warehouse_fault_runner.py` | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT |

## Release readiness / candidate certification aggregation

| Capability | Implementation owner | Current evidence |
|---|---|---|
| Source-controlled 0.4 readiness matrix | `release/0.4.0/readiness-spec.json` | CONTRACT + CI PROVEN |
| Exact candidate source-SHA binding | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Exact artifact-SHA binding for live IntegrationEvidenceManifest | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Generic proof cannot bypass integration-backed gate | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Required `NOT_RUN` / `FAIL` / `OUT_OF_SCOPE` blocks release | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN fail-closed |
| Optional `OUT_OF_SCOPE` support | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN |
| `release_ready=true` iff all required gates PASS | `evidence/release_readiness.py` | IMPLEMENTED + CI PROVEN |
| `release-readiness` report CLI | `cli/release.py` | PRESENTATION + CI PROVEN |
| `--require-ready` hard non-zero gate | `cli/release.py` | PRESENTATION + CI PROVEN |
| CI-retained blocked readiness report | `.github/workflows/ci.yml` | CI PROVEN; current main has 15 blockers |
| Candidate wheel manifest binds source/run/attempt/inner SHA256 | `deployment/candidate_artifact.py` | IMPLEMENTED CONTRACT; PR CI REQUIRED |
| Candidate manifest rejects wheel-byte/version/provenance mismatch | `deployment/candidate_artifact.py` | IMPLEMENTED fail-closed; PR CI REQUIRED |
| Main CI candidate artifact contains wheel + SHA256SUMS + CANDIDATE.json | `.github/workflows/ci.yml` | IMPLEMENTED WORKFLOW CONTRACT; PR CI REQUIRED |
| Main candidate artifact longer retention than PR artifact | `.github/workflows/ci.yml` | IMPLEMENTED WORKFLOW POLICY; PR CI REQUIRED |
| Exact certified wheel promotion without rebuild | `.github/workflows/release.yml` | IMPLEMENTED RELEASE CONTRACT; PR CI REQUIRED |
| Release requires certified readiness artifact bound to exact wheel | `.github/workflows/release.yml` | IMPLEMENTED fail-closed RELEASE CONTRACT; PR CI REQUIRED |
| Candidate-certification workflow that produces certified readiness artifact | future `.github/workflows/candidate-certification.yml` | NOT YET IMPLEMENTED / NEXT RELEASE BLOCKER |

Boundary: ordinary readiness CI proves that the aggregator fails closed; candidate-artifact CI proves candidate identity; neither certifies Fabric or makes 0.4 releasable. The candidate source SHA and exact inner wheel SHA256 have not yet been frozen for live certification, and no `release-readiness-certified-<candidate SHA>` artifact exists yet.

## Warehouse ambiguity / session recovery

| Guarantee | Current evidence |
|---|---|
| Matching same-transaction marker -> COMMITTED | REFERENCE + CI PROVEN |
| Marker absence alone -> UNRESOLVED | REFERENCE + CI PROVEN fail-closed |
| Unknown target outcome never blind retries | REFERENCE + CI PROVEN fail-closed |
| Simulated framework ACK loss is not real network/driver proof | EXPLICIT EVIDENCE BOUNDARY |
| Real-fault drill requires actual observed execution exception | IMPLEMENTED + CI PROVEN runner contract |
| Normal transaction return cannot PASS real-fault drill | REFERENCE + CI PROVEN false-positive guard |
| Fault arm/verification identity must match | REFERENCE + CI PROVEN fail-closed |
| Fault injector cannot manufacture NOT_COMMITTED | EXPLICIT EVIDENCE BOUNDARY |
| Exact Warehouse session identity = connection_id + session_id | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Session ID alone is insufficient | REFERENCE + CI PROVEN fail-closed |
| Session already gone before inspection remains UNRESOLVED | REFERENCE + CI PROVEN fail-closed |
| Absence proof requires open_transaction_count > 0 | REFERENCE + CI PROVEN fail-closed |
| Admin DMV lookup exact-filters connection + session | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Session termination uses validated `KILL <session_id>` | IMPLEMENTED + CI PROVEN PROVIDER CONTRACT |
| Post-termination exact session disappearance required | REFERENCE + CI PROVEN fail-closed |
| Marker must be re-read after termination | IMPLEMENTED + CI PROVEN race guard |
| Marker appearing during race forbids NOT_COMMITTED | REFERENCE + CI PROVEN race guard |
| Query Insights is not immediate absence proof | EXPLICIT EVIDENCE BOUNDARY |
| Admin credential/env-var name separate from ordinary Warehouse credential | IMPLEMENTED + CI PROVEN approved recovery guardrail |
| Fault authorization does not imply Admin termination authorization | IMPLEMENTED + CI PROVEN approved recovery guardrail |
| Admin secret value not read on COMMITTED path | IMPLEMENTED + CI PROVEN least-privilege guardrail |
| Safe session termination reconciles UNKNOWN -> NOT_COMMITTED | IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE SESSION-TERMINATION RECOVERY CONTRACT |
| NOT_COMMITTED recovery does not auto re-execute | IMPLEMENTED + CI PROVEN fail-closed |
| NOT_COMMITTED operational recovery does not PASS committed fault-drill evidence | EXPLICIT EVIDENCE SEPARATION |

## Extension surfaces

| Extension kind | Entry-point group | Boundary |
|---|---|---|
| Capture observer | `fabric_data_framework.capture_observers` | translate provider/item observation into bounded evidence; cannot decide framework PASS |
| Spark execution data | `fabric_data_framework.spark_execution_data` | bounded runtime execution-data resolution |
| Warehouse mutation | `fabric_data_framework.warehouse_mutations` | bounded mutation using supplied framework-owned Connection; cannot commit/write marker/journal |
| Warehouse commit fault injector | `fabric_data_framework.warehouse_commit_fault_injectors` | provider/session-specific arm/disarm/verify; cannot manufacture commit/absence truth |

## Real proof still missing

| Proof | State |
|---|---|
| Frozen exact 0.4 candidate source SHA + inner wheel SHA256 | NOT YET FROZEN |
| Candidate-certification workflow / certified readiness artifact | NOT YET IMPLEMENTED / NOT YET PRODUCED |
| Enterprise Fabric identity/token | NOT YET RETAINED |
| Workspace/item authorization | NOT YET RETAINED |
| Production Fabric SQL/Azure SQL certification PASS | NOT YET RETAINED |
| Live approved Pipeline | NOT YET RETAINED |
| Live Copy Job + verified observation/receipt | NOT YET RETAINED |
| Live bounded Spark + verified observation/receipt | NOT YET RETAINED |
| Representative live FULL -> REPLACE | NOT YET RETAINED |
| Representative live WATERMARK -> SCD1 | NOT YET RETAINED |
| Representative live WATERMARK -> SCD2 | NOT YET RETAINED |
| Real retry/rerun idempotency + progress safety drill | NOT YET RETAINED |
| Real reconciliation fail-closed drill | NOT YET RETAINED |
| Live Warehouse target+marker transaction | NOT YET RETAINED |
| Provider-specific real ambiguous COMMIT fault | NOT YET RETAINED |
| Live exact Warehouse session capture | NOT YET RETAINED |
| Live Admin DMV/KILL/rollback chain | NOT YET RETAINED |
| Production-approved marker absence proof | NOT YET RETAINED |
| Complete exact-candidate release proof bundle + integration evidence | NOT YET RETAINED |
| Release-readiness blockers = 0 | NOT YET; CURRENTLY 15 REQUIRED BLOCKERS |
| Live Debezium/Kafka certification | OUT OF SCOPE UNLESS 0.4 GA SCOPE PROMOTES IT |
| Capacity/IAM/network/DR/monitoring/governance | EXTERNAL / NOT YET RETAINED |

## Historical release proof

```text
v0.3.0 immutable release artifact = RELEASE PROVEN for v0.3.0
0.4.0 development source          = NOT RELEASED / FEATURE FROZEN / READINESS BLOCKED
```
