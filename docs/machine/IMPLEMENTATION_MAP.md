# MACHINE IMPLEMENTATION MAP

Use this file to locate the canonical implementation owner before editing framework behavior. Explicit owner modules are preferred; broad compatibility facades are intentionally absent.

## Top-level package ownership

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
  evidence/        integration evidence, approved runners, release readiness, proof merge, candidate certification
  deployment/      delivery/release provenance, candidate artifact identity, project init/validation
  extensions/      bounded plugin loading/contracts
  cli/             removable presentation leaf
```

The package root is namespace-only. Do not reintroduce root facades or old flat module aliases.

## Semantic configuration

| Area | Canonical owner | Boundary |
|---|---|---|
| Dataset semantic truth | `metadata/config.py` | immutable source-controlled DatasetConfig |
| Shared typed contracts | `contracts/` | provider-neutral value objects |
| Orthogonal capture semantics | `capture/semantic_contracts.py` | 14 exact source/Bronze semantic presets |
| Semantic onboarding / overclaim guards | `capture/onboarding.py` | validates source fidelity, delete/history claims |
| Capability resolution | `metadata/capabilities.py` | execution compatibility, not business semantics |
| Full -> WATERMARK / Snapshot -> CDC bootstrap | capture bootstrap modules | no-gap/no-double-apply fenced handoff |

Critical dependency direction:

```text
business/source semantics
        ↓
DatasetConfig + semantic selection
        ↓
capability resolver
        ↓
immutable ExecutionPlan
        ↓
provider/framework execution
```

Do not encode provider-specific execution details as semantic truth when capability/adapters can own them.

## Capture / Bronze / Apply

| Area | Canonical owner |
|---|---|
| Bronze record/lineage | `data_plane/bronze.py` |
| Watermark/file/API/snapshot/stream capture | `capture/` |
| CDC order/dedupe/checkpoint | CDC modules under capture/data-plane owners |
| Debezium/Kafka normalization/recovery | CDC adapter modules |
| Delta CDF bounded recovery | Delta/CDF adapter modules |
| APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF | `apply/` |

Capture strategy and apply strategy remain orthogonal. SCD2 never upgrades source/capture fidelity.

## Fabric/provider adapters

| Area | Canonical owner | Boundary |
|---|---|---|
| Fabric REST token abstraction | Fabric auth adapter modules | credentials never persisted in retained evidence |
| Pipeline scheduling/execution transport | Fabric Pipeline backend | provider terminal status != semantic success |
| Copy Job REST transport | Fabric Copy adapter | transport evidence only until CaptureReceipt/reconciliation succeeds |
| Spark Job Definition transport | Fabric Spark adapter | bounded execution evidence |
| Provider-native evidence conversion | Fabric capture/evidence adapters | cannot manufacture framework PASS |

## Target operations / recovery

| Area | Canonical owner | Critical invariant |
|---|---|---|
| Logical target-operation identity | `contracts/target_operation.py` | attempt-independent operation key |
| Persistent target-operation CAS | control-plane target-operation journal | UNKNOWN/IN_PROGRESS cannot blind retry |
| Generic commit probes | `recovery/target_probe.py` | COMMITTED / NOT_COMMITTED / UNRESOLVED |
| Fabric Warehouse same-transaction marker | `recovery/fabric_warehouse.py` | mutation + marker commit together |
| Exact-session absence proof | `recovery/fabric_warehouse_session_absence.py` | exact connection/session + open tx + Admin KILL + marker reread |
| Provider fault injection contract | `recovery/warehouse_fault_injection.py` | may cause/verify fault; cannot decide commit truth |

Marker absence alone is UNRESOLVED. Unknown commit outcome never permits blind re-execution.

## Relational control plane

| Area | Canonical owner |
|---|---|
| SQLAlchemy runtime repository | `control_plane/sqlalchemy_repository.py` |
| Backend certification profiles/contracts | control-plane certification modules |
| Schema materialization/migration | control-plane/deployment/CLI modules |

Production runtime never silently provisions or migrates control-plane schema.

## Integration evidence

Canonical owner:

```text
src/fabric_data_framework/evidence/
```

| Area | Canonical owner | Boundary |
|---|---|---|
| Evidence check/spec/result/manifest/hash | `evidence/integration_evidence.py` | exact environment/domain/framework/release/check membership |
| Projection from existing runtime/provider outcomes | `evidence/integration_checks.py` | projection only; no semantic redefinition |
| Credential-free approved-run planning | `evidence/integration_runner.py` | secret env-var names allowed, values not retained |
| Strict partial manifest merge | `evidence/integration_evidence_merge.py` | conflicting substantive reruns reject; no latest/PASS precedence |
| Retained text secret scanning | `evidence/safety.py` | fail closed before evidence retention |
| Approved control-plane runner | `evidence/approved_control_plane_runner.py` | real selected backend certification surface |
| Approved Pipeline runner | `evidence/approved_pipeline_runner.py` | remote execution + exact durable child outcome |
| Approved Copy/Spark runner | `evidence/approved_capture_runner.py` | provider evidence + verified CaptureReceipt |
| Approved Warehouse runner | `evidence/approved_warehouse_runner.py` | target mutation + same-transaction marker |
| Approved ambiguous-COMMIT runner | `evidence/approved_warehouse_fault_runner.py` | real execution exception/fault identity/recovery proof |

Evidence proves existing core semantics/runtime behavior. It must not modify core truth merely to get PASS.

## Release readiness and partial proof merge

Source-controlled readiness policy:

```text
release/0.4.0/readiness-spec.json
```

| Area | Canonical owner | Boundary |
|---|---|---|
| Readiness gate/spec/result models | `evidence/release_readiness.py` | exact framework version + candidate SHA; no provider execution |
| Non-integration proof bundle | `evidence/release_readiness.py` | source/wheel/customer + representative business-path evidence |
| Strict partial proof merge | `evidence/release_readiness_merge.py` | exact schema/version/source/wheel identity; no precedence for contradictory substantive reruns |
| Integration-backed gate projection | `evidence/release_readiness.py` + `evidence/integration_evidence.py` | generic proof cannot bypass provider/live integration gate |
| Ordinary readiness / proof-merge CLI | `cli/release.py` | presentation only |
| 0.4 readiness policy | `release/0.4.0/readiness-spec.json` | 15 required gates; Debezium optional unless scope changes |
| Blocked-report CI contract | `.github/workflows/ci.yml` | deliberately proves fail-closed behavior with missing evidence |

Exact readiness identity:

```text
framework version
+ exact candidate source SHA
+ exact inner wheel SHA256
+ ReleaseReadinessProofBundle
+ IntegrationEvidenceManifest(release_hash == wheel SHA256)
-> ReleaseReadinessReport
```

Strict release-proof merge was merged in PR #86 (`0f70e037806482c677fccae0ce9432504f2a9885`) with PR CI `33342779028`, main CI `33342806854`, and 664 tests.

## Candidate artifact identity

Canonical reusable owner:

```text
src/fabric_data_framework/deployment/candidate_artifact.py
```

Main CI `.github/workflows/ci.yml` builds one candidate wheel and retains `wheel + SHA256SUMS + CANDIDATE.json`. `CANDIDATE.json` binds source SHA, framework version, workflow run ID/attempt, wheel filename and inner wheel SHA256. Verification is standard-library only so candidate bytes are authenticated before installation.

A GitHub artifact archive digest is not the inner wheel SHA256.

## Candidate release proof producer

Workflow owner:

```text
.github/workflows/candidate-release-proofs.yml
```

Current feature-branch status: **IMPLEMENTED / CI PENDING**.

Ownership table:

| Area | Canonical owner | Boundary |
|---|---|---|
| Verify exact candidate main-CI provenance and required jobs | `candidate-release-proofs.yml` | source.tests PASS only after observed successful exact main CI |
| Re-authenticate CANDIDATE.json/SHA256SUMS/wheel bytes | `candidate-release-proofs.yml` + `deployment/candidate_artifact.py` | wheel.integrity PASS only for exact downloaded bytes |
| Exact `fabric-customer` source/main ancestry | `candidate-release-proofs.yml` | selected customer SHA must be explicit and reachable from customer main |
| Customer project + 100-table Health exact-candidate validation | `candidate-release-proofs.yml` + customer tooling | customer.compatibility PASS only after current candidate validation |
| Static partial proof | `candidate-release-proofs.yml` | contains only source.tests / wheel.integrity / customer.compatibility |
| Live business-path partial proof | future `.github/workflows/candidate-business-path-evidence.yml` | must own FULL/REPLACE, SCD1, SCD2, retry and reconciliation retained live evidence |
| Static/live strict merge | `candidate-release-proofs.yml` -> `release-proofs-merge` | final proof requires exact candidate/wheel match and no contradictory evidence |
| Final non-integration proof artifact | `candidate-release-proofs.yml` | upload only when exactly all 8 required non-integration gates exist and PASS |

The workflow must never add direct PASS records for `full.replace`, `watermark.scd1`, `watermark.scd2`, `retry.idempotency`, or `reconciliation.fail_closed`. Those belong to actual retained business-path execution evidence.

## Candidate certification

Source-controlled integration check template:

```text
release/0.4.0/integration-evidence-template.json
```

Reusable certification owner:

```text
src/fabric_data_framework/evidence/candidate_certification.py
```

Presentation/workflow owners:

```text
cli/release.py -> candidate-certify
.github/workflows/candidate-certification.yml
```

| Area | Canonical owner | Boundary |
|---|---|---|
| Bind integration template to exact env/domain/wheel hash | `evidence/candidate_certification.py` | template membership source-controlled; exact identity runtime-bound |
| Require fully certified IntegrationEvidenceManifest | `evidence/candidate_certification.py` | canonical validator with `require_certified=True` |
| Reject credential-like release proof text | `evidence/candidate_certification.py` + `evidence/safety.py` | certified artifact safe to retain/publish |
| Final zero-blocker readiness aggregation | `evidence/candidate_certification.py` -> `evidence/release_readiness.py` | all required readiness gates must PASS |
| Candidate/run/wheel/evidence provenance orchestration | `.github/workflows/candidate-certification.yml` | no Fabric execution, wheel build, or release mutation |
| Integration-evidence producer | future `.github/workflows/candidate-integration-evidence.yml` | approved exact-candidate live integration source; NOT YET IMPLEMENTED |

Merged PR #84 established candidate certification as CI-proven portable contract. The certification workflow accepts upstream evidence only from successful explicit exact-SHA producer runs and uploads `release-readiness-certified-<candidate SHA>` only after `release_ready=true`, blockers are empty, and every required gate PASS.

## Exact immutable release promotion

Canonical workflow:

```text
.github/workflows/release.yml
```

It is manual promotion only. It does not build wheel bytes. Before tag/release mutation it re-verifies candidate source/version/main-CI provenance, CANDIDATE.json + SHA256SUMS + exact wheel bytes, successful candidate-certification provenance, exact report/proof/integration identity, `release_ready=true`, blockers empty, all required readiness results PASS, and integration release_hash equal to exact wheel SHA.

Then and only then it tags the exact candidate SHA and publishes the already-certified wheel and evidence assets.

## Project initialization / validation / delivery

| Area | Canonical owner |
|---|---|
| Config bundle hashing/loading/materialization | `deployment/delivery.py` |
| Release manifest/provenance | deployment delivery modules |
| Customer/domain project scaffold | `deployment/project.py` |
| Whole-project static dry run/report | `deployment/project.py` |
| Per-dataset semantic validation | `capture/onboarding.py` |
| Capture/apply capability validation | `metadata/capabilities.py` |
| Project CLI adapters | `cli/project.py` |

Dependency rule:

```text
cli/project.py -> deployment/project.py

deployment/project.py
  -> fabric_data_framework.deployment.delivery
  -> capture/onboarding.py
  -> metadata/capabilities.py

reusable project logic -X-> cli
```

Project init never guesses keys/watermarks/delete/history semantics, overwrites existing files, creates Fabric resources, or persists secrets. Project validate is local/static and never upgrades portable validation to live proof.

## CLI presentation boundary

All CLI code lives under `src/fabric_data_framework/cli/`.

| File | Responsibility |
|---|---|
| `cli/main.py` | tiny composition root |
| `cli/project.py` | project init/validate presentation |
| `cli/release.py` | release-readiness + release-proofs-merge + candidate-certify presentation |
| `cli/base.py` | general validation/metadata/deployment/preflight |
| `cli/approved.py` | approved evidence-run adapters |

Non-negotiable direction:

```text
cli -> reusable core/evidence/deployment
core/evidence/deployment -X-> cli
```

## Extension registry

Known controlled entry points:

```text
fabric_data_framework.capture_observers
fabric_data_framework.spark_execution_data
fabric_data_framework.warehouse_mutations
fabric_data_framework.warehouse_commit_fault_injectors
```

Extensions may provide bounded provider behavior/evidence observations. They cannot redefine framework semantic truth or manufacture commit/evidence PASS.

## Next release implementation ownership

Preferred order:

```text
candidate-release-proofs workflow
  -> real candidate-business-path-evidence workflow
  -> candidate-integration-evidence workflow using approved live runners
  -> exact candidate freeze
  -> candidate-certification
  -> immutable release promotion
```

Do not collapse static and live proof into one fake producer. A workflow that merely writes PASS JSON without observing the corresponding real path is not acceptable evidence.

## Tests as executable specification

Release-critical tests must preserve:

```text
missing readiness evidence blocks
proof candidate/artifact identity matching
strict partial proof merge has no latest/PASS/FAIL precedence
integration-backed gates reject generic substitution
required OUT_OF_SCOPE blocks
candidate artifact rejects changed bytes/provenance/version
candidate release-proof producer only emits static PASS it re-verifies
candidate release-proof producer requires external live business-path evidence
candidate certification requires fully certified integration evidence
candidate certification rejects other-wheel evidence and credential-like proof text
release/certification workflows never rebuild certified wheel
machine docs cannot regress release-system state
```

## Documentation ownership

```text
docs/human/README.md                       human reading order
docs/human/CONCEPTS.md                     stable conceptual model
docs/human/REPOSITORY_GUIDE.md             repo/file map
docs/human/GETTING_STARTED.md              install/use
docs/human/CUSTOMER_PROJECT_BOOTSTRAP.md   domain repo bootstrap/dry run
docs/human/DATASET_ONBOARDING.md           new-data decision guide
docs/human/OPERATIONS.md                   operations/CLI
docs/human/RELEASE_CANDIDATE.md            release candidate operator flow

docs/machine/STATE.md                      exact current merged engineering state
docs/machine/CONTEXT.md                    durable invariants
docs/machine/APPROVED_EVIDENCE.md          approved real-run protocol
docs/machine/RELEASE_READINESS.md          exact release/certification contract
docs/machine/CAPABILITIES.md               guarantee/evidence matrix
docs/machine/IMPLEMENTATION_MAP.md         canonical code ownership
docs/machine/HISTORY.md                    compact merged milestones
```
