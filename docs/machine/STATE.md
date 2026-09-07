# MACHINE STATE — fabric-data-framework

This file is the single recovery checkpoint for current Framework engineering state.

**GitHub `main` is truth.** Do not reconstruct current architecture from old PRs, old Customer certification bundles, chat history or historical Fabric runs. Git history is for archaeology only.

```yaml
schema: fabric-data-framework-machine-state-v3
updated: 2026-09-07

release:
  public_release: v0.3.0
  source_version: 0.4.0-development-unreleased
  candidate_status: not_frozen
  release_allowed: false
  strict_release_ready: false
  readiness_required_blockers: 15
  real_fabric_execution_for_current_executable: NOT_YET

executable_baseline:
  # Exact main artifact selected as the next real-Fabric baseline.
  git_sha: 38741777955ffdb59cf9bdeea361bdd6651c5ee2
  main_ci_run: 34091549404
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success_fail_closed
  installed_wheel_acceptance_run: 34091549510
  installed_wheel_acceptance: success
  artifact_id: 10006992444
  artifact_name: framework-wheel-38741777955ffdb59cf9bdeea361bdd6651c5ee2
  wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
  wheel_sha256: 201947410f75b88596af897c78d6fd056a9a3040fbec4d83d85b5439d7077cf0
  artifact_zip_digest: sha256:7f418fe8d099d5a0b3cd1fffa656d8217496fea4845259064d9cd88d639d78ec
  readiness_artifact_id: 10006996671
  readiness_artifact_digest: sha256:053c3ea4a0d85ea5809b94be9b8517a837c5c9af2f783e086957d22a2d49f520
  selected_as_frozen_candidate: false
  live_fabric_evidence_retained_for_exact_wheel: false

repository_boundaries:
  framework:
    repo: ruizengalways/fabric-data-framework
    owns:
      - reusable_processing_framework
      - package_lifecycle
      - installed_wheel_certification
      - real_fabric_framework_certification
  customer_simulator:
    repo: ruizengalways/fabric-customer
    main_sha: 71c6c083e25cd133488d59318a856f7822f670f5
    main_ci_run: 34095079211
    main_ci: success
    version: 0.2.0
    framework_dependency_allowed: false
    owns:
      - deterministic_source_facts
      - source_delivery_behavior
      - expected_business_truth
      - workload_integrity_digest
  implementation_domain_repo:
    per_real_project: true
    may_depend_on_approved_framework_wheel: true
    owns:
      - DatasetConfig
      - project_mappings_and_rules
      - environment_bindings
      - project_deployment_content
      - implementation_adapters
  infra:
    repo_role: Fabric_capacity_workspace_permission_lifecycle

customer_workload_contract:
  framework_agnostic: true
  canonical_seed: 20260907
  scenario_days: 7
  source_modes:
    - snapshot
    - incremental
    - debezium_shaped_cdc
  integrity_files:
    - SHA256SUMS
    - WORKLOAD.json
  verification_command: fabric-customer verify --output <materialized-root>
  framework_v1_v2_comparison_requires_same_workload_digest: true

enterprise_topology:
  environments: [DEV, UAT, PROD]
  canonical_control_plane: Fabric SQL Database
  canonical_control_plane_profile: fabric_sql_database_v1
  medallion_data_plane: Lakehouse / OneLake
  warehouse_role: optional SQL-first Gold / dimensional serving
  same_logical_topology_required: true
  runtime_state_promoted_between_environments: false

certification_lifecycle:
  source_tests: framework_repo_tests
  wheel_build: exact_main_artifact
  installed_wheel_attestation: required
  installed_semantic_smoke: required
  bounded_real_fabric: required_for_real_fabric_claim
  environment_dependent_integration: explicit_configuration_and_authorization
  release_authorized_by_certification_runner: false
  legacy_names:
    customer_inputs: optional_framework_certification_integration_bundle
    customer_compatibility_gate: deprecated_serialized_readiness_name

fabric_status:
  exact_framework_wheel_installed_in_real_dev_fabric: not_retained
  lakehouse_bounded_certification: not_retained
  control_plane_certification: not_retained
  pipeline_copy_spark_integration: not_retained
  warehouse_commit_recovery: not_retained
  status_label: FABRIC_CERTIFICATION_REQUIRED

next_boundary:
  environment: isolated DEV Fabric
  action: install exact executable-baseline wheel in a dedicated Fabric Environment, publish/restart runtime, run certify_installed bounded first, stop on any real FAIL, then explicitly configure only required integration resources
  stop_on_real_fail: true
```

## Recovery interpretation

### 1. Do not resurrect the removed Customer certification architecture

The current `fabric-customer` main is an independent source-system simulator. It does **not** pin or import `fabric-data-framework`, does not own Framework DatasetConfig, and does not own Framework certification bootstrap.

Historical names such as:

```text
customer-inputs
--customer-inputs
customer.compatibility
```

may still exist in Framework compatibility surfaces or serialized readiness contracts. Interpret them as deprecated names for optional Framework integration/candidate contracts, not as repository ownership by `fabric-customer`.

### 2. Exact artifact baseline is separate from documentation HEAD

The exact artifact selected for the next real-Fabric run was built from Framework SHA:

```text
38741777955ffdb59cf9bdeea361bdd6651c5ee2
```

A later documentation-only commit does not change Framework package source/payload. CI may nevertheless rebuild a wheel and emit a different artifact/CANDIDATE identity. That does not automatically replace this selected baseline. If the artifact chosen for Fabric changes—or executable package content changes—update this section with the exact new main artifact and installed-wheel acceptance result before claiming evidence for it.

### 3. Current local/CI proof

For the exact selected artifact baseline:

```text
Framework source CI                PASS
Framework wheel build              PASS
Framework clean installed-wheel    PASS
Framework real Fabric              REQUIRED / NOT RETAINED
```

For the current Customer simulator main:

```text
no framework dependency            PASS
unit/architecture tests            PASS
full Ruff                          PASS
wheel build/install                PASS
deterministic materialize/verify   PASS
real Fabric simulator execution    REQUIRED / NOT RETAINED
```

### 4. Release readiness remains fail-closed

The current readiness contract still reports 15 required blockers because real environment/evidence gates have not been retained for the exact Framework wheel. One legacy gate is named `customer.compatibility`; this is a compatibility field name, not a requirement that the current `fabric-customer` repo become framework-coupled again.

Do not mark `v0.4.0` ready merely because source CI and installed-wheel acceptance are green.

## Next action

The next engineering boundary is **real Fabric execution**, not another simulator/certification ownership refactor:

```text
exact Framework wheel SHA256
201947410f75b88596af897c78d6fd056a9a3040fbec4d83d85b5439d7077cf0

-> isolated DEV Fabric Environment
-> install exact wheel
-> Publish / restart runtime
-> attach dedicated certification Lakehouse
-> stage matching CANDIDATE.json + wheel under Files/framework_cert
-> run certify_installed(...)
-> require exact installed-byte identity PASS
-> require bounded Lakehouse checks PASS
-> STOP on any real FAIL
-> configure Control Plane / Pipeline / Copy / Spark / Warehouse only for explicitly required later stages
-> retain exact-wheel evidence
```

Separately, `fabric-customer` may materialize one verified production-like workload. Record its `workload_digest` when using it for framework v1/v2 or implementation regression evidence.

Public production/release status remains `v0.3.0` until immutable `v0.4.0` is explicitly authorized and published.
