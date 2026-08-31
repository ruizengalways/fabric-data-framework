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
  pull_request: 97
  merge_sha: 3b39448fcefbeba7a66469c847542c3255e462ff
  milestone: added traceable Fabric Notebook manual certification and explicit GitHub administrator override certification without requiring GitHub-to-Fabric connectivity
  final_pr_ci_actions: 33377064054
  main_ci_actions: 33377208722
  tests: 748
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  live_fabric_evidence_retained: false
  candidate_capable_main_artifact:
    selected_as_frozen_candidate: false
    workflow_run_id: 33377208722
    workflow_run_attempt: 1
    candidate_git_sha: 3b39448fcefbeba7a66469c847542c3255e462ff
    wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    wheel_inner_sha256: 5d0c2f1f4348543bb8b9da0748788cc68b3ccbfed96fd73cec11ad7f475c0517
    artifact_id: 9752314929
    artifact_archive_digest: sha256:b53943452d4f985135aa3ce06a3f55a0dd87195676e539b7af970bbfb48b8bed
    artifact_expires_at: 2026-11-29T09:20:52Z
previous_code_baseline:
  pull_request: 94
  merge_sha: abc8b3a2b80b3f6babf88fdc2347a3bfe69be356
  final_pr_ci_actions: 33357795244
  main_ci_actions: 33357846835
  tests: 738
  candidate_capable_wheel_inner_sha256: d763cd4410a69ff6a83c492f3a546d096502c96c87eeddb37c2ae9404557e7b7
  candidate_capable_artifact_id: 9745697101
documentation_checkpoint:
  pull_request: 95
  merge_sha: 4006afb409c81c5510690c8c4dbeadd5e002fd0b
  final_pr_ci_actions: 33363382792
  main_ci_actions: 33363508468
  tests: 740
  milestone: canonical PR 94 release-proof cleanup documentation and consistency lock
release_readiness_artifact:
  artifact_id: 9752317358
  artifact_archive_digest: sha256:23a336390abade0de17ecf044ecec24be418da0cb587609a8256d5394559475e
  artifact_expires_at: 2026-09-14T09:21:07Z
  release_ready: false
  required_blockers: 15
manual_certification_contract:
  framework_pr: 97
  notebook_form_supported: true
  candidate_manifest_auto_identity: true
  optional_wheel_byte_hash_verification: true
  github_admin_override_workflow: .github/workflows/candidate-admin-certification.yml
  github_admin_override_requires_fabric_connectivity: false
  github_admin_override_resolves_candidate_identity_from_main_ci_run: true
  admin_override_record_retained: false
  admin_override_can_mark_manual_status_certified: true
  missing_fields_remain_explicit: true
  admin_override_fabricates_missing_live_evidence: false
  existing_framework_release_accepts_admin_override_as_release_readiness: false
  existing_evidence_based_candidate_certification_unchanged: true
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

`0.4.0` remains **UNRELEASED**, feature-frozen again after the explicitly requested manual-certification capability, not release-allowed, and without a selected/frozen exact candidate. Ordinary CI deliberately has no complete release proof or live certified integration manifest, so `release_ready=false` with 15 required blockers remains correct.

PR #97 is the current substantive code baseline and is **MERGED + MAIN CI PROVEN**. Final PR CI `33377064054` and independent main push CI `33377208722` both succeeded; the main Python 3.11 lane reported **748 passed**. PR #97 adds a Notebook/manual certification record and UI plus `.github/workflows/candidate-admin-certification.yml`. It does not contact Fabric, does not manufacture live evidence, does not freeze a candidate, and does not publish `v0.4.0`.

PR #94 remains the previous release-proof/domain-binding cleanup baseline: merge SHA `abc8b3a2b80b3f6babf88fdc2347a3bfe69be356`, PR CI `33357795244`, main CI `33357846835`, 738 tests, candidate-capable wheel SHA256 `d763cd4410a69ff6a83c492f3a546d096502c96c87eeddb37c2ae9404557e7b7`, artifact `9745697101`. Its identity-chain guarantees remain part of current source.

PR #95 remains a historical Framework documentation checkpoint. Documentation-only checkpoints do not constitute candidate freeze.

No current claim is `FABRIC PROVEN`, `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, or evidence-based `RELEASE PROVEN` for 0.4.

## Current candidate-capable main artifact

Current substantive candidate-capable source:

```text
3b39448fcefbeba7a66469c847542c3255e462ff
```

Exact inner framework wheel SHA256:

```text
5d0c2f1f4348543bb8b9da0748788cc68b3ccbfed96fd73cec11ad7f475c0517
```

Artifact ID `9752314929` is retained through `2026-11-29T09:20:52Z`. It is **candidate-capable only**. `selected_as_frozen_candidate: false`. Artifact existence, Notebook availability, or the presence of an administrator-override workflow does not silently select/freeze/certify this candidate.

The uploaded ZIP digest `sha256:b53943452d4f985135aa3ce06a3f55a0dd87195676e539b7af970bbfb48b8bed` is transport metadata and is never interchangeable with the inner wheel SHA256.

## Notebook / manual / administrator certification — PR #97

PR #97 adds an operationally separate certification transport for enterprises where GitHub cannot or should not authenticate into the corporate Fabric tenant.

Company-Fabric Notebook path:

```text
exact framework wheel + CANDIDATE.json
-> Fabric Notebook / Environment
-> framework manual-certification UI/API
-> operator records observed checks
-> manual-certification.json
```

When `CANDIDATE.json` is available, Framework auto-fills `framework_version`, the 40-character `candidate_git_sha`, and the 64-character wheel SHA256. Supplying the actual wheel path additionally hashes the wheel bytes and rejects an identity mismatch. This avoids requiring an operator to manually copy long hashes from a locked-down corporate environment.

Normal Notebook semantics are fail-closed: without administrator override, an incomplete identity yields `PARTIAL`; `CERTIFIED` requires exact candidate identity plus at least one supplied check and all supplied checks PASS.

Explicit administrator override semantics are different and intentionally visible:

```text
status = CERTIFIED
admin_override = true
override_reason = required
missing_fields = retained exactly
```

An administrator may accept a manual candidate even when some optional context/evidence cannot be exported. Missing evidence is not rewritten as evidence and unrun checks are not claimed to have run.

The GitHub-side convenience workflow is:

```text
.github/workflows/candidate-admin-certification.yml
```

It requires no Fabric token, Service Principal, SQL connection string, or GitHub-to-company-Fabric connectivity. The operator supplies a successful Framework `main` CI `candidate_run_id`, an override reason, and explicit confirmation; environment/notebook reference/notes are optional. GitHub resolves and verifies candidate SHA, run attempt, framework version, exact wheel bytes, `CANDIDATE.json`, `SHA256SUMS`, and wheel SHA256 automatically.

No administrator override record has been run/retained yet. The presence of this capability therefore changes no current release truth.

### Release boundary for administrator override

PR #97 deliberately does **not** modify the existing evidence-based release workflow. `framework-release` still requires the existing successful `.github/workflows/candidate-certification.yml` provenance and the normal exact release-readiness/proof/integration artifacts. An Admin Override record can say `CERTIFIED` under the explicit manual governance lane, and an exact-identity GitHub override record can retain `release_authorized=true` as the administrator decision, but the existing `release.yml` does not consume that record as a substitute for evidence-based readiness.

If policy later chooses to let an administrator override directly authorize tag/release creation, that must be a separate explicit release-policy change; it is not implied by PR #97.

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

PR #92 merge SHA `d5eed17f2ec2f869b4e3a448597e6d8d600568ea`; final PR CI `33356959856`; main CI `33357032461`; 734 tests. It remains **MERGED + MAIN CI PROVEN**.

PR #94 removes the last obsolete public runner-level proof packaging path. `approved_business_path_runner.py` now returns only the evaluated execution report. Candidate proof packaging is exclusively owned by `business_path_release_proof.py` and requires the exact customer `ReleaseManifest`. The obsolete `partial_proof_bundle` / `write_business_path_partial_proof_bundle` path is removed. The forbidden shortcut remains: `runner execution report -> candidate proof without exact ReleaseManifest` is removed.

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

Customer PR #14 hardened the control-plane external-evidence prerequisite. Seven arbitrary non-empty evidence reference strings are no longer sufficient to clear the Customer pre-candidate live-prerequisite boundary. Once all seven real external-evidence references exist, Customer additionally requires a credential-free source-controlled review binding that exactly matches the protected `DEV`/`UAT`/`PROD` environment and selected production-candidate control-plane profile.

The current Customer source intentionally retains null control-plane evidence and review-binding placeholders plus the invalid Warehouse fault-controller placeholder. Therefore the **current evidence-based Customer builder truth** remains:

```text
live_prerequisites_configured=false
live_prerequisite_blockers=
  control_plane_external_evidence_incomplete
  warehouse_real_fault_controller_not_configured
```

`control_plane_external_evidence_not_review_bound` is a later fail-closed transition only after all seven real evidence references are complete but the exact environment/profile review record is missing or mismatched.

Manual/Admin certification does not rewrite those Customer prerequisites. It is a separate governance decision path for environments where the full retained-evidence chain is impractical.

No input artifact has been retained for a selected framework candidate. Customer production/runtime dependency remains exactly `fabric-data-framework==0.3.0` until immutable v0.4.0 exists.

## Current remaining blockers — evidence-based release lane

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

## Next operating order

Two paths now coexist.

### A. Company Fabric manual / Notebook validation

```text
1. choose/download one exact candidate-capable main artifact; artifact existence does not itself freeze it
2. bring the exact wheel and, when possible, CANDIDATE.json into the isolated company Fabric environment
3. install the wheel in a Notebook/Environment and run the bounded real checks that corporate permissions allow
4. use display_notebook_certification_form() to record observed checks; identity auto-fills from CANDIDATE.json when available
5. if evidence/context cannot leave the corporate tenant, an administrator may explicitly use Admin override with a non-secret reason; missing_fields remains visible
6. if a GitHub-side exact administrator record is wanted, run candidate-admin-certification with the successful main candidate_run_id; GitHub does not connect to Fabric
```

This path may create an explicit manual `CERTIFIED` governance record. It does not fabricate checks that were not run and does not currently satisfy `release.yml`'s evidence-based release inputs.

### B. Full evidence-based automated release certification

```text
1. obtain reviewed real control-plane external evidence for the intended protected environment and production-candidate profile
2. obtain and approve a reachable real Warehouse/session ambiguous-COMMIT fault controller
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

Portable contract CI proves implementation and fail-closed behavior only. Green CI, workflow existence, source scan, candidate-capable wheel, Customer review-binding metadata, source-controlled evidence reference, Notebook checkbox, or Administrator Override does not by itself prove an unexecuted Fabric/control-plane/Warehouse check.

The manual lane may legitimately record `CERTIFIED` as an administrator governance decision; that provenance must remain distinguishable from `FABRIC PROVEN`, `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, and evidence-based `RELEASE PROVEN`.
