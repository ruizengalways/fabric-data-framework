# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-09-05
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
feature_freeze: true
candidate_status: not_frozen
code_baseline:
  pull_request: 105
  merge_sha: cb9f9be77a98a0a5aa8c5f85e0fa3d92697c60f0
  milestone: unified one-call runtime scope plus fail-closed first-time dedicated Control Plane bootstrap, built on the durable Fabric Pipeline child contract
  final_pr_ci_actions: 33961766325
  main_ci_actions: 33961827610
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  live_fabric_evidence_retained_for_current_bytes: false
  current_main_artifact:
    selected_as_frozen_candidate: false
    workflow_run_id: 33961827610
    workflow_run_attempt: 1
    candidate_git_sha: cb9f9be77a98a0a5aa8c5f85e0fa3d92697c60f0
    wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    wheel_inner_sha256: 13c9c7696f9c657243af1133731bf58600cffb3a78f77bede606a1b00a6c2c79
    artifact_id: 9968172160
    artifact_archive_digest: sha256:2b746b43237d221331ba6418459b2d2d3f62dfc3eaf98d4e3897384787bbefa6
pipeline_child_baseline:
  pull_request: 104
  merge_sha: 94cc0c90631a6582c8ba84911bc100195e2fbb86
  main_ci_actions: 33959169173
  milestone: reusable seven-parameter Fabric Pipeline child validates exact config/plan identity and persists the durable Framework DatasetDispatchOutcome
historical_first_company_fabric_artifact:
  pull_request: 99
  merge_sha: 303683729c4915d78200d463a6def01c8de9eae6
  final_pr_ci_actions: 33381590800
  main_ci_actions: 33381666892
  tests: 753
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
  evidence_class: historical_old_bytes_only
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
previous_manual_code_baseline:
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
manual_certification_contract:
  historical_framework_pr: 99
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
  merged_unified_certification_pr_20_main: 5b063a6318c3cc510a69181a53a47266309b8c14
  merged_pipeline_reference_pr_21_main: cedba6673f08ddfda9cae2e29a27cc6ecc768b58
  pr_21_customer_ci: 33962244955
  pr_21_certification_contract_ci: 33962244950
  pr_21_main_customer_ci: 33962296475
  pr_21_main_certification_contract_ci: 33962296508
  certification_framework_sha: cb9f9be77a98a0a5aa8c5f85e0fa3d92697c60f0
  released_runtime_pin: fabric-data-framework==0.3.0
  reusable_certification_pipeline_source_merged: true
  reusable_certification_pipeline_deployed_in_company_fabric: false
  actual_selected_candidate_input_artifact_retained: false
  real_control_plane_external_evidence_retained: false
  review_bound_control_plane_evidence_retained: false
  real_warehouse_fault_controller_configured: false
```

## Release decision

`0.4.0` remains **UNRELEASED**, feature-frozen, not release-allowed, and without a selected/frozen exact candidate. Current substantive executable Framework source is PR #105, merge SHA `cb9f9be77a98a0a5aa8c5f85e0fa3d92697c60f0`; PR CI `33961766325` and independent main CI `33961827610` both succeeded. Its exact main wheel SHA256 is `13c9c7696f9c657243af1133731bf58600cffb3a78f77bede606a1b00a6c2c79`, artifact `9968172160`.

PR #105 makes the public one-call certification runtime self-consistent: approved runners and exact Customer/domain extensions observe the same runner-declared runtime values within one scoped call, and the previous process environment is restored afterward. Its explicit first-time dedicated Control Plane path requires bounded PASS plus exact Customer identity before schema and exact semantic metadata are materialized. PR #105 itself did not contact company Fabric and has **no real-Fabric execution evidence yet**.

PR #104 remains the durable Pipeline-child milestone: exact seven-parameter correlation, exact DatasetConfig/effective-config/execution-plan verification, and durable Framework-owned `DatasetRunAudit`/`DatasetDispatchOutcome`. Provider `Completed` without the matching Framework outcome is not PASS.

PR #99 is **not current code**. It is the historical first company-Fabric bounded evidence baseline only. Its exact wheel executed successfully for the checks recorded below, and those facts remain valid only for PR #99 bytes. They cannot be reused for PR #104/#105 bytes.

PR #97 remains the original Notebook/manual certification and GitHub Admin Override feature baseline: merge SHA `3b39448fcefbeba7a66469c847542c3255e462ff`, PR CI `33377064054`, main CI `33377208722`, 748 tests, candidate-capable wheel SHA256 `5d0c2f1f4348543bb8b9da0748788cc68b3ccbfed96fd73cec11ad7f475c0517`, artifact `9752314929`.

PR #94 remains the historical release-proof/domain-binding cleanup baseline: merge SHA `abc8b3a2b80b3f6babf88fdc2347a3bfe69be356`, PR CI `33357795244`, main CI `33357846835`, 738 tests, candidate-capable wheel SHA256 `d763cd4410a69ff6a83c492f3a546d096502c96c87eeddb37c2ae9404557e7b7`, artifact `9745697101`. Its identity-chain guarantees remain part of current source.

Documentation-only recovery checkpoint commits do not become new executable candidate baselines merely by changing the repository SHA. The substantive executable Framework baseline remains PR #105 until Framework source bytes change.

Ordinary CI still has no complete release proof or live certified integration manifest, so `release_ready=false` with 15 required blockers remains correct. No current claim is `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, or evidence-based `RELEASE PROVEN` for 0.4.

## Current exact Framework artifact for the next real-Fabric execution

The next real-Fabric run must use the exact PR #105 successful-main artifact unless executable Framework source changes again:

```text
framework-ci main run          33961827610
candidate_git_sha              cb9f9be77a98a0a5aa8c5f85e0fa3d92697c60f0
artifact name                  framework-wheel-cb9f9be77a98a0a5aa8c5f85e0fa3d92697c60f0
artifact ID                    9968172160
wheel filename                 fabric_data_framework-0.4.0-py3-none-any.whl
wheel inner SHA256             13c9c7696f9c657243af1133731bf58600cffb3a78f77bede606a1b00a6c2c79
artifact ZIP digest            sha256:2b746b43237d221331ba6418459b2d2d3f62dfc3eaf98d4e3897384787bbefa6
selected as frozen candidate   false
real-Fabric execution          NOT YET
```

The artifact contains the exact wheel plus `CANDIDATE.json` and `SHA256SUMS`. The uploaded ZIP digest is transport metadata and is never interchangeable with the inner wheel SHA256.

## Historical first company Fabric bounded execution — 2026-09-03 / PR #99 bytes only

Canonical detailed checkpoint:

```text
docs/machine/FIRST_COMPANY_FABRIC_TEST_2026-09-03.md
```

Exact historical artifact:

```text
framework-ci main run          33381666892
candidate_git_sha              303683729c4915d78200d463a6def01c8de9eae6
artifact name                  framework-wheel-303683729c4915d78200d463a6def01c8de9eae6
artifact ID                    9753976212
wheel filename                 fabric_data_framework-0.4.0-py3-none-any.whl
wheel inner SHA256             0638c95c19ebcc43ec4ec462b7f960a164209874223517e3f74b951264b0eaf6
artifact ZIP digest            sha256:cd790310378d8aa11e950b004c9183125c52bbbc0ddf484d7749faa675e7171b
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

A dedicated DEV Warehouse existed, but the bounded lane did not substitute an ad-hoc SQL test for the approved Warehouse runner. Session-termination/fault-injection authorization was not confirmed, so both Warehouse checks remain `NOT_RUN`.

The manual record was created in company Fabric DEV with `missing_fields=[notebook_reference]`. Raw JSON is not retained in this repository; this machine checkpoint retains only the non-secret summary.

The certification form remains a **result recorder**, not a test executor. PASS values came from actual cells executed before the form was submitted.

No candidate freeze is required for this bounded pre-freeze compatibility test. Completion of that historical test did not make the evidence-based release lane ready, and it must not be projected onto current PR #105 bytes.

## Notebook / manual / administrator certification — historical feature path retained

Company-Fabric Notebook/manual path remains available as a diagnostic/legacy lane:

```text
exact framework wheel + CANDIDATE.json
-> isolated company Fabric DEV Notebook / default Lakehouse
-> run FIRST_FABRIC_NOTEBOOK_TEST.md cells
-> framework manual-certification UI/API records observed PASS/FAIL/NOT_RUN
-> manual-certification.json
```

When `CANDIDATE.json` is available, Framework auto-fills `framework_version`, the 40-character `candidate_git_sha`, and the 64-character wheel SHA256. Supplying the actual wheel path additionally hashes the wheel bytes and rejects an identity mismatch.

Normal Notebook semantics are fail-closed: without administrator override, an incomplete identity yields `PARTIAL`; a supplied failed check also yields `PARTIAL`; `CERTIFIED` requires exact candidate identity plus at least one supplied check and all supplied checks PASS.

Explicit administrator override semantics remain visible:

```text
status = CERTIFIED
admin_override = true
override_reason = required
missing_fields = retained exactly
executed FAIL checks remain retained as FAIL
```

The GitHub-side convenience workflow remains:

```text
.github/workflows/candidate-admin-certification.yml
```

It requires no Fabric token, Service Principal, SQL connection string, or GitHub-to-company-Fabric connectivity. No administrator override record has been run/retained. Missing evidence is not rewritten as evidence and unrun checks are not claimed to have run.

The evidence-based release workflow remains unchanged by manual/Admin certification. `framework-release` still requires the successful `.github/workflows/candidate-certification.yml` provenance and the normal exact release-readiness/proof/integration artifacts. Admin Override is not accepted as release readiness.

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

PR #94 removes the obsolete public runner-level proof packaging path. `approved_business_path_runner.py` returns only the evaluated execution report. Candidate proof packaging is exclusively owned by `business_path_release_proof.py` and requires the exact customer `ReleaseManifest`. The obsolete `partial_proof_bundle` / `write_business_path_partial_proof_bundle` path is removed. The forbidden shortcut remains: `runner execution report -> candidate proof without exact ReleaseManifest` is removed.

No step above authors live PASS on its own.

## Current Customer certification/deployment source — PR #21

Customer PR #21 is **MERGED + MAIN CI PROVEN** and is the current substantive Customer source for reusable real-Fabric certification Pipeline deployment:

```text
Customer PR                         #21
substantive merge/main SHA          cedba6673f08ddfda9cae2e29a27cc6ecc768b58
PR customer-ci                      33962244955 SUCCESS
PR customer-certification-contract  33962244950 SUCCESS
independent main customer-ci        33962296475 SUCCESS
independent main certification      33962296508 SUCCESS
certification Framework SHA         cb9f9be77a98a0a5aa8c5f85e0fa3d92697c60f0
released runtime pin                fabric-data-framework==0.3.0
Fabric items deployed               false
```

The merged Customer source owns:

```text
certification/fabric_items/render_fabric_items.py
certification/fabric_items/notebook/certification-pipeline-worker.ipynb
certification/fabric_items/pipeline/pipeline-content.template.json
certification/fabric_items/sql/warehouse-certification-fixtures.sql
certification/project/config/certification/pipeline-worker.json
docs/runbooks/DEPLOY_CERTIFICATION_FABRIC_ITEMS.md
```

The Data Pipeline forwards exactly seven Framework correlation parameters. Its worker uses the durable PR #104/#105 Framework child contract; Fabric `Completed` is insufficient without the exact Framework outcome. Business-path driver/observer share the runner-declared `WAREHOUSE_DATABASE_URL` runtime boundary.

Merged source does not mean company Fabric items have been deployed. Actual environment-local Notebook/Pipeline/Copy/Spark item UUIDs must be obtained from the isolated approved DEV deployment before building the exact Customer candidate-input artifact.

The older Customer producer history remains part of the release identity chain:

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

Current Customer source intentionally retains null control-plane evidence/review placeholders plus the invalid Warehouse fault-controller placeholder. Therefore current evidence-based Customer builder truth remains fail-closed:

```text
live_prerequisites_configured=false
live_prerequisite_blockers=
  control_plane_external_evidence_incomplete
  warehouse_real_fault_controller_not_configured
```

`control_plane_external_evidence_not_review_bound` is the later fail-closed state once all seven real evidence references exist but the exact environment/profile review record is missing or mismatched.

No input artifact has been retained for a selected Framework candidate. Customer production/runtime dependency remains exactly `fabric-data-framework==0.3.0` until immutable v0.4.0 exists.

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

### A. Repository recovery checkpoint — current work

Customer PR #21 source is merged + main-CI proven. Framework PR #105 source is merged + main-CI proven. Documentation-only recovery checkpoints may follow, but they do not replace the substantive executable source identities above and do not create new Fabric evidence.

### B. Next company Fabric DEV execution — after recovery docs are settled

```text
1. use exact Framework PR #105 main artifact / wheel SHA256 above
2. deploy Customer PR #21 repository-owned Notebook/Pipeline/fixture surface to isolated approved DEV
3. record actual environment-local item UUIDs
4. build exact Customer certification input artifact for the selected Customer source and exact PR #105 Framework wheel
5. upload exact Framework wheel + CANDIDATE.json + SHA256SUMS + exact customer-inputs
6. run bounded certification first; STOP on any real FAIL
7. for a newly created dedicated Control Plane only, use explicit allow_control_plane_migration=True after bounded PASS
8. continue ordinary live stages only with approved mutations
9. leave missing external evidence/fault-controller stages BLOCKED/NOT_RUN
```

The PR #99 historical PASS values cannot be reused for PR #105 bytes.

### C. Full evidence-based automated release certification — later

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

Do not freeze the historical PR #99 artifact merely because its bounded test passed. The strict lane calls for a NEW exact candidate only after the real environment prerequisites are actually ready.

## Evidence vocabulary boundary

Portable contract CI proves implementation and fail-closed behavior only. Green CI, workflow existence, source scan, candidate-capable wheel, Customer review-binding metadata, source-controlled evidence reference, Notebook dropdown, or Administrator Override does not by itself prove an unexecuted Fabric/control-plane/Warehouse check.

The 2026-09-03 manual lane legitimately records `CERTIFIED` for the executed bounded Notebook checks with exact identity and no Admin Override, but only for the exact PR #99 wheel. That provenance must remain distinguishable from current PR #105 executable source, `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, and evidence-based `RELEASE PROVEN`.
