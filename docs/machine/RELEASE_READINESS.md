# MACHINE RELEASE READINESS CONTRACT

```yaml
schema: fabric-data-framework-release-readiness-v1
framework_version: 0.4.0-development-unreleased
public_release: v0.3.0
release_allowed: false
readiness_spec: release/0.4.0/readiness-spec.json
integration_template: release/0.4.0/integration-evidence-template.json
readiness_implementation: src/fabric_data_framework/evidence/release_readiness.py
proof_merge_implementation: src/fabric_data_framework/evidence/release_readiness_merge.py
integration_rerun_implementation: src/fabric_data_framework/evidence/integration_evidence_rerun.py
business_path_implementation: src/fabric_data_framework/evidence/approved_business_path_runner.py
candidate_artifact_contract: src/fabric_data_framework/deployment/candidate_artifact.py
candidate_integration_workflow: .github/workflows/candidate-integration-evidence.yml
candidate_business_path_workflow: .github/workflows/candidate-business-path-evidence.yml
candidate_release_proofs_workflow: .github/workflows/candidate-release-proofs.yml
candidate_certification_workflow: .github/workflows/candidate-certification.yml
release_promotion_workflow: .github/workflows/release.yml
```

## Purpose

The release system separates independent truth sources. No stage may invent PASS to satisfy a later stage.

Correct 0.4 candidate order:

```text
main CI creates exact candidate wheel
        ↓
exact customer/domain release inputs exist
        ↓
candidate-integration-evidence produces fully certified exact live integration manifest
        ↓
candidate-business-path-evidence performs explicit representative Pipeline reruns
        ↓
candidate-release-proofs re-verifies static/customer facts and strict-merges five live path proofs
        ↓
candidate-certification combines complete release proofs + the same certified integration evidence
        ↓
framework-release promotes the exact already-certified bytes
```

The business-path stage intentionally comes **after** certified integration evidence because its reruns reuse already-proven Fabric identity, control-plane and Pipeline prerequisites.

## Exact identities

Three identities must remain distinct:

```text
candidate_git_sha
  exact 40-character framework source commit

framework_artifact_sha256
  exact inner candidate wheel SHA256
  = ReleaseReadinessProofBundle.artifact_sha256
  = IntegrationEvidence.release_hash

customer_domain_release_hash
  exact ReleaseManifest.bundle.release_hash
  = IntegrationEvidence.domain_release_hash
```

In exact-candidate approved runner config:

```text
ApprovedIntegrationRunnerConfig.framework_artifact_sha256
  = framework_artifact_sha256

ApprovedIntegrationRunnerConfig.release_hash
  = customer_domain_release_hash
```

These SHA256 values are independent. GitHub artifact ZIP digest is transport metadata only and cannot substitute for either.

## Latest merged candidate-capable artifact

PR #90 is the current merged-main baseline:

```text
merge SHA         7e12a320e73aa06f3e80f57e3deed14a6cc7add0
final PR CI       33349005817
main CI           33349064335
tests             728
wheel SHA256      dbc9b0cbcc73598c94ae67c4798ba9eefdf6ba203a6169ff61088a9d1757c3b8
artifact ID       9742969993
selected/frozen   false
```

Main CI retains the exact wheel, `SHA256SUMS`, and `CANDIDATE.json`. The artifact is candidate-capable only; it is neither selected/frozen nor live-certified.

## Readiness evidence ownership

`ReleaseReadinessProofBundle` owns non-integration gates:

```text
source.tests
wheel.integrity
customer.compatibility
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

`IntegrationEvidenceManifest` backs integration gates:

```text
fabric.identity
control.certification
fabric.pipeline
fabric.copy
fabric.spark
warehouse.commit
warehouse.ambiguous_commit
optional external.cdc.debezium
```

Generic release proof cannot satisfy an integration-backed gate.

## Strict partial release-proof merge — merged PR #86

Canonical implementation:

```text
src/fabric_data_framework/evidence/release_readiness_merge.py
fabric-framework release-proofs-merge
```

Rules:

```text
exact schema/version/candidate/wheel identity required
omitted or NOT_RUN = no proof
one substantive result retained unchanged
model-identical duplicate substantive result allowed
different substantive result = conflict
two different PASS records = conflict
unknown gate/kind drift = reject
integration-backed gate injection = reject
credential-like retained text = reject
no latest/PASS/FAIL/timestamp precedence
```

## Candidate integration evidence — merged PR #90

Workflow:

```text
.github/workflows/candidate-integration-evidence.yml
```

State: **MERGED + MAIN CI PROVEN** as a portable workflow contract. Final PR CI `33349005817` and main CI `33349064335` succeeded with 728 tests. There is no retained live Fabric integration artifact yet.

The workflow is manual exact-candidate orchestration. It authenticates the framework candidate source/main run/wheel bytes and exact customer SHA/input-producer run before executing any provider mutation. It materializes `release/0.4.0/integration-evidence-template.json` with:

```text
environment
domain
framework_version
release_hash = exact framework wheel SHA256
domain_release_hash = exact customer/domain ReleaseManifest.bundle.release_hash
```

It then reuses only existing approved commands for:

```text
fabric.item.read           -> integration-item-smoke-run
control.cert               -> integration-control-plane-certify-run
fabric.pipeline            -> integration-pipeline-run
fabric.copy                -> integration-capture-run
fabric.spark               -> integration-capture-run
warehouse.commit           -> integration-warehouse-run
warehouse.ambiguous_commit -> integration-warehouse-fault-drill-run
```

Partial manifests are strict-merged. Final publication requires:

```text
integration-evidence-merge --require-certified
integration-evidence-validate --require-certified
```

The workflow does not construct integration PASS results. Reading an approved runner's finished PASS result is allowed only for final validation.

The exact customer input artifact must own:

```text
ReleaseManifest
DatasetConfig bundle
ApprovedIntegrationRunnerConfig
fabric.pipeline binding with customer-selected dataset_id
Copy run recipe
Spark run recipe
Warehouse run recipe
Warehouse ambiguous-COMMIT recipe
control-plane external evidence references
fingerprinted customer extension wheels
```

`IntegrationCheckPhysicalBinding.dataset_id` is optional generally but required by the candidate integration producer for the representative `fabric.pipeline` binding. This keeps business dataset selection in the customer/domain repository rather than framework workflow inputs.

Mutation authorization remains layered:

```text
authorize_live_mutations=true
  required for mutating certification stages

authorize_warehouse_session_termination=true
  separate Admin/KILL authorization; never implied by general mutation permission
```

Optional Debezium/Kafka remains outside required 0.4 scope unless promoted.

## Explicit Pipeline rerun prerequisite — merged PR #88

Representative business paths deliberately rerun a Pipeline but must not mutate or overwrite the original certified integration manifest.

Canonical projection:

```text
src/fabric_data_framework/evidence/integration_evidence_rerun.py
```

Input:

```text
fully certified exact IntegrationEvidenceManifest
```

Output:

```text
new manifest with identical exact identities and all other retained results
selected FABRIC_PIPELINE_RUN PASS -> explicit NOT_RUN
new evidence_id / manifest_hash
source certified manifest remains unchanged
result is intentionally no longer certified
```

## Candidate business-path evidence — merged PR #88

Workflow:

```text
.github/workflows/candidate-business-path-evidence.yml
```

State: **MERGED + MAIN CI PROVEN** as a portable contract, with no live retained run.

It authenticates exact framework candidate/run/wheel, exact customer SHA/input-producer run, exact certified integration producer run, exact domain release, exact five-gate plan/scenario/driver/plugin bytes, then invokes the approved framework runner for exactly:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

The workflow cannot directly construct business-gate PASS. PASS belongs only to the framework evaluator after provider/outcome/state facts satisfy the contract.

## Candidate release-proof producer — merged PR #87

Workflow:

```text
.github/workflows/candidate-release-proofs.yml
```

It directly creates PASS only for facts it re-verifies itself:

```text
source.tests
wheel.integrity
customer.compatibility
```

It requires a successful exact-candidate business-path artifact for the five live gates and strict-merges static + live proof. It never executes Fabric, rebuilds the candidate wheel, creates a tag, or publishes a release.

## Candidate certification

Canonical owners:

```text
src/fabric_data_framework/evidence/candidate_certification.py
fabric-framework candidate-certify
.github/workflows/candidate-certification.yml
```

Candidate certification is aggregation only. It re-authenticates exact candidate bytes, validates proof safety/identity, requires fully certified integration evidence, and accepts only when:

```text
release_ready = true
blockers = []
every required readiness gate = PASS
```

Certification does not execute Fabric or build/tag/release.

## Remaining domain identity hardening before freeze

The current `ReleaseReadinessProofBundle` machine identity binds framework version, candidate source SHA and exact wheel SHA256. The certified integration manifest separately carries `domain_release_hash`.

Before selecting/freezing a 0.4 candidate, the final release-proof/certification path must machine-bind the same exact customer/domain release identity. A complete non-integration proof bundle must not be pairable with integration evidence from a different domain release merely because retained references appear compatible.

This is a required release blocker, not a new product feature.

## Required readiness matrix

Required:

```text
source.tests
wheel.integrity
customer.compatibility
fabric.identity
control.certification
fabric.pipeline
fabric.copy
fabric.spark
warehouse.commit
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
warehouse.ambiguous_commit
```

Optional unless scope changes:

```text
external.cdc.debezium
```

Ordinary framework CI intentionally has no retained candidate proofs/live integration manifest, so it remains:

```text
release_ready = false
required blockers = 15
```

A green ordinary readiness job proves fail-closed behavior, not release readiness.

## Immutable promotion

`.github/workflows/release.yml` is manual exact-byte promotion. It re-verifies candidate source/run/wheel and certified readiness evidence before tagging the exact candidate SHA and publishing those same wheel bytes/evidence assets. No release-time rebuild exists.

## Current truth

```text
public release                     v0.3.0
0.4.0                              UNRELEASED / FEATURE FROZEN
release_allowed                    false
candidate                          NOT YET FROZEN
ordinary readiness blockers        15
strict partial proof merge         MERGED + MAIN CI PROVEN (#86)
candidate-release-proofs           MERGED + MAIN CI PROVEN (#87)
candidate-business-path-evidence   MERGED + MAIN CI PROVEN (#88); no live run
candidate-integration-evidence     MERGED + MAIN CI PROVEN (#90); no live run
customer business-path inputs      NOT YET IMPLEMENTED / NOT RETAINED
release-proof/domain hash binding  REQUIRED BEFORE CANDIDATE FREEZE
certified readiness artifact       NOT YET PRODUCED
```

## Next order

```text
1. implement exact fabric-customer business-path/integration input producer and bounded live extensions
2. hard-bind domain_release_hash across final release proof/candidate certification
3. validate both contracts fail closed
4. only then select/freeze one exact candidate
5. produce certified integration evidence for exact wheel + exact domain release
6. execute five representative live business-path gates
7. run candidate-release-proofs
8. candidate-certify must reach blockers=[]
9. exact-byte release promotion
10. only then immutable v0.4.0 exists
```
