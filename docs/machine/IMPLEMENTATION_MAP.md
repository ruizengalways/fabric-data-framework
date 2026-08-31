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

| Area | Canonical owner | Boundary |
|---|---|---|
| Integration spec/result/manifest/hash | `evidence/integration_evidence.py` | exact framework wheel + exact domain release identities |
| Approved-run planning | `evidence/integration_runner.py` | physical bindings/env presence/authorization; never retains secret value |
| Runtime/provider result projection | `evidence/integration_checks.py` | projection only; no semantic redefinition |
| Strict staged merge | `evidence/integration_evidence_merge.py` | no latest/PASS precedence; both identities must match |
| Explicit Pipeline rerun prerequisite | `evidence/integration_evidence_rerun.py` | fully certified source -> new selected-check NOT_RUN projection |
| Control-plane runner | `evidence/approved_control_plane_runner.py` | real selected production-eligible backend |
| Pipeline runner | `evidence/approved_pipeline_runner.py` | native provider run + exact durable child outcome |
| Copy/Spark runner | `evidence/approved_capture_runner.py` | provider evidence + verified CaptureReceipt |
| Warehouse runner | `evidence/approved_warehouse_runner.py` | target mutation + marker |
| Ambiguous-COMMIT runner | `evidence/approved_warehouse_fault_runner.py` | real execution exception/fault/recovery evidence |
| Retained secret scan | `evidence/safety.py` | fail closed before evidence retention |

Exact integration identity invariant:

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

They must never be assumed equal.

## Business-path evidence ownership

| Area | Canonical owner | Boundary |
|---|---|---|
| Five live gate enum/scenario/observation/evaluator | `evidence/business_path_evidence.py` | evaluator is sole readiness PASS authority |
| Mutating driver recipe/request/receipt | `evidence/business_path_driver.py` | receipt has no PASS/status |
| Exact five-gate certification plan | `evidence/business_path_plan.py` | exactly five gates; safe project-root-contained paths |
| Approved execution orchestration | `evidence/approved_business_path_runner.py` | preflight/driver/observer/Pipeline/evaluator/cleanup separation |
| Exact domain-bound proof packaging | `evidence/business_path_release_proof.py` | binds evaluated result to Customer ReleaseManifest.bundle.release_hash; no PASS authority |
| Explicit rerun source | `evidence/integration_evidence_rerun.py` | source must be fully certified integration evidence |
| CLI leaf | `cli/business_path.py` | loads exact files and delegates; no proof semantics |
| Candidate producer | `.github/workflows/candidate-business-path-evidence.yml` | executes live paths; cannot author PASS JSON directly |

PR #88 regression provenance:

```text
merge SHA   1632aefe8c1fd71098200c434a1648d0385f4967
PR CI       33346419772
main CI     33346470401
tests       717
```

The retained business-path artifact includes `business-path-release-proofs.json`, `customer-release-manifest.json`, certified integration evidence and per-gate reports/receipts. Retaining the Customer ReleaseManifest is intentional: the later release-proof producer authenticates this exact domain identity.

## Readiness / release proof ownership

| Area | Canonical owner | Boundary |
|---|---|---|
| Readiness spec/proof/result/report | `evidence/release_readiness.py` | exact framework candidate/wheel + candidate domain identity; no provider execution |
| Strict non-integration partial proof merge | `evidence/release_readiness_merge.py` | candidate bundles require identical non-empty domain_release_hash; contradictions conflict |
| Business-path domain proof binding | `evidence/business_path_release_proof.py` | binds evaluated proof to exact domain release hash |
| Candidate certification aggregation | `evidence/candidate_certification.py` | proof + integration domain hash must both exist and match |
| `release-readiness` / `release-proofs-merge` / `candidate-certify` | `cli/release.py` | presentation only |
| Source-controlled 0.4 policy | `release/0.4.0/readiness-spec.json` | 15 required gates; Debezium optional |
| Ordinary blocked report | `.github/workflows/ci.yml` | deliberately retains missing-evidence state |

Final candidate identity chain:

```text
framework version
+ exact framework candidate source SHA
+ exact framework inner wheel SHA256
+ exact customer/domain ReleaseManifest.bundle.release_hash
+ complete ReleaseReadinessProofBundle carrying the same domain hash
+ certified IntegrationEvidenceManifest carrying the same domain hash
-> ReleaseReadinessReport carrying the same domain hash
```

Ordinary CI may omit `domain_release_hash`; exact candidate proof merge/certification may not.

## Exact domain identity hardening — merged PR #92

Provenance:

```text
merge SHA     d5eed17f2ec2f869b4e3a448597e6d8d600568ea
final PR CI   33356959856
main CI       33357032461
tests         734
state         MERGED + MAIN CI PROVEN
live proof    none
```

Owners changed by PR #92:

```text
src/fabric_data_framework/evidence/release_readiness.py
src/fabric_data_framework/evidence/release_readiness_merge.py
src/fabric_data_framework/evidence/business_path_release_proof.py
src/fabric_data_framework/evidence/candidate_certification.py
src/fabric_data_framework/cli/business_path.py
.github/workflows/candidate-release-proofs.yml
.github/workflows/release.yml
```

Fail-closed rule:

```text
candidate-release-proofs cannot take domain_release_hash as dispatch input
-> authenticate business-path run + customer-release-manifest.json
-> exact customer SHA/framework version/candidate SHA/wheel SHA/domain hash must agree
-> create static proof with authenticated domain hash
-> strict merge requires same domain hash in all partial proof bundles
-> candidate-certify requires proof.domain_release_hash == integration.domain_release_hash
-> release workflow requires report == proofs == integration domain_release_hash before tag
```

## Candidate artifact / producer ownership

### Main candidate artifact

Owners:

```text
src/fabric_data_framework/deployment/candidate_artifact.py
.github/workflows/ci.yml
```

Latest candidate-capable main artifact:

```text
source SHA         d5eed17f2ec2f869b4e3a448597e6d8d600568ea
main CI            33357032461
wheel SHA256       5aa82d6befa3d5abe5d212d875721e6ae9e3e4bc4d67fd5b4cdd1a32d9e16701
artifact ID        9745451533
selected/frozen    false
```

### Candidate release-proof producer

Owner:

```text
.github/workflows/candidate-release-proofs.yml
```

Original merged baseline PR #87:

```text
merge SHA 5a2edffe5930e9b8a2a79f66f4580ca4d9df2b4e
main CI   33343223496
```

Direct PASS scope remains exactly `source.tests`, `wheel.integrity`, `customer.compatibility`. The five live business gates arrive from `candidate-business-path-evidence.yml`. PR #92 adds exact retained Customer ReleaseManifest authentication before static proof creation.

### Candidate business-path producer

```text
.github/workflows/candidate-business-path-evidence.yml
```

Merged + main-CI proven PR #88; **no retained live business-path PASS artifact exists**.

### Candidate integration producer

```text
.github/workflows/candidate-integration-evidence.yml
```

Merged + main-CI proven PR #90:

```text
merge SHA   7e12a320e73aa06f3e80f57e3deed14a6cc7add0
final PR CI 33349005817
main CI     33349064335
tests       728
```

No retained live integration artifact exists.

### Customer input producer

External owner:

```text
fabric-customer/.github/workflows/candidate-business-path-inputs.yml
```

Contract is merged + Customer main-CI proven:

```text
PR #10 merge                 cda90f1c02fc9606aa64d2d1bd13f2ab89628aab
PR #11 checkpoint            31f3f506bc1c16a445652de2ad48fe512cfec10a
customer main CI             33353960915
customer certification CI    33353960906
production runtime pin       fabric-data-framework==0.3.0
```

No selected-candidate input artifact has been retained yet.

## Candidate certification

Owners:

```text
src/fabric_data_framework/evidence/candidate_certification.py
cli/release.py -> candidate-certify
.github/workflows/candidate-certification.yml
```

Certification performs aggregation only. It never executes Fabric, rebuilds wheel bytes, tags or releases. Exact candidate certification requires complete non-integration proof and fully certified integration evidence for the same framework candidate **and same domain release hash**.

## Exact immutable promotion

Owner:

```text
.github/workflows/release.yml
```

Release is manual exact-byte promotion. Before tag creation it re-verifies candidate source/run/wheel and certified evidence, including:

```text
release-readiness.json.domain_release_hash
== release-proofs.json.domain_release_hash
== integration-evidence.json.domain_release_hash
```

No release-time wheel rebuild exists.

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

## Next release implementation order

```text
finish merged-main documentation checkpoint
-> replace customer real-environment placeholders with reviewed enterprise evidence/fault binding
-> explicitly select/freeze one NEW exact framework main candidate
-> produce exact customer certification input artifact for that candidate
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
