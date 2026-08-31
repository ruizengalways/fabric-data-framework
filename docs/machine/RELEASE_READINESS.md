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
business_path_release_proof: src/fabric_data_framework/evidence/business_path_release_proof.py
candidate_certification: src/fabric_data_framework/evidence/candidate_certification.py
candidate_integration_workflow: .github/workflows/candidate-integration-evidence.yml
candidate_business_path_workflow: .github/workflows/candidate-business-path-evidence.yml
candidate_release_proofs_workflow: .github/workflows/candidate-release-proofs.yml
candidate_certification_workflow: .github/workflows/candidate-certification.yml
release_promotion_workflow: .github/workflows/release.yml
```

## Purpose

The release system separates independent truth sources. No stage may invent PASS to satisfy a later stage.

Correct 0.4 order:

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

No release-time wheel rebuild exists.

## Exact release identities

The release chain binds three independent identities:

```text
candidate_git_sha
  exact 40-character framework source commit

framework_artifact_sha256
  exact inner framework wheel SHA256
  = ReleaseReadinessProofBundle.artifact_sha256
  = ReleaseReadinessReport.artifact_sha256
  = IntegrationEvidence.release_hash

customer_domain_release_hash
  exact customer ReleaseManifest.bundle.release_hash
  = ReleaseReadinessProofBundle.domain_release_hash
  = ReleaseReadinessReport.domain_release_hash
  = IntegrationEvidence.domain_release_hash
```

The framework wheel SHA256 and customer/domain release SHA256 are **not expected to be equal** and must never be assumed equal. GitHub artifact archive digests are transport metadata only.

Exact candidate approved runner config keeps the same split:

```text
ApprovedIntegrationRunnerConfig.framework_artifact_sha256
  = exact framework candidate wheel SHA256

ApprovedIntegrationRunnerConfig.release_hash
  = exact customer/domain ReleaseManifest.bundle.release_hash
```

## Readiness gate ownership

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

Generic release proof cannot satisfy an integration-backed gate.

## Strict partial proof merge — merged PR #86

Canonical implementation:

```text
src/fabric_data_framework/evidence/release_readiness_merge.py
fabric-framework release-proofs-merge
```

Merged-main proof retained for regression context:

```text
merge SHA: 0f70e037806482c677fccae0ce9432504f2a9885
main CI:   33342806854
```

Rules:

```text
exact schema/framework/candidate/wheel identity required
candidate partial bundles require a non-empty domain_release_hash
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

## Candidate release-proof producer — merged PR #87 plus PR #92 hardening

Original producer merged-main proof retained for regression context:

```text
merge SHA: 5a2edffe5930e9b8a2a79f66f4580ca4d9df2b4e
main CI:   33343223496
```

Workflow:

```text
.github/workflows/candidate-release-proofs.yml
```

It directly creates PASS only for facts it re-verifies:

```text
source.tests
wheel.integrity
customer.compatibility
```

It never creates business-path PASS. The five live gates come from the separately retained exact-candidate business-path artifact and are strict-merged.

PR #92 hardens this producer so the static proof cannot choose or accept a `domain_release_hash` workflow input. It must first authenticate:

```text
business-path producer run provenance
retained/business-path-release-proofs.json
retained/customer-release-manifest.json
customer ReleaseManifest.bundle.domain_git_sha == exact customer SHA
business-path proof candidate SHA == exact framework candidate SHA
business-path proof artifact_sha256 == exact framework wheel SHA256
business-path proof domain_release_hash == customer ReleaseManifest.bundle.release_hash
all five business-path gates present and PASS
```

Only then is the authenticated customer/domain release hash copied into the static proof bundle. Final strict merge must preserve that same hash.

PR #92 first implementation CI proof:

```text
PR:             #92
implementation head: f07c464fefaec2f1533a67549382549613823253
framework-ci:   33356673686
Python 3.11:    SUCCESS
Python 3.13:    SUCCESS
wheel build:    SUCCESS
readiness:      SUCCESS / intentionally blocked
Python 3.13:    732 passed
status:         PR CI PROVEN / PENDING MERGE
```

This is source/contract CI proof, not live Fabric evidence and not a frozen candidate.

## Candidate integration evidence — merged PR #90

Workflow:

```text
.github/workflows/candidate-integration-evidence.yml
```

Merged-main baseline:

```text
merge SHA:       7e12a320e73aa06f3e80f57e3deed14a6cc7add0
final PR CI:     33349005817
main CI:         33349064335
tests:           728
wheel SHA256:    dbc9b0cbcc73598c94ae67c4798ba9eefdf6ba203a6169ff61088a9d1757c3b8
selected/frozen: false
```

State: **MERGED + MAIN CI PROVEN** as a portable fail-closed producer contract. No live Fabric integration artifact has been retained.

The workflow materializes integration evidence with both independent hashes and reuses only approved provider/control/Warehouse commands. Final publication requires:

```text
integration-evidence-merge --require-certified
integration-evidence-validate --require-certified
```

`IntegrationCheckPhysicalBinding.dataset_id` remains customer-owned for the representative Pipeline binding. `authorize_live_mutations` and `authorize_warehouse_session_termination` remain separate authorizations.

## Candidate business-path evidence — merged PR #88

Merged-main regression context:

```text
source SHA: 1632aefe8c1fd71098200c434a1648d0385f4967
main CI:    33346470401
```

Workflow:

```text
.github/workflows/candidate-business-path-evidence.yml
```

It executes exactly:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

The customer/domain release owns scenarios, deterministic fixture/fault driver, read-only observer, DatasetConfig values and fingerprinted extension bytes. The framework evaluator alone decides PASS/FAIL. Cleanup failure prevents proof publication.

Business-path proof packaging now binds the evaluator result to the exact customer `ReleaseManifest.bundle.release_hash` through:

```text
src/fabric_data_framework/evidence/business_path_release_proof.py
```

The retained business-path artifact also carries `customer-release-manifest.json`, allowing the later release-proof producer to independently re-authenticate the same domain identity.

## Customer certification inputs

The customer-owned producer now exists in `fabric-customer`:

```text
.github/workflows/candidate-business-path-inputs.yml
```

Customer implementation baseline:

```text
feature PR #10 merge: cda90f1c02fc9606aa64d2d1bd13f2ab89628aab
checkpoint PR #11:    31f3f506bc1c16a445652de2ad48fe512cfec10a
customer main CI:     33353960915 SUCCESS
cert contract CI:     33353960906 SUCCESS
released runtime pin: fabric-data-framework==0.3.0
```

This proves the static exact-input packaging contract only. No real candidate input artifact has been retained for a selected framework candidate, and the customer source intentionally still reports real-environment blockers.

## Candidate certification domain binding — PR #92

Canonical owner:

```text
src/fabric_data_framework/evidence/candidate_certification.py
fabric-framework candidate-certify
.github/workflows/candidate-certification.yml
```

Candidate certification remains aggregation only. For a candidate certification attempt, proof and integration evidence must both carry a non-empty exact `domain_release_hash` and must match. The resulting `ReleaseReadinessReport.domain_release_hash` carries the same machine identity.

Certification still requires:

```text
release_ready = true
blockers = []
every required readiness gate = PASS
```

It does not execute Fabric, build a wheel, tag, or release.

## Immutable promotion domain re-check — PR #92

`.github/workflows/release.yml` re-verifies candidate source/main-CI/wheel identity and the certified readiness artifact before tagging.

Before the tag can be created it now additionally requires:

```text
release-readiness.json.domain_release_hash
  == release-proofs.json.domain_release_hash
  == integration-evidence.json.domain_release_hash

and domain_release_hash must be a lowercase 64-character SHA256.
```

Thus a certified framework wheel cannot be promoted with release proofs and integration evidence from different customer/domain releases.

## Ordinary CI behavior remains intentionally blocked

Ordinary framework CI does not provide retained candidate proofs or live integration evidence. It therefore remains:

```text
release_ready = false
required blockers = 15
```

A green ordinary readiness job proves fail-closed behavior, not release readiness. `domain_release_hash` may remain absent in this non-candidate path; it becomes mandatory when exact candidate partial proofs are merged/certified.

## Current truth

```text
public release                     v0.3.0
0.4.0                              UNRELEASED / FEATURE FROZEN
release_allowed                    false
candidate                          NOT YET FROZEN
ordinary readiness blockers        15
strict partial proof merge         MERGED + MAIN CI PROVEN (#86)
candidate-release-proofs           MERGED baseline (#87); domain hardening PR #92 PR-CI proven
candidate-business-path-evidence   MERGED + MAIN CI PROVEN (#88); no live run
candidate-integration-evidence     MERGED + MAIN CI PROVEN (#90); no live run
customer input producer contract   MERGED + CUSTOMER MAIN CI PROVEN (#10/#11)
actual customer input artifact      NOT YET RETAINED FOR A SELECTED CANDIDATE
release-proof/domain binding       PR #92 PR CI PROVEN / PENDING MERGE
certified integration evidence     NOT YET PRODUCED
five live business-path proofs     NOT YET RETAINED
certified readiness artifact       NOT YET PRODUCED
immutable v0.4.0                    NOT YET PUBLISHED
```

## Next order

```text
1. finish PR #92 final CI, merge, and independently verify framework main
2. checkpoint merged domain-binding state in canonical docs
3. replace customer real-environment placeholders only with reviewed real enterprise evidence/fault infrastructure
4. only then select/freeze one new exact framework main candidate
5. produce exact customer business-path input artifact for that candidate
6. run candidate-integration-evidence in the protected real environment
7. run five candidate-business-path-evidence gates
8. run candidate-release-proofs for the same framework + domain identities
9. candidate-certify must reach blockers=[]
10. framework-release promotes the exact certified wheel bytes
11. only after immutable v0.4.0 exists migrate customer production runtime from v0.3.0
```
