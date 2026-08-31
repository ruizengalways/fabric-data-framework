# MACHINE IMPLEMENTATION MAP

Use this file to locate the canonical owner before changing framework behavior. Explicit owner modules are preferred; broad root compatibility facades remain intentionally absent.

## Top-level ownership

```text
src/fabric_data_framework/
  contracts/       provider-neutral immutable semantic/runtime contracts
  metadata/        DatasetConfig + capability metadata
  capture/         source/capture semantics, bounded reads, onboarding/bootstrap
  apply/           target apply semantics
  data_plane/      Bronze/staging contracts
  quality/         reconciliation/schema/temporal quality contracts
  orchestration/   planning/dispatch/failure isolation
  execution/       execution plans/backends
  adapters/        provider transports/auth
  control_plane/   relational runtime state/schema/certification
  recovery/        retry/replay/target commit/ambiguous outcome recovery
  evidence/        integration/business-path evidence, readiness, certification
  deployment/      delivery/release provenance, candidate identity, project init/validation
  extensions/      bounded plugin loading/contracts
  cli/             removable presentation leaf
```

Dependency direction remains:

```text
business/source semantics
  -> DatasetConfig + semantic selection
  -> capability resolver
  -> immutable ExecutionPlan
  -> provider/framework execution
```

Provider mechanics must not become semantic truth.

## Core semantic owners

| Area | Canonical owner | Boundary |
|---|---|---|
| Dataset semantic truth | `metadata/config.py` | immutable source-controlled DatasetConfig |
| Capture semantics | `capture/semantic_contracts.py` | exact source/Bronze fidelity patterns |
| Onboarding/overclaim guards | `capture/onboarding.py` | source fidelity / delete / history truth |
| Capability resolution | `metadata/capabilities.py` | execution compatibility, not business semantics |
| FULL/WATERMARK/CDC bootstrap/recovery | capture modules | fenced no-gap/no-double-apply handoff |
| APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF | `apply/` | provider-neutral apply semantics |

Capture and apply stay orthogonal; SCD2 never upgrades source/capture fidelity.

## Fabric/provider owners

| Area | Canonical owner | Boundary |
|---|---|---|
| Fabric REST/auth | adapters Fabric modules | credentials not retained |
| Pipeline transport | Fabric Pipeline adapter/backend | provider terminal status != semantic success |
| Copy transport | Fabric Copy adapter | transport evidence only until receipt/reconciliation |
| Spark transport | Fabric Spark adapter | bounded execution evidence |
| Warehouse same-transaction marker | `recovery/fabric_warehouse.py` | target mutation + marker commit together |
| Exact-session absence | `recovery/fabric_warehouse_session_absence.py` | exact session/open tx/Admin KILL/marker reread |

## Integration evidence ownership

Canonical directory:

```text
src/fabric_data_framework/evidence/
```

| Area | Canonical owner | Boundary |
|---|---|---|
| Integration spec/result/manifest/hash | `integration_evidence.py` | exact framework wheel + exact domain release identities + check membership |
| Approved-run planning | `integration_runner.py` | checks env-var presence, physical bindings and mutation authorization; never retains secret value |
| Runtime/provider result projection | `integration_checks.py` | projection only; no semantic redefinition |
| Strict staged merge | `integration_evidence_merge.py` | no latest/PASS precedence; both release identities must match |
| Explicit Pipeline rerun prerequisite | `integration_evidence_rerun.py` | fully certified source -> new non-certified selected-check NOT_RUN projection |
| Control-plane runner | `approved_control_plane_runner.py` | real selected production-eligible backend |
| Pipeline runner | `approved_pipeline_runner.py` | native provider run + exact durable child outcome |
| Copy/Spark runner | `approved_capture_runner.py` | provider evidence + verified CaptureReceipt |
| Warehouse runner | `approved_warehouse_runner.py` | target mutation + marker |
| Ambiguous-COMMIT runner | `approved_warehouse_fault_runner.py` | real execution exception/fault/recovery evidence |
| Retained secret scan | `safety.py` | fail closed before evidence retention |

### Exact integration identity invariant

```text
IntegrationEvidenceSpec.release_hash
IntegrationEvidenceManifest.release_hash
  = exact framework candidate wheel SHA256

IntegrationEvidenceSpec.domain_release_hash
IntegrationEvidenceManifest.domain_release_hash
  = exact customer/domain ReleaseManifest.bundle.release_hash

ApprovedIntegrationRunnerConfig.framework_artifact_sha256
  = framework candidate wheel SHA256 in exact-candidate mode

ApprovedIntegrationRunnerConfig.release_hash
  = customer/domain ReleaseManifest.bundle.release_hash
```

They must never be assumed equal. Historical development/reference single-hash runner configs are compatibility-only when `domain_release_hash` is absent. Exact 0.4 candidate evidence must bind both values.

### Candidate integration producer — merged PR #90

Owner:

```text
.github/workflows/candidate-integration-evidence.yml
```

Merged-main provenance:

```text
merge SHA   7e12a320e73aa06f3e80f57e3deed14a6cc7add0
final PR CI 33349005817
main CI     33349064335
tests       728
state       MERGED + MAIN CI PROVEN
live proof  none
```

The workflow is orchestration only. It authenticates exact framework candidate/main-run/wheel provenance plus exact customer SHA/input-producer provenance, verifies the exact customer release/config/recipe/extension bytes, then reuses existing approved commands in this order:

```text
integration-item-smoke-run
integration-control-plane-certify-run
integration-evidence-merge            # base prerequisites
integration-pipeline-run
integration-capture-run               # Copy
integration-capture-run               # Spark
integration-warehouse-run
integration-evidence-merge            # add normal Warehouse PASS to fault prerequisites
integration-warehouse-fault-drill-run
integration-evidence-merge --require-certified
integration-evidence-validate --require-certified
```

It must not instantiate integration PASS results. Final PASS status may only be read from already-produced approved manifests for verification.

PR #90 also extends `IntegrationCheckPhysicalBinding` with optional `dataset_id`. Exact candidate integration certification requires the customer-owned `fabric.pipeline` binding to carry the representative dataset ID. This keeps WHAT in the domain repo and HOW in the framework.

General live mutation authorization and Admin Warehouse session-termination authorization remain separate.

## Business-path evidence — merged PR #88

Canonical detailed contract:

```text
docs/machine/BUSINESS_PATH_EVIDENCE.md
```

| Area | Canonical owner | Boundary |
|---|---|---|
| Five live gate enum/scenario/observation/evaluator | `evidence/business_path_evidence.py` | evaluator is sole readiness PASS authority |
| Mutating driver recipe/request/receipt | `evidence/business_path_driver.py` | receipt has no PASS/status |
| Exact five-gate certification plan | `evidence/business_path_plan.py` | exactly five gates; canonical project-root-contained paths |
| Approved execution orchestration | `evidence/approved_business_path_runner.py` | preflight/driver/observer/Pipeline/evaluator/cleanup separation |
| Explicit rerun source | `evidence/integration_evidence_rerun.py` | source must be fully certified exact integration evidence |
| CLI leaf | `cli/business_path.py` | loads exact files and delegates; no proof semantics |
| Candidate producer | `.github/workflows/candidate-business-path-evidence.yml` | executes live paths; cannot author PASS JSON directly |

PR #88 provenance:

```text
merge SHA   1632aefe8c1fd71098200c434a1648d0385f4967
PR CI       33346419772
main CI     33346470401
tests       717
```

Execution order:

```text
safe identity/precondition checks
-> PREPARE_BASELINE
-> read-only BEFORE observation
-> PREPARE_ATTEMPT_1
-> existing approved Pipeline runner
-> retry only: failed-state observation + PREPARE_ATTEMPT_2 + second Pipeline run
-> final observation
-> framework evaluator
-> CLEANUP in finally
-> retained report/partial proof only after cleanup succeeds
```

The approved business-path runner must not call the driver until exact config-bundle identity, framework/domain hashes, certified prerequisites, Pipeline binding, runtime env presence, fingerprinted artifacts and explicit mutation authorization have passed.

## Readiness / partial proof ownership

| Area | Canonical owner | Boundary |
|---|---|---|
| Readiness spec/result/report | `evidence/release_readiness.py` | exact version/candidate/wheel; no provider execution |
| Strict non-integration partial proof merge | `evidence/release_readiness_merge.py` | exact candidate/wheel; contradiction conflicts |
| `release-readiness` / `release-proofs-merge` | `cli/release.py` | presentation only |
| Source-controlled 0.4 policy | `release/0.4.0/readiness-spec.json` | 15 required gates; Debezium optional |
| Ordinary blocked report | `.github/workflows/ci.yml` | deliberately retains missing-evidence state |

Current final readiness chain:

```text
framework version
+ exact candidate source SHA
+ exact candidate inner wheel SHA256
+ exact customer/domain release hash in certified integration evidence
+ ReleaseReadinessProofBundle
+ certified IntegrationEvidenceManifest
-> ReleaseReadinessReport
```

Before candidate freeze, release-proof/certification must additionally machine-bind the same `domain_release_hash`; indirect references alone are not sufficient for final promotion identity.

## Candidate artifact / release producers

### Main candidate artifact

Owners:

```text
src/fabric_data_framework/deployment/candidate_artifact.py
.github/workflows/ci.yml
```

Latest merged candidate-capable main artifact after PR #90:

```text
source SHA         7e12a320e73aa06f3e80f57e3deed14a6cc7add0
main CI            33349064335
wheel SHA256       dbc9b0cbcc73598c94ae67c4798ba9eefdf6ba203a6169ff61088a9d1757c3b8
artifact ID        9742969993
selected/frozen    false
```

Retained bytes remain `wheel + SHA256SUMS + CANDIDATE.json`.

### Candidate release-proof producer — merged PR #87

Owner:

```text
.github/workflows/candidate-release-proofs.yml
```

Direct PASS scope is exactly:

```text
source.tests
wheel.integrity
customer.compatibility
```

The five live business-path gates must arrive from `candidate-business-path-evidence.yml`.

### Candidate business-path producer — merged PR #88

Owner:

```text
.github/workflows/candidate-business-path-evidence.yml
```

It authenticates exact framework candidate/run/wheel, exact customer SHA + customer input producer run, exact certified integration producer run, exact domain release, exact plan/scenario/driver/plugin bytes, then invokes the approved framework runner for exactly five gates and strict-merges one-gate proofs. It contains no direct PASS construction.

The workflow contract is merged + main-CI proven, but there is **no retained live business-path PASS artifact yet**.

### Candidate integration producer — merged PR #90

Owner:

```text
.github/workflows/candidate-integration-evidence.yml
```

It is **MERGED + MAIN CI PROVEN**, not live-service proven. It cannot succeed today until `fabric-customer/.github/workflows/candidate-business-path-inputs.yml`, exact domain recipes/extensions and protected real environment credentials exist.

## Candidate certification

Owners:

```text
src/fabric_data_framework/evidence/candidate_certification.py
cli/release.py -> candidate-certify
.github/workflows/candidate-certification.yml
```

Certification performs aggregation only. It never executes Fabric, rebuilds wheel bytes, tags or releases. It requires a complete exact release-proof bundle plus fully certified exact integration evidence.

## Exact immutable promotion

Owner:

```text
.github/workflows/release.yml
```

Release is manual exact-byte promotion. It re-verifies candidate source/run/wheel and certified evidence, then tags the exact candidate SHA and publishes already-certified bytes. No release-time wheel rebuild exists.

## Customer project / delivery

| Area | Canonical owner |
|---|---|
| Config bundle hashing/loading/materialization | `deployment/delivery.py` |
| Release manifest/provenance | deployment contracts/delivery |
| Customer project scaffold | `deployment/project.py` |
| Whole-project static validation | `deployment/project.py` |
| Semantic onboarding validation | `capture/onboarding.py` |
| Capability validation | `metadata/capabilities.py` |

`project-init` never guesses key/watermark/delete/history semantics or creates Fabric resources. `project-validate` is static and never upgrades to live evidence.

## CLI boundary

| File | Responsibility |
|---|---|
| `cli/main.py` | tiny composition root |
| `cli/project.py` | project init/validate |
| `cli/release.py` | readiness/proof merge/candidate certification |
| `cli/approved.py` | approved integration provider runners |
| `cli/business_path.py` | approved representative business-path runner presentation |
| `cli/base.py` | general validation/metadata/deployment/preflight |

Non-negotiable dependency:

```text
cli -> reusable core/evidence/deployment
core/evidence/deployment -X-> cli
```

## Controlled extension groups

```text
fabric_data_framework.capture_observers
fabric_data_framework.spark_execution_data
fabric_data_framework.warehouse_mutations
fabric_data_framework.warehouse_commit_fault_injectors
fabric_data_framework.business_path_observers
fabric_data_framework.business_path_drivers
```

Business-path observer supplies read-only semantic facts; driver prepares bounded fixture/fault state. Neither can redefine framework PASS.

## Next release implementation order

```text
fabric-customer business-path/integration input producer + exact live extensions/plan
-> hard-bind domain_release_hash across final release proof/certification
-> validate producer and identity contracts fail closed
-> freeze one exact candidate only after producer paths are ready
-> certified integration evidence
-> five representative live business-path proofs
-> candidate-release-proofs
-> candidate-certification
-> exact-byte release
```

Do not collapse independent truth sources into a workflow that authors PASS JSON.

## Documentation ownership

```text
docs/machine/STATE.md                    exact current state
docs/machine/CONTEXT.md                  durable semantic/recovery invariants
docs/machine/APPROVED_EVIDENCE.md        integration approved-run rules
docs/machine/BUSINESS_PATH_EVIDENCE.md   representative live business-path contract
docs/machine/RELEASE_READINESS.md        release-system identity/order/gates
docs/machine/CAPABILITIES.md             capability/evidence matrix
docs/machine/IMPLEMENTATION_MAP.md        canonical implementation ownership
docs/machine/HISTORY.md                   compact merged milestone history
```
