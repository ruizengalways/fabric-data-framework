# MACHINE RELEASE READINESS CONTRACT

```yaml
schema: fabric-data-framework-release-readiness-v1
framework_version: 0.4.0-development-unreleased
public_release: v0.3.0
release_allowed: false
feature_freeze: true
candidate_status: not_frozen
readiness_spec: release/0.4.0/readiness-spec.json
integration_template: release/0.4.0/integration-evidence-template.json
readiness_implementation: src/fabric_data_framework/evidence/release_readiness.py
proof_merge_implementation: src/fabric_data_framework/evidence/release_readiness_merge.py
business_path_release_proof: src/fabric_data_framework/evidence/business_path_release_proof.py
candidate_certification: src/fabric_data_framework/evidence/candidate_certification.py
candidate_integration_workflow: .github/workflows/candidate-integration-evidence.yml
candidate_business_path_workflow: .github/workflows/candidate-business-path-evidence.yml
candidate_release_proofs_workflow: .github/workflows/candidate-release-proofs.yml
candidate_certification_workflow: .github/workflows/candidate-certification.yml
release_promotion_workflow: .github/workflows/release.yml
```

## Purpose and required order

No stage may invent PASS to satisfy a later stage.

```text
main CI builds exact framework candidate wheel
        ↓
customer repo produces exact domain certification inputs
        ↓
candidate-integration-evidence produces fully certified live integration evidence
        ↓
candidate-business-path-evidence executes five representative live Pipeline paths
        ↓
candidate-release-proofs re-verifies static/customer facts and strict-merges live path proof
        ↓
candidate-certification requires all exact identities + all required PASS
        ↓
framework-release re-verifies the same identities and promotes the exact certified bytes
```

There is no release-time wheel rebuild.

## Exact machine identities

```text
candidate_git_sha
  = exact framework source commit

framework_artifact_sha256
  = exact inner framework wheel SHA256
  = ReleaseReadinessProofBundle.artifact_sha256
  = ReleaseReadinessReport.artifact_sha256
  = IntegrationEvidence.release_hash

customer_domain_release_hash
  = exact ReleaseManifest.bundle.release_hash
  = ReleaseReadinessProofBundle.domain_release_hash
  = ReleaseReadinessReport.domain_release_hash
  = IntegrationEvidence.domain_release_hash
```

Framework wheel SHA256 and customer/domain release SHA256 are independent and must never be assumed equal. GitHub artifact archive digests are transport metadata only.

`ApprovedIntegrationRunnerConfig.framework_artifact_sha256` binds the framework wheel. `ApprovedIntegrationRunnerConfig.release_hash` binds the customer/domain release.

## Gate ownership

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

`IntegrationEvidenceManifest` owns integration-backed gates:

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

Generic proof cannot satisfy an integration-backed gate.

## Strict partial proof merge

Canonical owner:

```text
src/fabric_data_framework/evidence/release_readiness_merge.py
fabric-framework release-proofs-merge
```

Baseline PR #86: merge `0f70e037806482c677fccae0ce9432504f2a9885`, main CI `33342806854`.

Exact candidate rules:

```text
exact readiness schema/framework/candidate/wheel identity required
non-empty domain_release_hash required on every candidate partial bundle
all partial bundles must carry the same domain_release_hash
omitted or NOT_RUN = absence of proof
one substantive result retained unchanged
model-identical duplicate substantive result allowed
different substantive result = conflict
unknown gate/kind drift = reject
integration-backed gate injection = reject
credential-like retained text = reject
no latest/PASS/FAIL/timestamp precedence
```

Ordinary non-candidate readiness may omit domain identity; exact candidate partial-proof merge may not.

## Business-path proof packaging boundary

PR #92 established exact domain binding:

```text
merge SHA      d5eed17f2ec2f869b4e3a448597e6d8d600568ea
final PR CI    33356959856
main CI        33357032461
tests          734
```

Canonical packaging owner:

```text
src/fabric_data_framework/evidence/business_path_release_proof.py
```

It accepts an already-evaluated `ApprovedBusinessPathExecutionReport` plus the exact customer `ReleaseManifest`, verifies domain/framework agreement, and constructs the candidate partial bundle with:

```text
domain_release_hash = ReleaseManifest.bundle.release_hash
```

It does not decide PASS/FAIL.

PR #94 removes the obsolete runner-level unbound proof path:

```text
merge SHA      abc8b3a2b80b3f6babf88fdc2347a3bfe69be356
final PR CI    33357795244
main CI        33357846835
tests          738
```

`approved_business_path_runner.py` now returns only evaluated execution evidence. It no longer exposes `partial_proof_bundle` or `write_business_path_partial_proof_bundle`.

Exact-wheel scan of the PR #94 main artifact found only two `ReleaseReadinessProofBundle` construction owners:

```text
business_path_release_proof.py
  binds exact ReleaseManifest.bundle.release_hash

release_readiness_merge.py
  rejects any candidate partial bundle with missing domain_release_hash
  requires every bundle to carry the same domain_release_hash
```

Thus there is no known framework API path that can package candidate business-path proof without exact domain identity.

## Candidate release-proof producer

Workflow:

```text
.github/workflows/candidate-release-proofs.yml
```

Original producer baseline PR #87: merge `5a2edffe5930e9b8a2a79f66f4580ca4d9df2b4e`, main CI `33343223496`.

It directly creates PASS only for facts it re-verifies:

```text
source.tests
wheel.integrity
customer.compatibility
```

The five live business gates arrive from the separately retained business-path artifact. The workflow does not accept `domain_release_hash` as dispatch input. It authenticates `customer-release-manifest.json`, exact customer SHA/framework version/candidate SHA/wheel SHA, five PASS business gates, and requires the retained business-path proof hash to equal `ReleaseManifest.bundle.release_hash`. Only then is the same hash injected into the static partial bundle and strict-merged.

## Candidate integration evidence

Workflow:

```text
.github/workflows/candidate-integration-evidence.yml
```

PR #90 baseline:

```text
merge SHA       7e12a320e73aa06f3e80f57e3deed14a6cc7add0
final PR CI     33349005817
main CI         33349064335
tests           728
```

The portable workflow contract is merged + main-CI proven, but no live Fabric integration artifact has been retained. `IntegrationCheckPhysicalBinding.dataset_id` remains customer-owned. `authorize_live_mutations` and `authorize_warehouse_session_termination` remain separate authorizations. Publication requires:

```text
integration-evidence-merge --require-certified
integration-evidence-validate --require-certified
```

## Candidate business-path evidence

Workflow:

```text
.github/workflows/candidate-business-path-evidence.yml
```

PR #88 baseline: source `1632aefe8c1fd71098200c434a1648d0385f4967`, main CI `33346470401`, 717 tests.

It executes exactly:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

The customer release owns deterministic scenarios, fixture/fault driver, read-only observer, DatasetConfig values and fingerprinted extension bytes. The framework evaluator alone decides PASS/FAIL. Cleanup failure prevents proof publication. The retained artifact also carries `customer-release-manifest.json` so later aggregation can independently re-authenticate the same domain release.

## Customer certification inputs

Customer owner:

```text
fabric-customer/.github/workflows/candidate-business-path-inputs.yml
```

Contract provenance:

```text
feature PR #10 merge  cda90f1c02fc9606aa64d2d1bd13f2ab89628aab
checkpoint PR #11     31f3f506bc1c16a445652de2ad48fe512cfec10a
customer main CI      33353960915 SUCCESS
cert contract CI      33353960906 SUCCESS
released runtime pin  fabric-data-framework==0.3.0
```

No selected-candidate customer input artifact has been retained. Real-environment blockers remain intentionally fail-closed.

## Candidate certification and promotion

`fabric-framework candidate-certify` is aggregation only. It requires non-empty proof/integration `domain_release_hash` values and exact equality. The resulting `ReleaseReadinessReport.domain_release_hash` must match.

Before tag creation, `.github/workflows/release.yml` requires:

```text
release-readiness.json.domain_release_hash
  == release-proofs.json.domain_release_hash
  == integration-evidence.json.domain_release_hash
```

Promotion also re-verifies candidate source/version/run/wheel and uses the exact already-certified wheel bytes.

## Current candidate-capable main artifact

Latest main baseline after PR #94:

```text
source SHA       abc8b3a2b80b3f6babf88fdc2347a3bfe69be356
final PR CI      33357795244
main CI          33357846835
wheel SHA256     d763cd4410a69ff6a83c492f3a546d096502c96c87eeddb37c2ae9404557e7b7
artifact ID      9745697101
archive digest   sha256:c4a729c7da97185d27ff4b3cb50b48a106715fd6a4d2ef850e18fc6966ccf4ae
selected/frozen  false
```

This wheel is candidate-capable only. It is not selected/frozen, live-certified, or release-proven.

## Current truth

```text
public release                     v0.3.0
0.4.0                              UNRELEASED / FEATURE FROZEN
release_allowed                    false
candidate                          NOT YET FROZEN
ordinary readiness blockers        15
strict partial proof merge         MERGED + MAIN CI PROVEN (#86/#92 domain identity)
candidate-release-proofs           MERGED + MAIN CI PROVEN (#87/#92 hardening)
candidate-business-path-evidence   MERGED + MAIN CI PROVEN (#88); no live run
candidate-integration-evidence     MERGED + MAIN CI PROVEN (#90); no live run
customer input producer contract   MERGED + CUSTOMER MAIN CI PROVEN (#10/#11)
release-proof/domain binding       MERGED + MAIN CI PROVEN (#92)
unbound business-proof cleanup     MERGED + MAIN CI PROVEN (#94)
selected-candidate input artifact  NOT YET RETAINED
certified integration evidence     NOT YET PRODUCED
five live business-path proofs     NOT YET RETAINED
certified readiness artifact       NOT YET PRODUCED
immutable v0.4.0                    NOT YET PUBLISHED
```

Ordinary CI intentionally remains `release_ready=false` with 15 blockers. Green ordinary readiness proves fail-closed behavior, not release readiness.

## Next order

```text
1. finish PR #94 merged-main documentation checkpoint
2. replace customer real-environment placeholders only with reviewed enterprise evidence/fault infrastructure
3. only then explicitly select/freeze one NEW exact framework main candidate
4. produce exact customer certification input artifact for that candidate
5. run candidate-integration-evidence in the protected real environment
6. run all five candidate-business-path-evidence gates
7. run candidate-release-proofs for the same framework + domain identities
8. candidate-certify must reach blockers=[]
9. framework-release promotes exact certified wheel bytes
10. only after immutable v0.4.0 exists migrate customer production runtime from v0.3.0
```
