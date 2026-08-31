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
  pull_request: 94
  merge_sha: abc8b3a2b80b3f6babf88fdc2347a3bfe69be356
  milestone: removed obsolete unbound business-path proof API; candidate business-path proof packaging now requires exact customer ReleaseManifest
  final_pr_ci_actions: 33357795244
  main_ci_actions: 33357846835
  tests: 738
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  live_fabric_evidence_retained: false
  candidate_capable_main_artifact:
    selected_as_frozen_candidate: false
    workflow_run_id: 33357846835
    workflow_run_attempt: 1
    candidate_git_sha: abc8b3a2b80b3f6babf88fdc2347a3bfe69be356
    wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    wheel_inner_sha256: d763cd4410a69ff6a83c492f3a546d096502c96c87eeddb37c2ae9404557e7b7
    artifact_id: 9745697101
    artifact_archive_digest: sha256:c4a729c7da97185d27ff4b3cb50b48a106715fd6a4d2ef850e18fc6966ccf4ae
    artifact_expires_at: 2026-11-29T04:39:29Z
documentation_checkpoint:
  pull_request: 95
  merge_sha: 4006afb409c81c5510690c8c4dbeadd5e002fd0b
  final_pr_ci_actions: 33363382792
  main_ci_actions: 33363508468
  tests: 740
  milestone: canonical PR 94 release-proof cleanup documentation and consistency lock
release_readiness_artifact:
  artifact_id: 9745698588
  artifact_archive_digest: sha256:bc6e2b9c9e7c3c584b3d2a31c37d9c0fb5220a3e6922b02f8200243970e674c6
  artifact_expires_at: 2026-09-14T04:39:34Z
customer_input_contract:
  feature_pr_10_merge: cda90f1c02fc9606aa64d2d1bd13f2ab89628aab
  checkpoint_pr_11_merge: 31f3f506bc1c16a445652de2ad48fe512cfec10a
  compatibility_pr_12_merge: 9ddc11405de329fb647fb21b1217d1015e0fa3f5
  release_hardening_pr_14_merge: c4097dcc1319f382eb370e9c4d46dcbed7bb383b
  recovery_checkpoint_pr_15_merge: f83dc722da479971cdfd68d883291646c433ec15
  customer_pr_14_ci: 33367986684
  customer_pr_14_certification_contract_ci: 33367986688
  customer_pr_14_main_ci: 33368063581
  customer_pr_14_main_certification_contract_ci: 33368063590
  customer_pr_15_ci: 33368220306
  customer_pr_15_certification_contract_ci: 33368220330
  customer_main_ci: 33368266794
  customer_certification_contract_ci: 33368266793
  certification_framework_sha: abc8b3a2b80b3f6babf88fdc2347a3bfe69be356
  released_runtime_pin: fabric-data-framework==0.3.0
  actual_selected_candidate_input_artifact_retained: false
  real_control_plane_external_evidence_retained: false
  review_bound_control_plane_evidence_retained: false
  real_warehouse_fault_controller_configured: false
```

## Release decision

`0.4.0` remains **UNRELEASED**, feature-frozen, not release-allowed and without a selected/frozen exact candidate. Ordinary CI deliberately has no complete release proof or live certified integration manifest, so `release_ready=false` with 15 required blockers remains correct.

PR #94 is the current substantive code baseline and remains **MERGED + MAIN CI PROVEN**. Final PR CI `33357795244` and independent main push CI `33357846835` both succeeded with **738 tests**. The change removes the obsolete `ApprovedBusinessPathExecutionReport.partial_proof_bundle` / `write_business_path_partial_proof_bundle` path that could create a `ReleaseReadinessProofBundle` without `domain_release_hash`.

PR #95 is the current Framework documentation checkpoint. Final PR CI `33363382792` and independent main push CI `33363508468` succeeded with **740 tests**. It did not freeze a candidate or create live evidence.

No current claim is `FABRIC PROVEN`, `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, or `RELEASE PROVEN` for 0.4.

## Current candidate-capable main artifact

Substantive candidate-capable source:

```text
abc8b3a2b80b3f6babf88fdc2347a3bfe69be356
```

Exact inner framework wheel SHA256:

```text
d763cd4410a69ff6a83c492f3a546d096502c96c87eeddb37c2ae9404557e7b7
```

Artifact ID `9745697101` is retained through `2026-11-29T04:39:29Z`. It is **candidate-capable only**. It is not selected/frozen, certified, or release-proven. The uploaded ZIP digest is transport metadata and is never interchangeable with the inner wheel SHA256.

The current repository main also contains the PR #95 documentation checkpoint at `4006afb409c81c5510690c8c4dbeadd5e002fd0b`; documentation-only commits do not silently replace the explicit candidate-capable source identity or constitute candidate freeze.

## Exact domain identity chain — PR #92 plus PR #94 cleanup

The framework and customer release identities remain independent:

```text
framework candidate source:
  candidate_git_sha

framework binary:
  ReleaseReadinessProofBundle.artifact_sha256
  ReleaseReadinessReport.artifact_sha256
  IntegrationEvidence.release_hash
  = exact framework candidate wheel SHA256

customer/domain release:
  ReleaseManifest.bundle.release_hash
  ReleaseReadinessProofBundle.domain_release_hash
  ReleaseReadinessReport.domain_release_hash
  IntegrationEvidence.domain_release_hash
  = exact customer/domain release SHA256
```

These SHA256 values must never be assumed equal.

PR #92 established the machine identity chain:

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

PR #94 removes the last obsolete public runner-level proof packaging path. `approved_business_path_runner.py` now returns only the evaluated execution report. Candidate proof packaging is exclusively owned by `business_path_release_proof.py` and requires the exact customer `ReleaseManifest`. Exact-wheel scan of the PR #94 main artifact found only two `ReleaseReadinessProofBundle` construction owners: `business_path_release_proof.py` and `release_readiness_merge.py`; both bind or require non-empty `domain_release_hash` for candidate proof. The forbidden shortcut remains: `runner execution report -> candidate proof without exact ReleaseManifest` is removed.

No step above authors live PASS on its own.

## Customer certification input contract and release hardening

The customer-owned producer remains the source of the exact retained customer/domain inputs:

```text
fabric-customer/.github/workflows/candidate-business-path-inputs.yml
PR #10 merge       cda90f1c02fc9606aa64d2d1bd13f2ab89628aab
PR #11 checkpoint  31f3f506bc1c16a445652de2ad48fe512cfec10a
PR #12 compatibility alignment
                   9ddc11405de329fb647fb21b1217d1015e0fa3f5
PR #14 release hardening
                   c4097dcc1319f382eb370e9c4d46dcbed7bb383b
PR #15 recovery checkpoint
                   f83dc722da479971cdfd68d883291646c433ec15
PR #15 main CI      33368266794 SUCCESS
PR #15 main cert CI 33368266793 SUCCESS
```

Customer PR #14 hardened the control-plane external-evidence prerequisite. Seven arbitrary non-empty evidence reference strings are no longer sufficient to clear the Customer pre-candidate live-prerequisite boundary. Once all seven real external-evidence references exist, Customer additionally requires a credential-free source-controlled review binding that exactly matches the protected `DEV`/`UAT`/`PROD` environment and selected production-candidate control-plane profile. PR #14 and its main verification proved only this fail-closed contract; they did not validate an external ticket/catalog system, contact Fabric, execute control-plane probes, or author PASS evidence.

The current Customer source intentionally retains null control-plane evidence and review-binding placeholders plus the invalid Warehouse fault-controller placeholder. Therefore the **current** exact Customer builder truth remains:

```text
live_prerequisites_configured=false
live_prerequisite_blockers=
  control_plane_external_evidence_incomplete
  warehouse_real_fault_controller_not_configured
```

`control_plane_external_evidence_not_review_bound` is a later fail-closed transition only after all seven real evidence references are complete but the exact environment/profile review record is missing or mismatched. It is not fabricated as an additional current blocker while the evidence itself is absent.

No input artifact has been retained for a selected framework candidate. Customer production/runtime dependency remains exactly `fabric-data-framework==0.3.0` until immutable v0.4.0 exists.

## Current remaining blockers

```text
exact framework candidate freeze                    NOT YET
selected-candidate customer input artifact           NOT YET RETAINED
reviewed real control-plane external evidence        NOT YET RETAINED
review-bound control-plane evidence set              NOT YET RETAINED
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
1. obtain reviewed real control-plane external evidence for the intended protected environment and production-candidate profile; record only non-secret stable evidence references plus the exact Customer review binding
2. obtain and approve a reachable real Warehouse/session ambiguous-COMMIT fault controller; do not replace the .invalid placeholder before the real infrastructure exists
3. only after BOTH real-environment prerequisites are ready, explicitly select/freeze one NEW exact framework main candidate; never infer freeze from artifact existence
4. produce the exact customer certification input artifact for that candidate and exact Customer SHA
5. run candidate-integration-evidence in the protected real Fabric/control/Warehouse environment
6. run all five candidate-business-path-evidence drills
7. run candidate-release-proofs for the same exact framework wheel and customer/domain release identities
8. candidate-certify must reach blockers=[] and release_ready=true
9. framework-release promotes the exact already-certified wheel bytes; no rebuild
10. only after immutable v0.4.0 exists migrate customer production runtime from v0.3.0
```

## Evidence vocabulary boundary

Portable contract CI proves implementation and fail-closed behavior only. Green CI, workflow existence, a source scan, a candidate-capable wheel, Customer review-binding metadata, or a source-controlled evidence reference does not prove real Fabric execution, real control-plane controls, real Warehouse failure recovery, zero blockers, or release readiness.
