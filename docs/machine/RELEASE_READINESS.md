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

The business-path stage intentionally comes **after** certified integration evidence because its reruns reuse proven identity/control-plane/Pipeline prerequisites.

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

## Candidate artifact identity

Main CI retains:

```text
fabric_data_framework-<version>-py3-none-any.whl
SHA256SUMS
CANDIDATE.json
```

`CANDIDATE.json` binds source SHA, version, main workflow run ID/attempt, wheel filename and exact inner wheel SHA256. The candidate verifier authenticates those bytes before installation.

Latest merged candidate-capable baseline from PR #88:

```text
merge SHA         1632aefe8c1fd71098200c434a1648d0385f4967
PR CI             33346419772
main CI           33346470401
tests             717
wheel SHA256      9c813a2c23344c55409ac5f4f7e879d4515196987835bee6473d54ff3a1e027f
artifact ID       9742145456
selected/frozen   false
```

This artifact is candidate-capable only. It is neither selected/frozen nor live-certified.

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

## Strict partial release-proof merge

Canonical implementation:

```text
src/fabric_data_framework/evidence/release_readiness_merge.py
fabric-framework release-proofs-merge
```

Merged PR #86 established:

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
```

There is no latest/PASS/FAIL/timestamp precedence.

## Candidate integration evidence — next release blocker

Expected workflow:

```text
.github/workflows/candidate-integration-evidence.yml
```

It is **NOT YET IMPLEMENTED**.

Its retained manifest must be materialized from `release/0.4.0/integration-evidence-template.json` and bind:

```text
environment
domain
framework_version
release_hash = exact framework wheel SHA256
domain_release_hash = exact customer/domain ReleaseManifest.bundle.release_hash
```

It must use the existing approved runners for item read, control plane, Pipeline, Copy, Spark, Warehouse commit and real ambiguous-COMMIT evidence. A successful producer artifact may exist only when every required integration check has retained PASS evidence. Optional Debezium/Kafka remains outside required 0.4 scope unless promoted.

The integration template declares both runtime identity placeholders as null:

```json
{
  "release_hash": null,
  "domain_release_hash": null
}
```

Candidate certification materializes both at runtime.

## Explicit Pipeline rerun prerequisite — merged PR #88

Approved provider runners reject silent reruns when a selected check already has substantive evidence. Representative business paths deliberately rerun a Pipeline, so they must not mutate or overwrite the original certified integration manifest.

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

The projected prerequisite still requires retained PASS Fabric item and control-plane evidence before the business-path runner may execute.

## Candidate business-path evidence — merged PR #88

Workflow:

```text
.github/workflows/candidate-business-path-evidence.yml
```

Portable workflow/runner contract state: **MERGED + MAIN CI PROVEN**.

PR #88 provenance:

```text
merge SHA   1632aefe8c1fd71098200c434a1648d0385f4967
PR CI       33346419772
main CI     33346470401
tests       717
```

Trusted inputs include:

```text
candidate_run_id
candidate_git_sha
candidate_wheel_sha256
customer_git_sha
customer_inputs_run_id
integration_evidence_run_id
business_path_plan_path
```

It requires:

```text
successful exact main framework CI run
exact authenticated candidate wheel bytes
successful exact-SHA candidate-integration-evidence workflow run
successful exact customer-SHA candidate-business-path-inputs workflow run
fully certified integration manifest
exact customer ReleaseManifest
exact five-gate business-path plan
exact scenario and driver-config fingerprints
exact driver/observer extension wheel fingerprints
```

Before live execution it verifies:

```text
integration.release_hash == candidate wheel SHA256
integration.domain_release_hash == customer ReleaseManifest.bundle.release_hash
runner.framework_artifact_sha256 == candidate wheel SHA256
runner.release_hash == customer ReleaseManifest.bundle.release_hash
customer ReleaseManifest.domain_git_sha == exact customer SHA
```

The workflow invokes the approved framework runner for exactly:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

The workflow contains no direct construction of business-gate PASS proof. PASS belongs only to the framework evaluator after provider/outcome/state facts satisfy the contract. Exactly five one-gate proof bundles are strict-merged; upload occurs only when membership is exact and every gate is PASS.

There is **no successful live business-path run retained yet**. Merged/green workflow code is not Fabric proof.

Detailed gate semantics are canonical in `docs/machine/BUSINESS_PATH_EVIDENCE.md`.

## Candidate release-proof producer — merged PR #87

Workflow:

```text
.github/workflows/candidate-release-proofs.yml
```

State: **MERGED + MAIN CI PROVEN**.

It directly creates PASS only for facts it re-verifies itself:

```text
source.tests
wheel.integrity
customer.compatibility
```

It requires a successful exact-candidate business-path workflow run for the five live gates, downloads the retained live partial bundle, then strict-merges static + live evidence. It refuses `release-proofs-<candidate SHA>` unless exactly all eight non-integration gates are present and PASS.

It never executes Fabric, rebuilds the candidate wheel, creates a tag, or publishes a release.

## Candidate certification

Canonical owners:

```text
src/fabric_data_framework/evidence/candidate_certification.py
fabric-framework candidate-certify
.github/workflows/candidate-certification.yml
```

Candidate certification is merged/CI-proven as a portable aggregation contract. It accepts only exact successful producer runs, re-authenticates candidate bytes, validates proof safety and identity, requires fully certified integration evidence, runs final readiness aggregation, and uploads a certified artifact only when:

```text
release_ready = true
blockers = []
every required readiness gate = PASS
```

PR #88 made `domain_release_hash` an independent stable identity while preserving `release_hash` as the framework wheel SHA256.

Certification does not execute Fabric or build/tag/release.

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
candidate-business-path-evidence   MERGED + MAIN CI PROVEN contract (#88); no live run
candidate-integration-evidence     NOT YET IMPLEMENTED
customer business-path inputs      NOT YET IMPLEMENTED / NOT RETAINED
certified readiness artifact       NOT YET PRODUCED
```

## Next order

```text
1. implement candidate-integration-evidence producer
2. implement exact fabric-customer business-path input producer and bounded live extensions
3. validate both producer contracts without fabricating PASS
4. only then select/freeze one exact candidate
5. produce certified integration evidence for exact wheel + exact domain release
6. execute five representative live business-path gates
7. run merged candidate-release-proofs
8. candidate-certify must reach blockers=[]
9. exact-byte release promotion
10. only then immutable v0.4.0 exists
```
