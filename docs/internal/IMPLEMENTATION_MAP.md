# Implementation map

Use this file to locate the canonical module before changing framework behavior. It is a code-ownership map, not a second architecture or release-history document.

## Top-level package ownership

```text
src/fabric_data_framework/
  contracts/       provider-neutral immutable runtime/semantic contracts
  metadata/        DatasetConfig + capability metadata
  capture/         source/capture semantics and onboarding/bootstrap
  apply/           target apply semantics
  data_plane/      Bronze/staging contracts
  quality/         DQ/reconciliation/schema/temporal quality
  orchestration/   planning/dispatch/failure isolation
  execution/       execution plans/backends/Pipeline child
  adapters/        Fabric/provider transports and auth
  control_plane/   relational operational state/schema/certification
  recovery/        retry/replay/rebuild/impact/cutover/target-commit recovery
  evidence/        integration/business-path/readiness evidence
  certification/   installed-wheel/bounded/unified framework certification
  deployment/      project scaffold, delivery provenance, candidate artifact
  extensions/      bounded extension registry/contracts
  cli/             presentation/composition leaf
```

Core dependency direction:

```text
source/business semantics
-> DatasetConfig / semantic selection
-> capability resolution
-> immutable ExecutionPlan
-> provider/framework execution
-> durable evidence/recovery
```

Provider mechanics must not become semantic truth.

## Semantic owners

| Area | Canonical owner |
|---|---|
| Dataset semantic config | `metadata/config.py` |
| Capture fidelity/delete/history contracts | `capture/semantic_contracts.py` |
| Onboarding/overclaim guards | `capture/onboarding.py` |
| Capability resolution | `metadata/capabilities.py` |
| FULL/WATERMARK/CDC bootstrap | capture bootstrap modules |
| APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF | `apply/` |
| DQ/quarantine/reconciliation | `quality/` |
| Execution-group planning/dependencies | orchestration/contracts |

Capture and apply stay orthogonal. SCD2 never upgrades source fidelity.

## Recovery/rebuild owners

| Area | Canonical owner | Important boundary |
|---|---|---|
| Reprocess request/run-mode contract | `contracts/recovery.py` | non-normal work must be explicit/audited |
| Rebuild scope + post-rebuild state contract | `contracts/rebuild.py` | `TARGET_ONLY`, `CAPTURE_AND_TARGET`, `AUTHORITATIVE_RESET` |
| FULL_REBUILD coordinator | `recovery/rebuild.py` | requested scope must equal completed scope before state cutover |
| Issue origin + immutable impact plan | `contracts/rebuild_impact.py` | first bad point determines minimum root scope |
| Dependency-aware impact planner | `recovery/rebuild_impact.py` | only root + downstream descendants; unrelated branches excluded |
| Versioned physical target/cutover contracts | `contracts/target_version.py` | stable logical object + explicit physical version + validation/approval gate |
| Blue/green logical-binding cutover coordinator | `recovery/target_cutover.py` | optimistic generation check; no automatic old-version deletion |
| Retry/unknown outcome runtime | `recovery/runtime.py` | no blind retry after ambiguous commit |
| Quarantine replay | `recovery/replay.py` | retained immutable payload only |
| Warehouse same-transaction marker | `recovery/fabric_warehouse.py` | target mutation + marker commit together |
| Exact-session absence/recovery | `recovery/fabric_warehouse_session_absence.py` | Admin path separately authorized |

Rebuild scope invariant:

```text
TARGET_ONLY
  -> retained capture/Bronze is authoritative
  -> capture/runtime state replacement must be unchanged

CAPTURE_AND_TARGET
  -> rebuild capture/Bronze + target
  -> checkpoint/boundary may change
  -> RebuildProgressKind may not change

AUTHORITATIVE_RESET
  -> widest reset
  -> explicit post-rebuild state required
  -> RebuildProgressKind may change
```

Impact/cutover invariant:

```text
first untrustworthy root
-> compute only downstream contaminated subgraph
-> rebuild in dependency waves
-> build v2 candidate beside active v1 when blue/green is required
-> reconciliation + consumer/UAT validation + approval
-> switch stable logical binding
-> retain v1 for rollback
-> manual cleanup only
```

All three rebuild scopes are scopes of `RunMode.FULL_REBUILD`; they are not separate run modes. Permanent business-data purge is deliberately outside framework automation.

## Fabric/provider owners

| Area | Canonical owner | Important boundary |
|---|---|---|
| Fabric auth/REST | `adapters/fabric/` | secrets not retained |
| Fabric Pipeline backend | `execution/backends/fabric_pipeline.py` | provider terminal status != semantic outcome |
| Pipeline child contract | `execution/pipeline_child.py` | exact config/plan/run correlation |
| Fabric capture transports | `adapters/fabric/capture_transports.py` | provider evidence + framework receipt |
| Fabric SQL auth | `adapters/fabric/sql_auth.py` | token/runtime credential boundary |
| Warehouse same-transaction marker | `recovery/fabric_warehouse.py` | target mutation + marker commit together |
| Exact-session absence/recovery | `recovery/fabric_warehouse_session_absence.py` | Admin path separately authorized |

## Certification owners

| Area | Canonical owner |
|---|---|
| Active installed package vs wheel bytes | `certification/installed.py` |
| Installed semantic smoke | `certification/semantic.py` |
| Lakehouse bounded Fabric checks | `certification/bounded.py` |
| Conventional one-call API | `certification/simple.py` |
| Unified environment-dependent orchestrator | `certification/unified.py` |
| Framework-owned reference integration fixtures/config | `certification/integration_project/` and packaged certification resources |

`certify_installed()` is the preferred high-level boundary: attest installed bytes first, then execute semantic/Fabric certification.

## Integration evidence owners

| Area | Canonical owner | Boundary |
|---|---|---|
| Spec/result/manifest/hash | `evidence/integration_evidence.py` | exact framework + integration-input identities |
| Approved run planning/config | `evidence/integration_runner.py` | bindings, runtime names, authorization, identity |
| Provider result projection | `evidence/integration_checks.py` | does not redefine semantic truth |
| Strict merge | `evidence/integration_evidence_merge.py` | contradictory reruns do not use precedence shortcuts |
| Explicit rerun projection | `evidence/integration_evidence_rerun.py` | fully bound source evidence required |
| Control Plane runner | `evidence/approved_control_plane_runner.py` | real selected backend |
| Pipeline runner | `evidence/approved_pipeline_runner.py` | native run + exact durable child outcome |
| Copy/Spark runner | `evidence/approved_capture_runner.py` | native provider evidence + verified CaptureReceipt |
| Warehouse runner | `evidence/approved_warehouse_runner.py` | mutation + marker proof |
| Ambiguous-COMMIT runner | `evidence/approved_warehouse_fault_runner.py` | real fault/recovery evidence |
| Secret scan | `evidence/safety.py` | fail closed before retention |

Identity invariant:

```text
IntegrationEvidenceSpec.framework_artifact_sha256
  = exact candidate framework wheel SHA256

IntegrationEvidenceSpec.integration_inputs_hash
  = exact framework-owned integration input bundle hash

ApprovedIntegrationRunnerConfig.framework_artifact_sha256
  = same exact candidate wheel SHA256

ApprovedIntegrationRunnerConfig.integration_inputs_hash
  = same exact integration input bundle hash
```

No customer/domain release identity is part of framework candidate certification.

## Business-path evidence owners

| Area | Canonical owner |
|---|---|
| Scenarios/observations/evaluator | `evidence/business_path_evidence.py` |
| Driver recipe/request/receipt | `evidence/business_path_driver.py` |
| Five-gate certification plan | `evidence/business_path_plan.py` |
| Approved execution orchestration | `evidence/approved_business_path_runner.py` |
| Candidate proof packaging | `evidence/business_path_release_proof.py` |

Representative gates are:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

Drivers/observers report execution facts; evaluator/readiness code owns PASS authority.

## Release-readiness owners

| Area | Canonical owner |
|---|---|
| Readiness spec/proof/result/report | `evidence/release_readiness.py` |
| Strict proof merge | `evidence/release_readiness_merge.py` |
| Business-path partial proof packaging | `evidence/business_path_release_proof.py` |
| Candidate certification aggregation | `evidence/candidate_certification.py` |
| Candidate artifact identity | `deployment/candidate_artifact.py` |
| Source-controlled policy | `release/<version>/readiness-spec.json` |
| Candidate integration-input producer | `.github/workflows/candidate-integration-inputs.yml` |
| Candidate integration evidence | `.github/workflows/candidate-integration-evidence.yml` |
| Candidate business paths | `.github/workflows/candidate-business-path-evidence.yml` |
| Candidate release proofs | `.github/workflows/candidate-release-proofs.yml` |
| Final candidate aggregation | `.github/workflows/candidate-certification.yml` |
| Exact-byte publication/promotion | `.github/workflows/release.yml` |

Final framework candidate chain:

```text
framework source/version provenance
+ framework_artifact_sha256
+ integration_inputs_hash
+ required release proofs
+ certified integration evidence
-> fail-closed ReleaseReadinessReport
-> explicit release authorization
-> exact-byte promotion
```

## Implementation project owners

| Area | Canonical owner |
|---|---|
| Config bundle hashing/materialization | `deployment/delivery.py` |
| Project scaffold/static validation | `deployment/project.py` |
| Semantic onboarding | `capture/onboarding.py` |
| Capability validation | `metadata/capabilities.py` |
| Project-specific DatasetConfig/mappings/bindings | implementation/domain repo |
| Physical v1/v2 target names and provider-specific logical-binding adapter | implementation/domain repo |
| UAT/business validation and approval reference | implementation/domain governance |
| Old target-version deletion after rollback window | manual operator/governance process |

`project-init` never guesses source semantics or creates Fabric resources. `project-validate` is static and never upgrades itself to live evidence.

## CLI boundary

```text
cli -> reusable framework/deployment/evidence modules
reusable modules -X-> cli
```

The CLI is a presentation/composition leaf. Business/evidence semantics belong in reusable modules so the same contracts can be used from CI, notebooks and other callers.

## Documentation ownership

```text
docs/ARCHITECTURE.md                 durable architecture
docs/GETTING_STARTED.md              setup/consumption
docs/IMPLEMENTATION_PROJECT.md       real consumer project runbook
docs/DATA_PATTERNS.md                source/capture/apply decisions
docs/OPERATIONS.md                   transient runtime operations/recovery
docs/REPAIR_AND_REBUILD.md           data correctness repair/rebuild/v1-v2 cutover
docs/CODE_READING_GUIDE.md           end-to-end source reading order/call graph
docs/TESTING_AND_CERTIFICATION.md    certification lifecycle
docs/RELEASE.md                      release lifecycle
docs/reference/                      narrow technical contracts
docs/internal/STATE.md               exact current state
docs/internal/CAPABILITIES.md        capability/evidence matrix
docs/internal/IMPLEMENTATION_MAP.md  this module map
```
