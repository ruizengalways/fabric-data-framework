# Engineering state

This file is the **single current-state recovery checkpoint** for `fabric-data-framework`. Git history is the historical record; do not create PR-by-PR state documents.

```yaml
schema: fabric-data-framework-state-v4
updated: 2026-09-07

release:
  public_release: v0.3.0
  source_version: 0.4.0-development-unreleased
  candidate_status: not_frozen
  release_allowed: false
  real_fabric_status: FABRIC_CERTIFICATION_REQUIRED

candidate_identity:
  framework_artifact_sha256: not_selected_for_current_source
  integration_inputs_hash: not_selected_for_current_source
  current_source_requires_new_exact_artifact_before_release_claim: true

repository_boundaries:
  framework:
    repo: ruizengalways/fabric-data-framework
    owns:
      - reusable_framework
      - package_lifecycle
      - installed_wheel_certification
      - real_fabric_framework_certification
      - framework_owned_integration_inputs
      - candidate_release_evidence
  customer_simulator:
    repo: ruizengalways/fabric-customer
    framework_dependency_allowed: false
    owns:
      - deterministic_source_facts
      - source_delivery_behavior
      - expected_business_truth
      - workload_digest
  implementation_domain_repo:
    per_real_project: true
    may_depend_on_approved_framework_wheel: true
    owns:
      - DatasetConfig
      - project_mappings_and_rules
      - execution_groups
      - environment_bindings
      - project_deployment_content
      - implementation_adapters
  infrastructure:
    owns:
      - Fabric_capacity
      - workspaces
      - permissions

enterprise_topology:
  environments: [DEV, UAT, PROD]
  canonical_control_plane: Fabric SQL Database
  canonical_control_plane_profile: fabric_sql_database_v1
  medallion_data_plane: Lakehouse / OneLake
  warehouse_role: optional SQL-first Gold / dimensional serving
  warehouse_platform: Fabric Warehouse
  same_logical_topology_required: true
  promote_runtime_state_between_environments: false

certification:
  source_tests: required
  exact_wheel_build: required
  installed_wheel_attestation: required
  installed_semantic_smoke: required
  bounded_real_fabric: required_for_fabric_claim
  environment_dependent_integration: explicit_configuration_and_authorization
  release_authorized_by_certification_runner: false
  identity:
    - framework_artifact_sha256
    - integration_inputs_hash

fabric_proof:
  exact_current_candidate_selected: false
  bounded_lakehouse_for_current_candidate: not_retained
  control_plane_for_current_candidate: not_retained
  pipeline_copy_spark_for_current_candidate: not_retained
  warehouse_commit_recovery_for_current_candidate: not_retained
  representative_business_paths_for_current_candidate: not_retained
  status_label: FABRIC_CERTIFICATION_REQUIRED

next_boundary:
  - finish source/contract CI for the current hard-cut candidate-certification architecture
  - build and retain a new exact main wheel for current executable source
  - record framework_artifact_sha256 and integration_inputs_hash
  - install the exact wheel in isolated DEV Fabric
  - run certify_installed bounded first
  - stop on any real FAIL
  - run only explicitly required/authorized integration stages
  - retain exact-identity evidence
```

## Current architecture interpretation

Framework certification is fully framework-owned. The candidate/evidence chain uses:

```text
framework_artifact_sha256
+
integration_inputs_hash
```

No customer/domain release identity participates in framework candidate certification, and the framework release workflows do not depend on `fabric-customer` to produce certification inputs.

`fabric-customer` remains useful as an independent realistic source simulator. When an implementation compares framework versions against the same scenario, record the same verified `workload_digest`; that identity is independent from the framework wheel SHA.

## Real Fabric boundary

Do not upgrade local or CI proof into a Fabric claim. For the current executable source, real Fabric evidence has not been retained for a selected exact candidate.

```text
source/contract proof        != real Fabric proof
installed-wheel acceptance   != real Fabric proof
provider Completed            != framework semantic PASS
```

Until a new exact current-source wheel is selected and executed in Fabric, the status remains:

```text
FABRIC CERTIFICATION REQUIRED
```

## Release boundary

`0.4.0` is not frozen and not release-authorized. Any exact wheel previously built from older executable source may still be useful as historical/test evidence for those bytes, but it does not certify the current executable source after code changes.

Release promotion must use the exact already-built/certified wheel bytes; no release-time wheel rebuild.

## Documentation rule

Canonical user documentation is under `docs/*.md`; narrow contracts are under `docs/reference/`. Only three engineering-recovery documents live under `docs/internal/`:

```text
STATE.md
CAPABILITIES.md
IMPLEMENTATION_MAP.md
```

Do not add another state/evidence narrative document when code, executable schemas, one canonical topic doc, or one of these three internal files can own the information.
