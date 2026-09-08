# Engineering state

This file is the **single current-state recovery checkpoint** for `fabric-data-framework`. Git history is the historical record; do not create PR-by-PR state documents.

```yaml
schema: fabric-data-framework-state-v4
updated: 2026-09-08

release:
  public_release: v0.3.0
  source_version: 0.4.0-development-unreleased
  candidate_status: not_frozen
  exact_candidate_source_selected: true
  release_allowed: false
  real_fabric_status: FABRIC_CERTIFICATION_REQUIRED

candidate_identity:
  candidate_git_sha: 81f4d5f93983e8288246f5b1521f763091880297
  candidate_main_framework_ci_run: 34216247521
  candidate_main_installed_wheel_run: 34216247544
  candidate_wheel_artifact_id: 10051879910
  candidate_wheel_artifact_name: framework-wheel-81f4d5f93983e8288246f5b1521f763091880297
  candidate_wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
  framework_artifact_sha256: 845f68d938a39ada944a1a71513b4f46b3a68416a5b53d60dbd10c2f6f95327c
  integration_inputs_hash: not_constructed_for_selected_candidate
  integration_inputs_status: blocked_pending_approved_live_DEV_bindings
  current_source_requires_new_exact_artifact_before_release_claim: false
  candidate_bytes_must_not_change: true

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
      - physical_target_version_names
      - provider_specific_logical_target_binding
      - UAT_business_validation_and_approval
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

runtime_recovery:
  rebuild_scope_contract_status: merged_on_main
  rebuild_scope_runtime_merge_sha: 40034aae983c6437cd6c1fbf77217ab8efbc919a
  repair_impact_and_cutover_contract_status: merged_on_main
  repair_impact_and_cutover_runtime_merge_sha: 962a37923d7c74e901d2ff89941a165f6d0d8eb2
  repair_impact_and_cutover_pr_head_sha: 6f0a9fb2cc1bec0ef33d4add9fc3702824e5c989
  repair_impact_and_cutover_pr_ci_status: passed
  repair_impact_and_cutover_main_ci_status: passed
  repair_impact_and_cutover_main_framework_ci_run: 34191016408
  repair_impact_and_cutover_main_installed_wheel_run: 34191016381
  run_modes:
    - RETRY
    - BACKFILL
    - REPLAY
    - FULL_REBUILD
  full_rebuild_scopes:
    - TARGET_ONLY
    - CAPTURE_AND_TARGET
    - AUTHORITATIVE_RESET
  repair_issue_origins:
    TARGET_LOGIC: TARGET_ONLY
    CAPTURE_DATA: CAPTURE_AND_TARGET
    CAPTURE_SEMANTICS: AUTHORITATIVE_RESET
  dependency_impact_rule: root_plus_downstream_descendants_only
  unrelated_branches_rebuilt: false
  downstream_default_rebuild_scope: TARGET_ONLY
  disabled_contaminated_datasets_reported: true
  target_version_cutover:
    stable_logical_object: required
    explicit_physical_version: required
    candidate_built_gate: required
    reconciliation_gate: required
    consumer_uat_validation_gate: required
    approval_reference_match: required
    optimistic_generation_check: required
    same_request_idempotent: true
    old_version_auto_delete: false
  target_only_capture_state_change_allowed: false
  capture_and_target_progress_kind_change_allowed: false
  authoritative_reset_progress_kind_change_allowed: true
  requested_scope_must_equal_completed_scope: true
  target_commit_and_reconciliation_gate_required_before_state_cutover: true
  automatic_business_data_purge_supported: false
  purge_policy: manual_operator_governance_only

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
  exact_current_candidate_selected: true
  selected_candidate_installed_wheel_acceptance: passed
  selected_candidate_real_fabric_execution: not_run
  bounded_lakehouse_for_current_candidate: not_retained
  control_plane_for_current_candidate: not_retained
  pipeline_copy_spark_for_current_candidate: not_retained
  warehouse_commit_recovery_for_current_candidate: not_retained
  representative_business_paths_for_current_candidate: not_retained
  status_label: FABRIC_CERTIFICATION_REQUIRED

external_execution_boundary:
  approved_DEV_workspace_id: not_available_in_current_connected_tooling
  approved_DEV_item_bindings: not_available_in_current_connected_tooling
  Fabric_runtime_credentials: not_available_in_current_connected_tooling
  GitHub_workflow_dispatch_action: not_available_in_current_connected_tooling
  do_not_guess_or_reuse_unverified_resource_ids: true

next_boundary:
  - resolve and live-verify the approved isolated DEV Fabric workspace/lakehouse anchor
  - bootstrap/read back framework-owned certification assets using the exact selected wheel
  - resolve exact item bindings by live Fabric item discovery
  - construct and retain framework-owned integration inputs
  - record integration_inputs_hash for the selected candidate
  - install/attest the exact selected wheel in isolated DEV Fabric
  - run certify_installed bounded first
  - stop on any real FAIL
  - run only explicitly required and authorized integration stages
  - retain exact identity-bound evidence
```

## Current candidate interpretation

One exact executable candidate has now been selected from the successful `main` push CI for source commit:

```text
81f4d5f93983e8288246f5b1521f763091880297
```

The retained CI artifact contains:

```text
fabric_data_framework-0.4.0-py3-none-any.whl
```

and the inner wheel bytes independently match:

```text
framework_artifact_sha256
= 845f68d938a39ada944a1a71513b4f46b3a68416a5b53d60dbd10c2f6f95327c
```

The selected source/main CI provenance is:

```text
framework-ci              34216247521  PASS
installed-wheel-acceptance 34216247544  PASS
```

This selection does **not** freeze or authorize `0.4.0`. The second candidate identity component, `integration_inputs_hash`, has not yet been constructed because the current connected tooling does not expose a live verified isolated DEV Fabric workspace/lakehouse anchor, item bindings, or Fabric runtime credentials. Those values must not be guessed or copied from stale evidence.

Framework certification remains fully framework-owned. The complete candidate/evidence identity is still:

```text
framework_artifact_sha256
+
integration_inputs_hash
```

No customer/domain release identity participates in framework candidate certification, and the framework release workflows do not depend on `fabric-customer` to produce certification inputs.

`fabric-customer` remains useful as an independent realistic source simulator. When an implementation compares framework versions against the same scenario, record the same verified `workload_digest`; that identity is independent from the framework wheel SHA.

## Rebuild scope

`FULL_REBUILD` remains one run mode with three explicit scopes:

```text
TARGET_ONLY
  trusted retained capture/Bronze remains authoritative
  rebuild downstream target only
  capture/runtime state replacement must remain exactly unchanged

CAPTURE_AND_TARGET
  reconstruct capture/Bronze and downstream target
  checkpoint/boundary may change
  RebuildProgressKind may not change

AUTHORITATIVE_RESET
  widest authoritative reconstruction
  explicit post-rebuild state is required
  RebuildProgressKind may change (NONE/WATERMARK/CDC/EXTERNAL)
```

All scopes require exact requested/completed scope agreement plus target commit and required reconciliation before state cutover.

## Data-correctness repair and downstream impact

The repair planning model is on `main` via merge `962a37923d7c74e901d2ff89941a165f6d0d8eb2`. Exact-head PR CI and post-merge main CI passed. It classifies the first untrustworthy point:

```text
TARGET_LOGIC      -> root TARGET_ONLY
CAPTURE_DATA      -> root CAPTURE_AND_TARGET
CAPTURE_SEMANTICS -> root AUTHORITATIVE_RESET
```

`build_rebuild_impact_plan(...)` computes the exact root + downstream descendant subgraph from DatasetConfig dependencies, produces topological rebuild waves, excludes unrelated branches, and reports disabled-but-contaminated datasets. Root scope cannot be narrowed below the issue-origin requirement. Downstream descendants default to `TARGET_ONLY` and may be explicitly widened when retained facts are insufficient.

Primary files:

```text
src/fabric_data_framework/contracts/rebuild_impact.py
src/fabric_data_framework/recovery/rebuild_impact.py
tests/test_rebuild_impact.py
```

## Versioned target / blue-green cutover

Material data-logic changes may build a physical candidate beside the active version:

```text
logical customer
  -> customer_v1 active
  -> customer_v2 candidate
```

`TargetVersionSpec` identifies the candidate. `TargetCutoverRequest` + `TargetCutoverGate` require candidate build, reconciliation, consumer/UAT validation and a matching approval reference. `execute_target_cutover(...)` uses an optimistic active-generation check and stable cutover request identity. Successful repeat of the same request is idempotent; stale requests fail closed.

The framework changes the logical binding only. It never automatically deletes the previous physical version. The implementation repo owns real physical naming and the provider-specific binding adapter; manual old-version cleanup remains governance-owned.

Primary files:

```text
src/fabric_data_framework/contracts/target_version.py
src/fabric_data_framework/recovery/target_cutover.py
tests/test_target_version_cutover.py
```

Canonical repair documentation:

```text
docs/REPAIR_AND_REBUILD.md
```

Use that document first for questions such as:

```text
Gold logic is wrong: what do I rebuild?
Silver has a new requirement: should I create v2?
Bronze is wrong: which Silver/Gold descendants are contaminated?
Does Gold need v2 when Silver changes?
How do UAT approval, PROD cutover and rollback work?
```

## Purge boundary

The framework deliberately does not automate irreversible business-data purge. Dataset pause/stop remains metadata/override driven, but permanent hard deletion of Bronze/Silver/Gold or control-plane state is a manual, environment-specific operator/governance action.

```text
rebuild != purge
cutover != delete old version
FULL_REBUILD != automatic DROP/DELETE lifecycle
```

## Real Fabric boundary

Do not upgrade local or CI proof into a Fabric claim. The exact current candidate is selected, but it has not executed in real Fabric and no current-candidate Fabric evidence has been retained.

```text
source/contract proof        != real Fabric proof
installed-wheel acceptance   != real Fabric proof
provider Completed            != framework semantic PASS
```

Until the exact selected wheel is installed/attested and the required bounded/authorized stages actually execute in isolated DEV Fabric with retained identity-bound evidence, the status remains:

```text
FABRIC CERTIFICATION REQUIRED
```

## Release boundary

`0.4.0` is not frozen and not release-authorized. An exact current executable wheel has been selected, but the complete candidate identity is not yet closed because `integration_inputs_hash` is pending live verified DEV bindings.

Any packaged-code change invalidates this selected executable candidate and requires a new exact wheel. Docs/test-only state bookkeeping may advance `main` without changing the selected candidate bytes; release governance remains bound to the exact selected candidate source/artifact identity.

Release promotion must use the exact already-built/certified wheel bytes; no release-time wheel rebuild.

## Documentation rule

Canonical user documentation is under `docs/*.md`; narrow contracts are under `docs/reference/`. Only three engineering-recovery documents live under `docs/internal/`:

```text
STATE.md
CAPABILITIES.md
IMPLEMENTATION_MAP.md
```

Do not add another state/evidence narrative document when code, executable schemas, one canonical topic doc, or one of these three internal files can own the information.