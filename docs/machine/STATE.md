# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-08-31
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
feature_freeze: true
candidate_status: not_frozen
code_baseline:
  pull_request: 92
  merge_sha: d5eed17f2ec2f869b4e3a448597e6d8d600568ea
  milestone: exact customer/domain release identity bound through proof, certification and promotion
  final_pr_ci_actions: 33356959856
  main_ci_actions: 33357032461
  tests: 734
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  live_fabric_evidence_retained: false
  candidate_capable_main_artifact:
    selected_as_frozen_candidate: false
    workflow_run_id: 33357032461
    workflow_run_attempt: 1
    candidate_git_sha: d5eed17f2ec2f869b4e3a448597e6d8d600568ea
    wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    wheel_inner_sha256: 5aa82d6befa3d5abe5d212d875721e6ae9e3e4bc4d67fd5b4cdd1a32d9e16701
    artifact_id: 9745451533
    artifact_archive_digest: sha256:716b1ba26267c748a449dacfd8e723eb21bc39a1414ac60eeb82596bc2afb618
    artifact_expires_at: 2026-11-29T04:25:31Z
release_readiness_artifact:
  artifact_id: 9745453012
  artifact_archive_digest: sha256:6f0cd23569f3395a92e1940286207ecc9d9e467a810e243fd1ba7fc4fb973227
  artifact_expires_at: 2026-09-14T04:25:47Z
customer_input_contract:
  feature_pr_10_merge: cda90f1c02fc9606aa64d2d1bd13f2ab89628aab
  checkpoint_pr_11_merge: 31f3f506bc1c16a445652de2ad48fe512cfec10a
  customer_main_ci: 33353960915
  customer_certification_contract_ci: 33353960906
  released_runtime_pin: fabric-data-framework==0.3.0
  actual_selected_candidate_input_artifact_retained: false
```

## Release decision

`0.4.0` remains **UNRELEASED**, feature-frozen, not release-allowed and without a selected/frozen exact candidate. Ordinary CI deliberately has no complete release proof or live certified integration manifest, so `release_ready=false` with 15 required blockers remains correct.

PR #92 is now **MERGED + MAIN CI PROVEN**. Final PR CI `33356959856` and independent main push CI `33357032461` both succeeded with **734 tests**. Main re-proved Python 3.11/3.13, exact wheel build and the ordinary fail-closed readiness contract.

No current claim is `FABRIC PROVEN`, `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, or `RELEASE PROVEN` for 0.4.

## Current candidate-capable main artifact

Main source:

```text
d5eed17f2ec2f869b4e3a448597e6d8d600568ea
```

Exact inner framework wheel SHA256:

```text
5aa82d6befa3d5abe5d212d875721e6ae9e3e4bc4d67fd5b4cdd1a32d9e16701
```

Artifact ID `9745451533` is retained through `2026-11-29T04:25:31Z`. It is **candidate-capable only**. It is not selected/frozen, certified, or release-proven. The uploaded ZIP digest is transport metadata and is never interchangeable with the inner wheel SHA256.

## Merged exact domain identity chain — PR #92

The framework and customer release identities remain independent:

```text
framework candidate source:
  candidate_git_sha

framework binary:
  ReleaseReadinessProofBundle.artifact_sha256
  ReleaseReadinessReport.artifact_sha256
  IntegrationEvidence.release_hash
  = exact inner framework wheel SHA256

customer/domain release:
  ReleaseManifest.bundle.release_hash
  ReleaseReadinessProofBundle.domain_release_hash
  ReleaseReadinessReport.domain_release_hash
  IntegrationEvidence.domain_release_hash
  = exact customer/domain release SHA256
```

These SHA256 values must never be assumed equal.

PR #92 permanently closes the previous machine-binding gap:

```text
business-path evaluator result
-> business_path_release_proof.py binds exact Customer ReleaseManifest.bundle.release_hash
-> candidate-business-path-evidence retains customer-release-manifest.json with the five-gate proof
-> candidate-release-proofs authenticates that retained manifest and cannot accept domain_release_hash as dispatch input
-> strict release proof merge requires the same non-empty domain_release_hash on every candidate partial bundle
-> candidate-certify requires proof.domain_release_hash == integration.domain_release_hash
-> ReleaseReadinessReport carries the same domain_release_hash
-> framework-release requires report == proofs == integration domain_release_hash before tag creation
```

No step above authors live PASS on its own.

## Customer certification input contract

The customer-owned producer is merged and Customer-main proven:

```text
fabric-customer/.github/workflows/candidate-business-path-inputs.yml
PR #10 merge       cda90f1c02fc9606aa64d2d1bd13f2ab89628aab
PR #11 checkpoint  31f3f506bc1c16a445652de2ad48fe512cfec10a
customer main CI   33353960915 SUCCESS
cert contract CI    33353960906 SUCCESS
```

This proves the static producer contract only. No input artifact has been retained for a selected framework candidate. Customer production/runtime dependency remains exactly `fabric-data-framework==0.3.0` until immutable v0.4.0 exists.

The customer source still intentionally fails closed on real-environment prerequisites, including reviewed control-plane external evidence and a real Warehouse ambiguous-COMMIT fault controller.

## Current remaining blockers

```text
exact framework candidate freeze                    NOT YET
selected-candidate customer input artifact           NOT YET RETAINED
reviewed real control-plane external evidence        NOT YET RETAINED
real Warehouse ambiguous-COMMIT fault controller     NOT YET CONFIGURED
certified integration evidence                       NOT YET PRODUCED
five live business-path proofs                       NOT YET RETAINED
complete release proof                               NOT YET RETAINED
certified readiness artifact                         NOT YET PRODUCED
ordinary readiness blockers                          15
immutable v0.4.0                                      NOT YET PUBLISHED
customer production dependency migration             NOT ALLOWED YET
```

## Next engineering order

```text
1. finish this merged-main documentation checkpoint
2. replace customer live placeholders only with reviewed real enterprise bindings/evidence
3. only then explicitly select/freeze one NEW exact framework main candidate
4. produce exact customer certification input artifact for that candidate
5. run candidate-integration-evidence in the protected real Fabric/control/Warehouse environment
6. run all five candidate-business-path-evidence drills
7. run candidate-release-proofs for the same exact framework + domain identities
8. candidate-certify must reach blockers=[]
9. framework-release promotes the exact already-certified wheel bytes
10. only after immutable v0.4.0 exists migrate customer production runtime from v0.3.0
```

## Evidence vocabulary boundary

Portable contract CI proves implementation and fail-closed behavior only. Green CI, workflow existence, or a candidate-capable wheel does not prove real Fabric execution, real Warehouse failure recovery, zero blockers, or release readiness.
