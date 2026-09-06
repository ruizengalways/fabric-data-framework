# MACHINE STATE — fabric-data-framework

This file is the single recovery checkpoint for current Framework engineering state.

**GitHub `main` is truth.** Do not reconstruct the current candidate from old PRs, old Fabric test records, chat history, or Git history. Git history is only for archaeology when explicitly needed.

```yaml
schema: fabric-data-framework-machine-state-v2
updated: 2026-09-06

release:
  public_release: v0.3.0
  source_version: 0.4.0-development-unreleased
  feature_freeze: true
  candidate_status: not_frozen
  release_allowed: false
  strict_release_ready: false
  readiness_required_blockers: 15

executable_baseline:
  source_pr: 112
  source_sha: 17fbbd8ed2afb14771748a25d3e12d9bf63fe986
  pr_ci_run: 34010577594
  main_ci_run: 34010629765
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  artifact_id: 9982333832
  artifact_name: framework-wheel-17fbbd8ed2afb14771748a25d3e12d9bf63fe986
  wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
  wheel_sha256: 0d7d351548712db3293b00a3b8eb968387f573b542d8fe506c9436a1b9b0a834
  artifact_zip_digest: sha256:07e6f54e9fa4a9b93f4536afd2d0f59754cde4fd33bd26dd3a15ae4b8c2b9791
  selected_as_frozen_candidate: false
  live_fabric_evidence_retained_for_current_bytes: false
  real_fabric_execution: NOT_YET

enterprise_topology:
  environments: [DEV, UAT, PROD]
  canonical_control_plane: Fabric SQL Database
  canonical_control_plane_profile: fabric_sql_database_v1
  medallion_data_plane: Lakehouse / OneLake
  warehouse_role: optional SQL-first Gold / dimensional serving
  same_logical_topology_required: true
  runtime_state_promoted_between_environments: false

fabric_native_auth:
  sql_runtime_default: fabric-user
  sql_identity: signed-in Fabric Notebook user via Microsoft Entra
  key_vault_required_for_default_lane: false
  key_vault_optional: true
  normal_user_implies_warehouse_session_control: false

customer_contract:
  customer_main_sha: 93ef6c0142d57d447a6ca85afce089406ff6b00a
  customer_main_ci: 34025700377
  customer_main_certification_contract_ci: 34025700373
  production_runtime_pin: fabric-data-framework==0.3.0
  certification_framework_sha: 17fbbd8ed2afb14771748a25d3e12d9bf63fe986
  fabric_rest_auth_default: azure-cli
  sql_runtime_auth_default: fabric-user
  repository_owned_certification_notebook_deployed: false
  repository_owned_certification_pipeline_deployed: false
  current_framework_real_fabric_certification_executed: false
  actual_selected_candidate_input_artifact_retained: false

strict_evidence:
  real_control_plane_external_evidence_retained: false
  review_bound_control_plane_evidence_retained: false
  real_warehouse_fault_controller_configured: false
  blockers:
    - control_plane_external_evidence_incomplete
    - control_plane_external_evidence_not_review_bound
    - warehouse_real_fault_controller_not_configured

next_boundary:
  environment: isolated DEV Fabric
  action: deploy and execute the repository-owned certification Notebook and Pipeline with the exact executable artifact above
  stop_on_real_fail: true
```

## Recovery interpretation

The current repository `main` may contain documentation/test-only commits after the executable baseline. Those commits **do not create a new executable candidate**. Until executable Framework source changes, the exact bytes for the next real-Fabric run remain the artifact recorded under `executable_baseline`.

The Customer repo is already aligned to the current Fabric-native path, but merged source is not proof of company-Fabric deployment. There is still no retained evidence that the repository-owned certification Notebook/Pipeline were deployed or that the current Framework bytes were executed in real Fabric.

## Next action

Do not create another recovery/checkpoint PR just to record history. The next engineering boundary is:

```text
exact Framework artifact above
+ current fabric-customer main
-> isolated DEV Fabric
-> deploy certification Notebook + Pipeline
-> retain real item UUIDs / definition hashes
-> run bounded certification
-> STOP on any real FAIL
-> continue only explicitly approved live stages
-> retain genuine evidence
```

Production stays on `fabric-data-framework==0.3.0` until immutable Framework `v0.4.0` exists and strict release governance authorizes migration.
