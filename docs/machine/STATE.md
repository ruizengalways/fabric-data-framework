# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-09-06
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
feature_freeze: true
candidate_status: not_frozen
code_baseline:
  pull_request: 112
  merge_sha: 17fbbd8ed2afb14771748a25d3e12d9bf63fe986
  milestone: Fabric-native Entra SQL runtime on canonical enterprise Fabric SQL Database topology while preserving approved runner authorization gates
  final_pr_ci_actions: 34010577594
  main_ci_actions: 34010629765
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  live_fabric_evidence_retained_for_current_bytes: false
  current_main_artifact:
    selected_as_frozen_candidate: false
    workflow_run_id: 34010629765
    workflow_run_attempt: 1
    candidate_git_sha: 17fbbd8ed2afb14771748a25d3e12d9bf63fe986
    wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    wheel_inner_sha256: 0d7d351548712db3293b00a3b8eb968387f573b542d8fe506c9436a1b9b0a834
    artifact_id: 9982333832
    artifact_archive_digest: sha256:07e6f54e9fa4a9b93f4536afd2d0f59754cde4fd33bd26dd3a15ae4b8c2b9791
historical_framework_executable:
  pull_request: 109
  merge_sha: 3bd3375b796531e5ca6c7e144e7f50e154cec29f
  main_ci_actions: 33997925998
  artifact_id: 9978610894
  wheel_inner_sha256: fe9adb12d9804dd146957dfc84925b18330edd0c189e5f713867e8e7e9478178
  real_fabric_execution_status: NOT YET
  current_executable_identity: false
enterprise_topology:
  canonical_control_plane_profile: fabric_sql_database_v1
  enterprise_environments: [DEV, UAT, PROD]
  same_logical_topology_required: true
  lakehouse_as_enterprise_canonical_control_plane: false
  medallion_data_plane: Lakehouse / OneLake
  warehouse_role: optional SQL-first Gold / dimensional serving
  runtime_state_promoted_between_environments: false
  canonical_machine_doc: docs/machine/ENTERPRISE_TOPOLOGY.md
  canonical_human_doc: docs/human/ENTERPRISE_FABRIC_ARCHITECTURE.md
product_pipeline_operations_baseline:
  pull_request: 107
  merge_sha: 4c8ad9994f3800e901c146b919f85454d78f080e
  final_pr_ci_actions: 33967940246
  main_ci_actions: 33968014547
  wheel_inner_sha256: 06d4a9ca948693c87a658a34e8c4fccb42439a7f9f67c44985ac726dedb4e04d
  artifact_id: 9970044954
  milestone: FAIL_AT_END, ExecutionGroupPolicy, governed DQ/quarantine budgets/detail, aggregate audit, conservative recovery
  current_executable_identity: false
runtime_bootstrap_baseline:
  pull_request: 105
  merge_sha: cb9f9be77a98a0a5aa8c5f85e0fa3d92697c60f0
  main_ci_actions: 33961827610
  milestone: one-call runtime scope and fail-closed first-time dedicated Control Plane bootstrap
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
  notebook_check_result_states: [NOT_RUN, PASS, FAIL]
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
  merged_deployer_pr_23_main: 88d7c3b7b473ad84b5d96aa472293ae24c055c88
  merged_product_operations_pr_25_main: 1d70fe26baf3ceef1be7c0b0cd359f330316e0ee
  product_operations_checkpoint_pr_26_main: fc224d606eb5833bf75db36bd338dcb7e9d93bb8
  merged_enterprise_topology_pr_27_main: fa495fce622de8a5344bf74ecc52885fe85596f4
  enterprise_topology_checkpoint_pr_28_main: 9488b1b4b1f1f90a750bee66fee0c7b373c1839a
  merged_candidate_input_topology_hardening_pr_29_main: 1effd5fe283afeb5b960a87e64638f1674433580
  candidate_input_checkpoint_pr_30_main: 4676157be2d8203c7cd5a625e9e68540dc12d4ad
  merged_fabric_native_auth_pr_31_main: b8791ee3f7c575e87d457501ea2e93e40d75fcb6
  fabric_native_checkpoint_pr_32_main: 71947122a6cdfd7c4c6bf5e6c677d28f65d48064
  pr_25_customer_ci: 33969274525
  pr_25_certification_contract_ci: 33969274509
  pr_25_main_customer_ci: 33969382068
  pr_25_main_certification_contract_ci: 33969382063
  pr_29_customer_ci: 34001442382
  pr_29_certification_contract_ci: 34001442376
  pr_29_main_customer_ci: 34001481213
  pr_29_main_certification_contract_ci: 34001481204
  pr_30_main_customer_ci: 34001648070
  pr_30_main_certification_contract_ci: 34001648061
  pr_31_customer_ci: 34016083859
  pr_31_certification_contract_ci: 34016083851
  pr_31_main_customer_ci: 34016136469
  pr_31_main_certification_contract_ci: 34016136281
  pr_32_customer_ci: 34016330538
  pr_32_certification_contract_ci: 34016330542
  pr_32_main_customer_ci: 34016357415
  pr_32_main_certification_contract_ci: 34016357443
  historical_framework_next_project_contract_sha: 148e02e3fff7861f238296e7554815a6fd49dd0a
  certification_framework_sha: 17fbbd8ed2afb14771748a25d3e12d9bf63fe986
  released_runtime_pin: fabric-data-framework==0.3.0
  reusable_certification_pipeline_source_merged: true
  reusable_certification_pipeline_deployed_in_company_fabric: false
  repository_owned_certification_notebook_deployed: false
  repository_owned_certification_pipeline_deployed: false
  current_pr112_real_fabric_certification_executed: false
  product_pipeline_operations_reference_merged: true
  execution_group_policy_examples_ci_proven: true
  enterprise_topology_customer_update_in_progress: false
  enterprise_topology_customer_main_ci_proven: true
  candidate_input_canonical_control_plane_profile: fabric_sql_database_v1
  candidate_input_alternate_profile_rejected: true
  fabric_rest_auth_default: azure-cli
  sql_runtime_auth_default: fabric-user
  key_vault_required_for_default_lane: false
  key_vault_optional: true
  env_token_optional: true
  actual_selected_candidate_input_artifact_retained: false
  real_control_plane_external_evidence_retained: false
  review_bound_control_plane_evidence_retained: false
  real_warehouse_fault_controller_configured: false
```

## Release decision

`0.4.0` remains **UNRELEASED**, feature-frozen, not release-allowed, and without a selected/frozen exact candidate.

Current substantive executable Framework source is PR #112, merge SHA `17fbbd8ed2afb14771748a25d3e12d9bf63fe986`. Final successful PR CI `34010577594` and independent main CI `34010629765` succeeded on Python 3.11/3.13, build-wheel and release-readiness contract. Its exact main wheel SHA256 is `0d7d351548712db3293b00a3b8eb968387f573b542d8fe506c9436a1b9b0a834`, artifact `9982333832`, archive digest `sha256:07e6f54e9fa4a9b93f4536afd2d0f59754cde4fd33bd26dd3a15ae4b8c2b9791`.

PR #112 keeps the PR #109 enterprise topology contract and adds the Fabric-native Entra SQL runtime. DEV/UAT/PROD all use `fabric_sql_database_v1` as the Framework operational Control Plane backend; Lakehouse/OneLake owns the medallion business data plane; Fabric Warehouse remains optional SQL-first Gold/dimensional serving. The default Fabric-native SQL lane uses signed-in Fabric Notebook user identity plus non-secret server/database identity and never promotes a normal user identity into Warehouse session-control authority.

PR #109 remains a historical executable predecessor. It had no current-byte real-Fabric execution and its exact artifact remains recoverable only as historical identity. PR #107 remains the product Pipeline operations milestone and all of its capabilities remain present in current source: dataset/provider fault boundaries isolate siblings, failed dependencies become `BLOCKED`, independently runnable work continues, and default `FAIL_AT_END` marks the parent `FAILED` only after aggregation. PR #105 remains the one-call runtime/Control Plane bootstrap milestone; PR #104 remains the durable Pipeline-child milestone.

PR #99 is **not current code**. It is historical first-company-Fabric evidence for old bytes only. Its bounded PASS cannot be reused for PR #112 bytes.

Documentation-only recovery checkpoints after PR #112 do not become new executable candidate baselines merely because their Git SHA changes. The exact next real-Fabric executable artifact remains the successful PR #112/main wheel unless executable Framework source changes again.

Ordinary CI still has no complete release proof or live certified integration manifest, so `release_ready=false` with 15 required blockers remains correct. No current claim is `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, or evidence-based `RELEASE PROVEN` for 0.4.

## Current exact Framework artifact for the next real-Fabric execution

```text
framework-ci main run          34010629765
candidate_git_sha              17fbbd8ed2afb14771748a25d3e12d9bf63fe986
artifact name                  framework-wheel-17fbbd8ed2afb14771748a25d3e12d9bf63fe986
artifact ID                    9982333832
wheel filename                 fabric_data_framework-0.4.0-py3-none-any.whl
wheel inner SHA256             0d7d351548712db3293b00a3b8eb968387f573b542d8fe506c9436a1b9b0a834
artifact ZIP digest            sha256:07e6f54e9fa4a9b93f4536afd2d0f59754cde4fd33bd26dd3a15ae4b8c2b9791
selected as frozen candidate   false
real-Fabric execution          NOT YET
```

The artifact contains the exact wheel plus `CANDIDATE.json` and `SHA256SUMS`. The uploaded ZIP digest is transport metadata and is never interchangeable with the inner wheel SHA256.

## Enterprise Fabric topology contract

Canonical architecture docs:

```text
docs/human/ENTERPRISE_FABRIC_ARCHITECTURE.md
docs/machine/ENTERPRISE_TOPOLOGY.md
```

Enterprise invariant:

```text
DEV/UAT/PROD: Fabric SQL Database = Framework operational control plane
Bronze/Silver/Gold: Lakehouse / OneLake analytical data plane
Gold SQL/dimensional serving: optional Fabric Warehouse
```

`Bronze / Silver / Gold` are data-maturity layers. `Lakehouse / Warehouse / SQL Database` are workload/storage engines. They are different dimensions.

Delta optimistic concurrency may reject overlapping writes/merges to Lakehouse control tables. That behavior protects Delta correctness but is not the canonical enterprise operational-state workload. Do not develop with Lakehouse control tables in DEV and then switch control-plane semantics during UAT/PROD promotion.

CI/CD promotes code, semantic/config policy, Fabric item definitions and SQL schema/migrations. It does **not** promote `pipeline_run`, `dataset_run`, watermarks/checkpoints, retry/reprocess history, operation-journal state, secrets, physical item IDs or business data.

## Product Pipeline operations / recovery contract

Normal business-Pipeline runbook:

```text
docs/human/PIPELINE_OPERATIONS_AND_RECOVERY.md
```

Default operating model:

```text
one table FAIL
-> durable dataset error
-> independent siblings continue
-> failed dependents BLOCKED
-> all runnable work reaches terminal state
-> parent Pipeline FAILED at end
```

Default recovery classification:

```text
explicit transient + retryable=true -> bounded RETRY
DQ threshold exceeded -> fix data/rule then REPLAY
DQ failure with quarantine disabled -> repair then RETRY
reconciliation failure -> investigate before reprocess
BLOCKED dependency -> recover upstream first
UNKNOWN_COMMIT -> reconcile operation/target evidence before retry
bounded source gap -> BACKFILL
authoritative reset only -> FULL_REBUILD
```

Whole-Pipeline blind retry is not the default incident response. Unknown/ambiguous commit never permits blind retry. Detailed quarantine business rows remain in governed data-plane storage; relational Control Plane stores only lineage/summary/reference.

Customer PR #25 is the 100-table product operations reference. Customer production still remains exactly `fabric-data-framework==0.3.0`.

## Historical first company Fabric bounded execution — 2026-09-03 / PR #99 bytes only

Canonical checkpoint:

```text
docs/machine/FIRST_COMPANY_FABRIC_TEST_2026-09-03.md
```

Exact historical artifact:

```text
framework-ci main run          33381666892
candidate_git_sha              303683729c4915d78200d463a6def01c8de9eae6
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

The reconciliation check deliberately forced underlying reconciliation status to `FAIL`; the certification check passed because Framework returned `blocks_state_advance=true`. A dedicated DEV Warehouse existed, but no ad-hoc SQL was substituted for the approved Warehouse runner and no unauthorized fault injection occurred.

The manual record had `missing_fields=[notebook_reference]`. Raw JSON is not retained in this repository. The certification form remains a **result recorder**, not a test executor. PASS values came from actual executed checks.

No candidate freeze is required for that bounded pre-freeze compatibility test. Completion did not make the evidence-based release lane ready and cannot be projected onto current PR #112 bytes.

## Notebook/manual/Admin certification boundary

The Notebook/manual diagnostic lane remains available. When `CANDIDATE.json` is available, Framework auto-fills exact identity; actual wheel bytes may additionally be hashed and verified.

Administrator override remains explicit:

```text
status = CERTIFIED
admin_override = true
override_reason = required
missing_fields = retained exactly
executed FAIL checks remain retained as FAIL
```

The GitHub-side convenience workflow remains `.github/workflows/candidate-admin-certification.yml`. It requires no Fabric connectivity, does not fabricate missing evidence, and is not accepted by the evidence-based release workflow as release readiness.

## Exact domain identity chain

Framework and Customer release identities remain independent:

```text
framework candidate binary:
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

These values must never be assumed equal.

PR #92 remains **MERGED + MAIN CI PROVEN** for exact domain binding: merge `d5eed17f2ec2f869b4e3a448597e6d8d600568ea`, final PR CI `33356959856`, main CI `33357032461`, 734 tests. Candidate business-path proof packaging remains exclusively owned by `business_path_release_proof.py`, which requires the exact Customer `ReleaseManifest`.

The obsolete `partial_proof_bundle` / `write_business_path_partial_proof_bundle` path is removed. The forbidden shortcut `runner execution report -> candidate proof without exact ReleaseManifest` remains removed.

## Current Customer source alignment

Customer production/runtime dependency remains exactly:

```text
fabric-data-framework==0.3.0
```

Current merged Customer alignment:

```text
PR #27 enterprise topology main       fa495fce622de8a5344bf74ecc52885fe85596f4
PR #29 candidate-input hardening main 1effd5fe283afeb5b960a87e64638f1674433580
PR #31 Fabric-native auth main        b8791ee3f7c575e87d457501ea2e93e40d75fcb6
PR #31 customer-ci                    34016083859 SUCCESS
PR #31 certification-contract        34016083851 SUCCESS
PR #31 main customer-ci               34016136469 SUCCESS
PR #31 main certification-contract    34016136281 SUCCESS
PR #32 recovery checkpoint main       71947122a6cdfd7c4c6bf5e6c677d28f65d48064
PR #32 customer-ci                    34016330538 SUCCESS
PR #32 certification-contract        34016330542 SUCCESS
PR #32 main customer-ci               34016357415 SUCCESS
PR #32 main certification-contract    34016357443 SUCCESS
historical project-contract SHA       148e02e3fff7861f238296e7554815a6fd49dd0a
certification Framework SHA           17fbbd8ed2afb14771748a25d3e12d9bf63fe986
canonical candidate-input profile     fabric_sql_database_v1
Fabric REST auth default              azure-cli
SQL runtime auth default              fabric-user
Key Vault required by default         false
```

The Customer enterprise/candidate-input alignment is complete and independent main-CI proven. PR #31 makes ordinary certification-item deployment Fabric-native: Azure CLI user auth is the default Fabric REST lane, `fabric-user` is the default SQL lane, Key Vault is optional, and `env-token` remains optional for approved automation. PR #32 is docs/tests recovery state and does not replace PR #31 as the substantive Customer auth/deployment baseline.

The historical `FRAMEWORK_NEXT_SHA=148e02e3fff7861f238296e7554815a6fd49dd0a` remains a separate project-contract compatibility lane; current 0.4 certification source tracks PR #112. Customer production dependency remains `fabric-data-framework==0.3.0`.

The reusable certification Pipeline source is merged but neither the repository-owned certification Notebook nor Pipeline is evidenced as deployed in company Fabric, and no real-Fabric certification result exists for PR #112 bytes.

Current fail-closed Customer input truth remains:

```text
actual_selected_candidate_input_artifact_retained: false
control_plane_external_evidence_incomplete
control_plane_external_evidence_not_review_bound
warehouse_real_fault_controller_not_configured
```

## Remaining evidence-based release blockers

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

### A. Source/recovery alignment — complete

```text
Framework PR #112 executable baseline is PR/main-CI proven
Customer PR #27 enterprise topology is main-CI proven
Customer PR #29 candidate-input profile hardening is main-CI proven
Customer PR #31 Fabric-native auth/deployment hardening is main-CI proven
Customer PR #32 recovery checkpoint is main-CI proven
Customer production pin remains fabric-data-framework==0.3.0
next execution boundary is real isolated DEV Fabric
```

### B. Next company Fabric DEV execution

```text
1. use exact Framework PR #112 main artifact / wheel SHA256 above
2. use current Customer main after PR #32 recovery checkpoint
3. use/provision a dedicated DEV Fabric SQL Database as canonical Framework Control Plane
4. run az login with approved operator identity
5. deploy repository-owned certification Notebook/Pipeline only in isolated approved DEV using default azure-cli + fabric-user auth; Key Vault remains optional
6. retain only the non-secret deployment-result.json and actual environment-local item UUIDs
7. build exact Customer certification inputs for exact Customer SHA + PR #112 Framework wheel; profile must be fabric_sql_database_v1
8. upload exact Framework wheel + CANDIDATE.json + SHA256SUMS + exact customer-inputs
9. run bounded certification first; STOP on any real FAIL
10. for a newly created dedicated Control Plane only, use explicit allow_control_plane_migration=True after bounded PASS
11. continue ordinary live stages only with approved mutations
12. leave missing external evidence/fault-controller stages BLOCKED/NOT_RUN
```

PR #99 historical PASS values cannot be reused for PR #112 bytes. PR #109 had no current-byte real-Fabric PASS and is historical only.

### C. Full evidence-based release certification — later

```text
1. obtain reviewed real control-plane external evidence for the protected environment/profile
2. obtain an approved reachable Warehouse/session ambiguous-COMMIT fault controller
3. only after BOTH prerequisite families are genuinely ready, explicitly select/freeze one NEW exact framework candidate
4. produce exact Customer inputs for that candidate + exact Customer SHA
5. run protected candidate integration evidence
6. run all five business-path drills
7. produce release proofs for the same exact framework/domain identities
8. candidate-certify must reach blockers=[] and release_ready=true
9. framework-release promotes the exact already-certified wheel bytes; no rebuild
10. only after immutable v0.4.0 exists consider Customer production migration
```

## Evidence vocabulary boundary

Portable contract CI proves implementation and fail-closed behavior only. Green CI, workflow existence, candidate-capable artifact, source-controlled evidence reference, Notebook UI or Admin Override does not prove an unexecuted Fabric/control-plane/Warehouse check.

The 2026-09-03 manual lane legitimately records `CERTIFIED` for exact PR #99 bounded Notebook checks with exact identity and no Admin Override, but only for PR #99 bytes. That provenance remains distinct from current PR #112 executable source, `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, and evidence-based `RELEASE PROVEN`.
