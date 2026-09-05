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
  pull_request: 109
  merge_sha: 3bd3375b796531e5ca6c7e144e7f50e154cec29f
  milestone: canonical enterprise Fabric SQL Database control plane with DEV/UAT/PROD topology parity; Lakehouse medallion data plane; optional Warehouse Gold serving
  final_pr_ci_actions: 33997830902
  main_ci_actions: 33997925998
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  live_fabric_evidence_retained_for_current_bytes: false
  current_main_artifact:
    selected_as_frozen_candidate: false
    workflow_run_id: 33997925998
    workflow_run_attempt: 1
    candidate_git_sha: 3bd3375b796531e5ca6c7e144e7f50e154cec29f
    wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    wheel_inner_sha256: fe9adb12d9804dd146957dfc84925b18330edd0c189e5f713867e8e7e9478178
    artifact_id: 9978610894
    artifact_archive_digest: sha256:6e9fa87f8472ffb61cf1b7319160cc4b0b23ab6e9559731446e8ae4f2f381830
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
  pr_25_customer_ci: 33969274525
  pr_25_certification_contract_ci: 33969274509
  pr_25_main_customer_ci: 33969382068
  pr_25_main_certification_contract_ci: 33969382063
  pr_27_customer_ci: 33998332579
  pr_27_certification_contract_ci: 33998332576
  pr_27_main_customer_ci: 33998361497
  pr_27_main_certification_contract_ci: 33998361592
  pr_28_main_customer_ci: 33998526517
  pr_28_main_certification_contract_ci: 33998526504
  certification_framework_sha: 3bd3375b796531e5ca6c7e144e7f50e154cec29f
  released_runtime_pin: fabric-data-framework==0.3.0
  reusable_certification_pipeline_source_merged: true
  reusable_certification_pipeline_deployed_in_company_fabric: false
  product_pipeline_operations_reference_merged: true
  execution_group_policy_examples_ci_proven: true
  enterprise_topology_customer_update_in_progress: false
  enterprise_topology_customer_alignment_main_ci_proven: true
  actual_selected_candidate_input_artifact_retained: false
  real_control_plane_external_evidence_retained: false
  review_bound_control_plane_evidence_retained: false
  real_warehouse_fault_controller_configured: false
```

## Release decision

`0.4.0` remains **UNRELEASED**, feature-frozen, not release-allowed, and without a selected/frozen exact candidate.

Current substantive executable Framework source is PR #109, merge SHA `3bd3375b796531e5ca6c7e144e7f50e154cec29f`. Final PR CI `33997830902` and independent main CI `33997925998` succeeded on Python 3.11/3.13, build-wheel and release-readiness contract. Its exact main wheel SHA256 is `fe9adb12d9804dd146957dfc84925b18330edd0c189e5f713867e8e7e9478178`, artifact `9978610894`, archive digest `sha256:6e9fa87f8472ffb61cf1b7319160cc4b0b23ab6e9559731446e8ae4f2f381830`.

PR #109 makes the Microsoft Fabric enterprise reference topology explicit and executable: DEV/UAT/PROD all use `fabric_sql_database_v1` as the Framework operational Control Plane backend. Lakehouse/OneLake owns the medallion business data plane and governed quarantine detail. Fabric Warehouse is optional for SQL-first Gold/dimensional serving. Runtime state is environment-local and is never promoted from DEV to UAT/PROD.

PR #107 remains the product Pipeline operations milestone and all of its capabilities remain present in current source: dataset/provider fault boundaries isolate siblings, failed dependencies become `BLOCKED`, independently runnable work continues, and default `FAIL_AT_END` only marks the parent `FAILED` after aggregation. It also owns `ExecutionGroupPolicy`, bounded group concurrency, DQ/quarantine defaults and per-dataset patches, quarantine budgets, governed FULL quarantine detail, aggregate error persistence, and conservative RETRY/REPLAY/BACKFILL/FULL_REBUILD/UNKNOWN_COMMIT recovery planning. PR #107 is no longer current executable identity.

PR #105 remains the one-call runtime/Control Plane bootstrap milestone. PR #104 remains the durable Pipeline-child milestone. Their old artifacts are not current executable identity.

PR #99 is **not current code**. It is historical first-company-Fabric evidence for old bytes only. Its bounded PASS cannot be reused for PR #109 bytes.

Documentation-only recovery checkpoints after PR #109 do not become new executable candidate baselines merely because their Git SHA changes. The exact next real-Fabric executable artifact remains the successful PR #109/main wheel unless executable Framework source changes again.

Ordinary CI still has no complete release proof or live certified integration manifest, so `release_ready=false` with 15 required blockers remains correct. No current claim is `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, or evidence-based `RELEASE PROVEN` for 0.4.

## Current exact Framework artifact for the next real-Fabric execution

```text
framework-ci main run          33997925998
candidate_git_sha              3bd3375b796531e5ca6c7e144e7f50e154cec29f
artifact name                  framework-wheel-3bd3375b796531e5ca6c7e144e7f50e154cec29f
artifact ID                    9978610894
wheel filename                 fabric_data_framework-0.4.0-py3-none-any.whl
wheel inner SHA256             fe9adb12d9804dd146957dfc84925b18330edd0c189e5f713867e8e7e9478178
artifact ZIP digest            sha256:6e9fa87f8472ffb61cf1b7319160cc4b0b23ab6e9559731446e8ae4f2f381830
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

Customer PR #25 is the 100-table product operations reference. Customer PR #27/#28 make the enterprise topology and PR #109 compatibility lane canonical and main-CI proven. Customer production still remains exactly `fabric-data-framework==0.3.0`.

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

No candidate freeze is required for that bounded pre-freeze compatibility test. Completion did not make the evidence-based release lane ready and cannot be projected onto current PR #109 bytes.

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

Enterprise topology/compatibility alignment is now **MERGED + MAIN CI PROVEN**:

```text
Customer PR #27 substantive merge/main    fa495fce622de8a5344bf74ecc52885fe85596f4
PR #27 customer-ci                        33998332579 SUCCESS
PR #27 certification-contract             33998332576 SUCCESS
PR #27 main customer-ci                   33998361497 SUCCESS
PR #27 main certification-contract        33998361592 SUCCESS
Customer PR #28 docs checkpoint main      9488b1b4b1f1f90a750bee66fee0c7b373c1839a
PR #28 main customer-ci                   33998526517 SUCCESS
PR #28 main certification-contract        33998526504 SUCCESS
certification Framework SHA               3bd3375b796531e5ca6c7e144e7f50e154cec29f
```

PR #27 makes `fabric_sql_database_v1` canonical for the Customer enterprise DEV/UAT/PROD Control Plane, documents Lakehouse/OneLake as the medallion data plane and Warehouse as optional SQL-first Gold serving, and moves `customer-certification-contract` to exact Framework PR #109. PR #28 makes that merged state recoverable from Customer `main`.

Customer PR #25 remains the 100-table product operations reference. Customer PR #23 remains the certification/Fabric-item deployer implementation milestone. The reusable certification Pipeline source is merged but is not yet evidenced as deployed in company Fabric.

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

### A. Source/recovery alignment

```text
COMPLETED
Framework PR #109 enterprise topology                 MERGED + MAIN CI PROVEN
Framework PR #110 recovery checkpoint                 MERGED + MAIN CI PROVEN
Customer PR #27 enterprise topology/compatibility     MERGED + MAIN CI PROVEN
Customer PR #28 recovery checkpoint                   MERGED + MAIN CI PROVEN
Customer production pin                              unchanged at v0.3.0
```

### B. Next company Fabric DEV execution

```text
1. use exact Framework PR #109 main artifact / wheel SHA256 above
2. use Customer PR #27 substantive topology baseline / current Customer main
3. provision/use a dedicated DEV Fabric SQL Database as canonical Framework Control Plane
4. deploy repository-owned certification Notebook/Pipeline only in isolated approved DEV
5. record/resolve actual environment-local item UUIDs
6. build exact Customer certification inputs for exact Customer SHA + PR #109 Framework wheel
7. upload exact Framework wheel + CANDIDATE.json + SHA256SUMS + exact customer-inputs
8. run bounded certification first; STOP on any real FAIL
9. for a newly created dedicated Control Plane only, use explicit allow_control_plane_migration=True after bounded PASS
10. continue ordinary live stages only with approved mutations
11. leave missing external evidence/fault-controller stages BLOCKED/NOT_RUN
```

PR #99 historical PASS values cannot be reused for PR #109 bytes.

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

The 2026-09-03 manual lane legitimately records `CERTIFIED` for exact PR #99 bounded Notebook checks with exact identity and no Admin Override, but only for PR #99 bytes. That provenance remains distinct from current PR #109 executable source, `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, and evidence-based `RELEASE PROVEN`.
