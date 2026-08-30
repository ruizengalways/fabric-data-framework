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
certification_implementation: src/fabric_data_framework/evidence/candidate_certification.py
candidate_artifact_contract: src/fabric_data_framework/deployment/candidate_artifact.py
candidate_release_proofs_workflow: .github/workflows/candidate-release-proofs.yml
candidate_certification_workflow: .github/workflows/candidate-certification.yml
release_promotion_workflow: .github/workflows/release.yml
readiness_cli: fabric-framework release-readiness
proof_merge_cli: fabric-framework release-proofs-merge
certification_cli: fabric-framework candidate-certify
```

## Purpose

The release system is deliberately split into independent truth boundaries:

```text
exact candidate artifact identity
  -> retained non-integration release proof
  -> retained integration evidence
  -> candidate certification
  -> immutable exact-byte promotion
```

No layer may invent PASS merely to satisfy the next layer. Provider/business-path evidence is produced separately, aggregation validates retained facts, and release promotes only already-certified bytes.

## Exact candidate identity

```text
candidate_git_sha = exact 40-character source commit
artifact_sha256   = exact inner candidate wheel SHA256
framework_version = exact package version
candidate_run_id  = successful main framework-ci run that built those bytes
```

GitHub artifact archive digest is transport metadata only. It is not the inner wheel SHA256 and must not replace `artifact_sha256` in proof, certification, or release.

Main CI retains:

```text
fabric_data_framework-<version>-py3-none-any.whl
SHA256SUMS
CANDIDATE.json
```

`CANDIDATE.json` binds package/version, source SHA, workflow run ID/attempt, wheel filename and exact inner wheel SHA256. The standard-library verifier authenticates these bytes before installation.

## Readiness evidence ownership

```text
ReleaseReadinessProofBundle
  source.tests
  wheel.integrity
  customer.compatibility
  full.replace
  watermark.scd1
  watermark.scd2
  retry.idempotency
  reconciliation.fail_closed

IntegrationEvidenceManifest
  fabric.identity
  control.certification
  fabric.pipeline
  fabric.copy
  fabric.spark
  warehouse.commit
  warehouse.ambiguous_commit
  optional external.cdc.debezium
```

Integration-backed gates cannot be satisfied by generic release proof entries.

## Strict partial release-proof merge

Canonical implementation:

```text
src/fabric_data_framework/evidence/release_readiness_merge.py
fabric-framework release-proofs-merge
```

Merged PR #86 established fail-closed partial proof merge:

```text
PR        #86
merge SHA 0f70e037806482c677fccae0ce9432504f2a9885
PR CI     33342779028
main CI   33342806854
tests     664
```

Every partial bundle must match readiness schema/framework version and bind the same exact candidate SHA plus non-null inner wheel SHA256. Only known non-integration gates with exact gate kind are accepted. Retained references/details are secret-scanned.

Merge semantics:

```text
omitted / NOT_RUN                        -> no proof
one substantive PASS/FAIL/OUT_OF_SCOPE  -> retain unchanged
model-identical duplicate substantive   -> allowed
different substantive result            -> conflict
different PASS evidence                  -> conflict
candidate SHA mismatch                   -> reject
wheel SHA mismatch                       -> reject
unknown gate / kind drift                -> reject
integration-backed gate                  -> reject
```

There is no latest-wins, PASS-wins, FAIL-wins, or timestamp precedence. A conflicting rerun must be explicitly selected before merge.

A successful merge proves only that supplied retained evidence is compatible. It does not create PASS and does not make the candidate releasable.

## Candidate release-proof producer

Workflow:

```text
.github/workflows/candidate-release-proofs.yml
```

Current feature-branch state: **IMPLEMENTED / CI PENDING**.

The workflow is manual and must be dispatched at the exact candidate ref. It requires:

```text
candidate_run_id
candidate_git_sha
candidate_wheel_sha256
customer_git_sha
business_path_evidence_run_id
```

It independently verifies:

```text
GITHUB_SHA == candidate_git_sha
candidate source is reachable from framework main
candidate run is successful main push framework-ci
candidate run head SHA equals candidate_git_sha
required CI jobs test-python-3.11 / test-python-3.13 / build-wheel / release-readiness-contract are success
CANDIDATE.json + SHA256SUMS + downloaded wheel bytes match exact inputs
exact candidate wheel installs successfully
customer_git_sha is exact and reachable from fabric-customer main
customer project-validate passes against exact candidate wheel
100-table Health framework-next project generation/validation passes exact workload counts
```

Only after those observations does it create static PASS results for:

```text
source.tests
wheel.integrity
customer.compatibility
```

It does **not** contain code that directly marks the five live business-path gates PASS.

Those five gates must come from a successful exact-candidate run of:

```text
.github/workflows/candidate-business-path-evidence.yml
```

Expected artifact:

```text
business-path-release-proofs-<candidate SHA>/business-path-release-proofs.json
```

Required live business-path gates:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

`candidate-release-proofs.yml` verifies that producer run is `workflow_dispatch`, successful, uses the exact workflow path, and has `head_sha == candidate_git_sha`. It then strict-merges static + business-path partial bundles and refuses final publication unless the merged bundle contains exactly every required non-integration gate and all are PASS.

Successful output:

```text
release-proofs-<candidate SHA>/
  release-proofs.json
  customer-project-validation.json
  health-project-validation.json
```

Retention is 90 days. The workflow builds no wheel, creates no tag/release, and cannot substitute old customer compatibility or old business-path evidence for the exact candidate.

## Integration evidence template

Approved integration check membership is source controlled at:

```text
release/0.4.0/integration-evidence-template.json
```

The template has `release_hash=null`; `candidate-certify` binds environment/domain and exact inner wheel SHA256 at certification time. The retained `IntegrationEvidenceManifest` must exactly match that materialized spec and be certified for every required integration check.

## Candidate certification

Reusable implementation/workflow:

```text
src/fabric_data_framework/evidence/candidate_certification.py
fabric-framework candidate-certify
.github/workflows/candidate-certification.yml
```

Candidate certification is merged and CI proven from PR #84. It accepts only a successful exact-SHA `candidate-release-proofs.yml` run and successful exact-SHA `candidate-integration-evidence.yml` run, re-verifies exact candidate bytes, validates proof/integration identity and safety, and uploads `release-readiness-certified-<candidate SHA>` only when every required readiness gate is PASS and blockers are empty.

Certification performs no wheel build, tag creation, or release creation.

## Readiness matrix

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

Optional unless 0.4 scope changes:

```text
external.cdc.debezium
```

Ordinary framework CI deliberately supplies no proof bundle or integration manifest, so its readiness report remains:

```text
release_ready = false
15 required blockers
```

That is expected fail-closed behavior, not a failed CI contract and not live Fabric evidence.

## Immutable promotion

`framework-release` is manual exact-byte promotion only. It downloads the exact candidate artifact and exact certified readiness artifact, verifies all identities and PASS state, then tags the exact candidate SHA and publishes those same wheel bytes plus evidence assets. There is no release-time rebuild.

## Current truth

```text
public release                     v0.3.0
0.4.0                              UNRELEASED / FEATURE FROZEN
release_allowed                    false
candidate                          NOT YET FROZEN
ordinary readiness blockers        15
strict partial proof merge         MERGED + MAIN CI PROVEN
candidate-release-proofs workflow  FEATURE BRANCH IMPLEMENTED / CI PENDING
candidate-business-path-evidence   NOT YET IMPLEMENTED
candidate-integration-evidence     NOT YET IMPLEMENTED
certified readiness artifact       NOT YET PRODUCED
```

Next order:

```text
1. validate/merge candidate-release-proofs workflow
2. implement real candidate-business-path-evidence producer
3. implement candidate-integration-evidence orchestration
4. select/freeze one exact main candidate SHA + inner wheel SHA256
5. run exact customer/static proof
6. run representative live business-path proof
7. run approved Fabric integration evidence
8. candidate-certify must reach blockers=[]
9. framework-release promotes exact certified bytes
```
