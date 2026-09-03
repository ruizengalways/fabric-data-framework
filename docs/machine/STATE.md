# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-09-03
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
feature_freeze: true
candidate_status: not_frozen
code_baseline:
  pull_request: 99
  merge_sha: 303683729c4915d78200d463a6def01c8de9eae6
  milestone: hardened the first company-Fabric Notebook certification path with Fabric-supported widgets, explicit PASS/FAIL/NOT_RUN capture, and an executable bounded first-test runbook
  final_pr_ci_actions: 33381590800
  main_ci_actions: 33381666892
  tests: 753
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  live_fabric_evidence_retained: false
  first_company_fabric_test_ready: true
  first_company_fabric_test_executed: true
  first_company_fabric_test_result: bounded_pass
  first_company_fabric_test_runbook: docs/human/FIRST_FABRIC_NOTEBOOK_TEST.md
  first_company_fabric_test_checkpoint: docs/machine/FIRST_COMPANY_FABRIC_TEST_2026-09-03.md
  candidate_capable_main_artifact:
    selected_as_frozen_candidate: false
    workflow_run_id: 33381666892
    workflow_run_attempt: 1
    candidate_git_sha: 303683729c4915d78200d463a6def01c8de9eae6
    wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    wheel_inner_sha256: 0638c95c19ebcc43ec4ec462b7f960a164209874223517e3f74b951264b0eaf6
    artifact_id: 9753976212
    artifact_archive_digest: sha256:cd790310378d8aa11e950b004c9183125c52bbbc0ddf484d7749faa675e7171b
    artifact_expires_at: 2026-11-29T10:16:35Z
first_company_fabric_test:
  executed_on: 2026-09-03
  environment: DEV
  exact_identity: PASS
  lakehouse_smoke: PASS
  full_replace: PASS
  watermark_scd1: PASS
  watermark_scd2: PASS
  retry_idempotency: PASS
  reconciliation_fail_closed: PASS
  warehouse_commit: NOT_RUN
  warehouse_ambiguous_commit: NOT_RUN
  manual_certification_status: CERTIFIED
  manual_certification_mode: NOTEBOOK
  manual_certification_missing_fields:
    - notebook_reference
  admin_override: false
  release_authorized: false
  raw_manual_record_retained_in_repo: false
  summary_checkpoint: docs/machine/FIRST_COMPANY_FABRIC_TEST_2026-09-03.md
previous_code_baseline:
  pull_request: 97
  merge_sha: 3b39448fcefbeba7a66469c847542c3255e462ff
  final_pr_ci_actions: 33377064054
  main_ci_actions: 33377208722
  tests: 748
  candidate_capable_wheel_inner_sha256: 5d0c2f1f4348543bb8b9da0748788cc68b3ccbfed96fd73cec11ad7f475c0517
  candidate_capable_artifact_id: 9752314929
historical_identity_baseline:
  pull_request: 94
  merge_sha: abc8b3a2b80b3f6babf88fdc2347a3bfe69be356
  final_pr_ci_actions: 33357795244
  main_ci_actions: 33357846835
  tests: 738
  candidate_capable_wheel_inner_sha256: d763cd4410a69ff6a83c492f3a546d096502c96c87eeddb37c2ae9404557e7b7
  candidate_capable_artifact_id: 9745697101
documentation_checkpoint:
  pull_request: 98
  merge_sha: cc3f16099f5d9dc6c42189ec281a4d9d1a11e565
  final_pr_ci_actions: 33377525790
  main_ci_actions: 33377589383
  milestone: prior canonical machine-state checkpoint for Notebook/manual and administrator certification after PR 97
historical_documentation_checkpoint:
  pull_request: 95
  merge_sha: 4006afb409c81c5510690c8c4dbeadd5e002fd0b
  final_pr_ci_actions: 33363382792
  main_ci_actions: 33363508468
  tests: 740
  milestone: canonical PR 94 release-proof cleanup documentation and consistency lock
release_readiness_artifact:
  artifact_id: 9753979589
  artifact_archive_digest: sha256:6d47510240f5c3422ca08fa5955e21b7c67c9c743810a315f8861988f071f858
  artifact_expires_at: 2026-09-14T10:16:54Z
  release_ready: false
  required_blockers: 15
manual_certification_contract:
  framework_pr: 99
  original_manual_certification_feature_pr: 97
  notebook_form_supported: true
  notebook_output_widget_used: false
  notebook_result_surface: disabled_textarea
  notebook_check_result_control: dropdown
  notebook_check_result_states:
    - NOT_RUN
    - PASS
    - FAIL
  form_executes_tests: false
  candidate_manifest_auto_identity: true
  optional_wheel_byte_hash_verification: true
  github_admin_override_workflow: .github/workflows/candidate-admin-certification.yml
  github_admin_override_requires_fabric_connectivity: false
  github_admin_override_resolves_candidate_identity_from_main_ci_run: true
  notebook_manual_record_executed: true
  notebook_manual_record_raw_repo_retained: false
  admin_override_record_retained: false
  admin_override_can_mark_manual_status_certified: true
  failed_checks_remain_explicit_under_admin_override: true
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
  manual_admin_checkpoint_pr_16_merge: 0c6cb0afd662f61082b41d34ef245ec2b055c97d
  customer_pr_16_ci: 33378015885
  customer_pr_16_certification_contract_ci: 33378015947
  customer_main_ci: 33378071077
  customer_certification_contract_ci: 33378071142
  certification_framework_sha: abc8b3a2b80b3f6babf88fdc2347a3bfe69be356
  released_runtime_pin: fabric-data-framework==0.3.0
  actual_selected_candidate_input_artifact_retained: false
  real_control_plane_external_evidence_retained: false
  review_bound_control_plane_evidence_retained: false
  real_warehouse_fault_controller_configured: false
```

## Release decision

`0.4.0` remains **UNRELEASED**, feature-frozen after the explicitly requested manual-certification capability and its pre-test Fabric Notebook hardening, not release-allowed, and without a selected/frozen exact candidate. The first bounded real-company Fabric Notebook test has now executed successfully for the exact PR #99 artifact, but ordinary CI still has no complete release proof or live certified integration manifest, so `release_ready=false` with 15 required blockers remains correct.

PR #99 is the current substantive code baseline and is **MERGED + MAIN CI PROVEN**. Final PR CI `33381590800` and independent main push CI `33381666892` both succeeded; the main Python 3.11 lane reported **753 passed**. PR #99 fixes the first-test Notebook UI to avoid Fabric's unsupported Output widget, records check outcomes with `NOT RUN / PASS / FAIL` dropdowns, and adds `docs/human/FIRST_FABRIC_NOTEBOOK_TEST.md`. It does not itself contact Fabric, does not manufacture live evidence, does not freeze a candidate, and does not publish `v0.4.0`.

PR #97 remains the original Notebook/manual certification and GitHub Admin Override feature baseline: merge SHA `3b39448fcefbeba7a66469c847542c3255e462ff`, PR CI `33377064054`, main CI `33377208722`, 748 tests, candidate-capable wheel SHA256 `5d0c2f1f4348543bb8b9da0748788cc68b3ccbfed96fd73cec11ad7f475c0517`, artifact `9752314929`.

PR #94 remains the historical release-proof/domain-binding cleanup baseline: merge SHA `abc8b3a2b80b3f6babf88fdc2347a3bfe69be356`, PR CI `33357795244`, main CI `33357846835`, 738 tests, candidate-capable wheel SHA256 `d763cd4410a69ff6a83c492f3a546d096502c96c87eeddb37c2ae9404557e7b7`, artifact `9745697101`. Its identity-chain guarantees remain part of current source.

PR #98 is a prior machine-state documentation checkpoint; PR #95 remains an older historical documentation checkpoint. Documentation-only checkpoints do not constitute candidate freeze.

The bounded Notebook execution may be described as a real company-Fabric DEV compatibility/smoke result for the checks actually run. No current claim is `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, or evidence-based `RELEASE PROVEN` for 0.4. No retained live evidence-based release run exists yet.

## Exact artifact used for the first company Fabric test

The executed bounded test used the PR #99 main artifact, not the older PR #97 artifact and not a later documentation-only wheel:

```text
framework-ci main run          33381666892
candidate_git_sha              303683729c4915d78200d463a6def01c8de9eae6
artifact name                  framework-wheel-303683729c4915d78200d463a6def01c8de9eae6
artifact ID                    9753976212
wheel filename                 fabric_data_framework-0.4.0-py3-none-any.whl
wheel inner SHA256             0638c95c19ebcc43ec4ec462b7f960a164209874223517e3f74b951264b0eaf6
artifact ZIP digest            sha256:cd790310378d8aa11e950b004c9183125c52bbbc0ddf484d7749faa675e7171b
artifact expires               2026-11-29T10:16:35Z
```

The artifact contains the exact wheel plus `CANDIDATE.json` and `SHA256SUMS`. All three were kept together for the company Fabric test. The Notebook verified actual wheel bytes, installed Framework version, exact candidate Git SHA, and `workflow_run_id=33381666892` before semantic checks.

This artifact remains **candidate-capable only**. `selected_as_frozen_candidate: false`. Downloading it, uploading it to Fabric, or executing the bounded first test did not silently freeze/select it and did not change `release_allowed=false`.

The uploaded ZIP digest is transport metadata and is never interchangeable with the inner wheel SHA256.

## First company Fabric bounded execution — 2026-09-03

Canonical detailed checkpoint:

```text
docs/machine/FIRST_COMPANY_FABRIC_TEST_2026-09-03.md
```

Actual results:

```text
exact candidate identity / wheel-byte verification  PASS
Lakehouse write/read smoke                          PASS
FULL -> REPLACE guard + result                      PASS
WATERMARK -> SCD1                                   PASS
WATERMARK -> SCD2                                   PASS
retry / idempotency                                 PASS
reconciliation fail-closed                          PASS
warehouse.commit                                    NOT_RUN
warehouse.ambiguous_commit                          NOT_RUN
manual certification                                CERTIFIED / NOTEBOOK
admin override                                      false
release authorized                                  false
```

The reconciliation check deliberately forced the underlying reconciliation status to `FAIL`; the certification check passed because Framework also returned `blocks_state_advance=true`.

A dedicated DEV Warehouse exists, but the bounded lane did not substitute an ad-hoc SQL test for the approved Warehouse runner. Session-termination/fault-injection authorization was not confirmed, so both Warehouse checks remain `NOT_RUN`.

The manual record was created in the attached company Fabric DEV Lakehouse with `missing_fields=[notebook_reference]`. `operator`, `notebook_reference`, `notes`, and `override_reason` were null/empty in the final sanity inspection, and no secret-bearing material was observed. The raw JSON is not retained in this repository; this machine checkpoint retains only the non-secret summary.

The certification form remains a **result recorder**, not a test executor. The PASS values above came from actual cells executed before the form was submitted.

No candidate freeze is required for this bounded pre-freeze compatibility test. Completion of the test does not by itself make the evidence-based release lane ready.

## Notebook / manual / administrator certification — PR #97 plus PR #99 hardening

Company-Fabric Notebook path:

```text
exact framework wheel + CANDIDATE.json
-> isolated company Fabric DEV Notebook / default Lakehouse
-> run FIRST_FABRIC_NOTEBOOK_TEST.md cells
-> framework manual-certification UI/API records observed PASS/FAIL/NOT_RUN
-> manual-certification.json
```

When `CANDIDATE.json` is available, Framework auto-fills `framework_version`, the 40-character `candidate_git_sha`, and the 64-character wheel SHA256. Supplying the actual wheel path additionally hashes the wheel bytes and rejects an identity mismatch. This avoids requiring an operator to manually copy long hashes from a locked-down corporate environment.

Normal Notebook semantics are fail-closed: without administrator override, an incomplete identity yields `PARTIAL`; a supplied failed check also yields `PARTIAL`; `CERTIFIED` requires exact candidate identity plus at least one supplied check and all supplied checks PASS.

Explicit administrator override semantics are different and intentionally visible:

```text
status = CERTIFIED
admin_override = true
override_reason = required
missing_fields = retained exactly
executed FAIL checks remain retained as FAIL
```

An administrator may accept a manual candidate when some optional context/evidence cannot be exported. Missing evidence is not rewritten as evidence and unrun checks are not claimed to have run. The default operational policy is to investigate a known functional FAIL rather than use override to erase it.

The GitHub-side convenience workflow remains:

```text
.github/workflows/candidate-admin-certification.yml
```

It requires no Fabric token, Service Principal, SQL connection string, or GitHub-to-company-Fabric connectivity. The operator supplies a successful Framework `main` CI `candidate_run_id`, an override reason, and explicit confirmation; environment/notebook reference/notes are optional. GitHub resolves and verifies candidate SHA, run attempt, framework version, exact wheel bytes, `CANDIDATE.json`, `SHA256SUMS`, and wheel SHA256 automatically.

No administrator override record has been run/retained. A normal company-Fabric Notebook manual certification record was created during the 2026-09-03 bounded execution with `admin_override=false` and `release_authorized=false`; its raw JSON remains inside the company Fabric environment rather than this repository.

### Release boundary for administrator override

PR #97 and PR #99 deliberately do **not** modify the existing evidence-based release workflow. `framework-release` still requires the existing successful `.github/workflows/candidate-certification.yml` provenance and the normal exact release-readiness/proof/integration artifacts. An Admin Override record can say `CERTIFIED` under the explicit manual governance lane, and an exact-identity GitHub override record can retain `release_authorized=true` as the administrator decision, but the existing `release.yml` does not consume that record as a substitute for evidence-based readiness.

If policy later chooses to let an administrator override directly authorize tag/release creation, that must be a separate explicit release-policy change; it is not implied by PR #97 or PR #99.

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
PR #16 manual/admin recovery checkpoint
                   0c6cb0afd662f61082b41d34ef245ec2b055c97d
PR #16 main CI      33378071077 SUCCESS
PR #16 main cert CI 33378071142 SUCCESS
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

Two paths remain distinct.

### A. First company Fabric bounded manual / Notebook validation — COMPLETED 2026-09-03

The exact main run `33381666892` / artifact `9753976212` was executed in company Fabric DEV and produced the bounded PASS/NOT_RUN result recorded above and in `docs/machine/FIRST_COMPANY_FABRIC_TEST_2026-09-03.md`.

No candidate freeze is required for this bounded pre-freeze compatibility test. Completion of the test does not by itself make the evidence-based release lane ready.

### B. Full evidence-based automated release certification — NEXT RELEASE-ORIENTED WORK

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

Do not freeze the already-tested PR #99 artifact merely because its bounded test passed. The strict lane calls for a NEW exact candidate only after the real environment prerequisites are actually ready.

## Evidence vocabulary boundary

Portable contract CI proves implementation and fail-closed behavior only. Green CI, workflow existence, source scan, candidate-capable wheel, Customer review-binding metadata, source-controlled evidence reference, Notebook dropdown, or Administrator Override does not by itself prove an unexecuted Fabric/control-plane/Warehouse check.

The 2026-09-03 manual lane legitimately records `CERTIFIED` for the executed bounded Notebook checks with exact identity and no Admin Override. That provenance must remain distinguishable from `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, and evidence-based `RELEASE PROVEN`.