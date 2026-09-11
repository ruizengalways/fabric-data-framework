# Engineering state

This file is the **single current-state recovery checkpoint** for `fabric-data-framework`. Git history is the historical record; do not create PR-by-PR state documents.

```yaml
schema: fabric-data-framework-state-v5
updated: 2026-09-11

release:
  public_release: v0.3.0
  source_version: 0.4.0-development-unreleased
  candidate_status: not_frozen
  exact_candidate_source_selected: false
  release_allowed: false
  real_fabric_status: FABRIC_CERTIFICATION_REQUIRED

candidate_identity:
  current_source_candidate_git_sha: not_selected_after_scd2_key_contract_change
  current_source_framework_artifact_sha256: not_selected_after_scd2_key_contract_change
  integration_inputs_hash: not_yet_constructed
  integration_inputs_status: blocked_pending_approved_live_DEV_bindings
  current_source_requires_new_exact_artifact_before_release_claim: true
  candidate_bytes_must_not_change: false
  superseded_package_structure_candidate:
    candidate_git_sha: 8b118e9bf5c5132738eb1a486a6df3e6589cd16e
    candidate_main_framework_ci_run: 34347024953
    candidate_main_installed_wheel_run: 34347025079
    candidate_wheel_artifact_id: 10102117043
    candidate_wheel_artifact_name: framework-wheel-8b118e9bf5c5132738eb1a486a6df3e6589cd16e
    candidate_wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    framework_artifact_sha256: 7ae26c3bef5cc5e5310c59c8f7182402ed26247b23c04cff4189250d8507e9a2
    wheel_sha_verified_against_candidate_json: true
    wheel_sha_verified_against_sha256sums: true
    wheel_sha_independently_rehashed: true
    status: superseded_by_scd2_key_contract_change
  historical_reconciliation_candidate:
    candidate_git_sha: 1c04216812dd438af58ffda73b22f6ff4d96459b
    framework_artifact_sha256: 704989633b11ae110d0728dbc168cb85a994f7310aae13682ccd800a2a00b587
    status: superseded_by_package_structure_refactor
  older_historical_candidate:
    candidate_git_sha: 81f4d5f93983e8288246f5b1521f763091880297
    framework_artifact_sha256: 845f68d938a39ada944a1a71513b4f46b3a68416a5b53d60dbd10c2f6f95327c
    status: superseded_for_current_source_by_packaged_runtime_changes
  quarantine_only_candidate_pr:
    pr: 132
    source_git_sha: 685a5eb1cc8018cd0918186debbe110c2f91a7f0
    status: closed_without_merge_superseded_by_reconciliation_runtime

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
      - project_reconciliation_configuration
      - provider_reconciliation_observation_adapters
      - project_business_reconciliation_controls
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
  control_plane_schema_version: 6
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
  run_modes:
    - RETRY
    - BACKFILL
    - REPLAY
    - FULL_REBUILD
  quarantine_governance:
    merge_sha: 685a5eb1cc8018cd0918186debbe110c2f91a7f0
    original_quarantine_evidence_mutable: false
    bronze_manual_correction_allowed: false
    review_transitions_append_only: true
    review_transition_conflict_policy: fail_closed
    review_statuses:
      - OPEN
      - UNDER_REVIEW
      - RESOLVED
      - REJECTED
      - WAIVED
    replayed_status_operator_settable: false
    replayed_status_derived_from_semantic_replay_marker: true
    manual_correction_requires_governed_reference_and_sha256: true
    manual_correction_replay_requires_exact_approved_provenance: true
    replay_success_deletes_original_evidence: false
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

reconciliation:
  declarative_policy_engine_status: merged_on_main
  pr: 133
  pr_head_sha: 5caee889482944b6761c36c789d191e784a6a393
  pr_framework_ci_run: 34232392803
  pr_installed_wheel_run: 34232392715
  merge_sha: 1c04216812dd438af58ffda73b22f6ff4d96459b
  main_framework_ci_run: 34232496900
  main_installed_wheel_run: 34232496960
  pr_exact_head_ci_status: passed
  main_post_merge_ci_status: passed
  provider_completion_is_reconciliation_authority: false
  provider_role: collect_typed_scalar_or_partitioned_observations
  framework_role: validate_evidence_and_evaluate_policy
  portable_check_kinds:
    - ROW_COUNT_MATCH
    - UNIQUE_KEY
    - NULL_RATE
    - AGGREGATE_MATCH
    - CHECKSUM_MATCH
    - CUSTOM
  row_accounting_default_enabled: true
  absolute_tolerance_supported: true
  relative_tolerance_supported: true
  partition_scoped_checks_supported: true
  severities:
    - ERROR
    - WARNING
  warning_blocks_publication: false
  missing_unknown_duplicate_or_malformed_observation: fail_closed
  required_for_state_commit_false_semantics: observability_only
  strategy_specific_invariants_replaced_by_declarative_checks: false
  integrated_strategy_paths:
    - FULL_REPLACE
    - APPEND
    - WATERMARK_SCD2
    - SNAPSHOT_DIFF
  complete_policy_materialized_to_control_plane_definition: true
  control_plane_schema_bump_required: false

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
  current_source_installed_wheel_acceptance: not_run_for_new_source
  current_source_real_fabric_execution: not_run
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
  - after the SCD2 key-contract repair reaches main, select and independently verify the new exact main wheel
  - record the new exact candidate provenance before any real Fabric certification
  - obtain and live-verify the approved isolated DEV Fabric workspace/lakehouse identity and runtime credentials
  - bootstrap/read back framework-owned certification assets using the exact selected wheel
  - resolve exact item bindings by live Fabric item discovery
  - construct and retain framework-owned integration inputs
  - record integration_inputs_hash without guessing or substituting another identity
  - install/attest the exact selected wheel in isolated DEV Fabric
  - run certify_installed bounded first
  - stop on any real FAIL
  - run only explicitly required and authorized integration stages
  - retain exact identity-bound evidence
```

## Current candidate state after the SCD2 key-contract repair

The previously selected package-structure candidate is now historical provenance only:

```text
source        8b118e9bf5c5132738eb1a486a6df3e6589cd16e
wheel SHA256  7ae26c3bef5cc5e5310c59c8f7182402ed26247b23c04cff4189250d8507e9a2
```

The SCD2 metadata contract now fails closed when `merge_key` differs from `business_key`. Because this changes packaged source, no exact current-source candidate is selected until the repair is merged to `main`, both post-merge gates pass, and the retained main wheel is independently verified against `CANDIDATE.json` and `SHA256SUMS`. Real Fabric certification must not run against the superseded wheel.

For SCD2, `business_key` is the canonical entity identity used by the reference and CDC history engines. The shared `merge_key` field remains required in the current metadata schema but must equal `business_key`; divergent values are invalid.

## Declarative reconciliation

PR #133 productized reconciliation as a source-controlled framework policy rather than a post-run dashboard or provider status check.

```text
provider / SQL / Spark / project adapter
  -> collect typed scalar or partitioned ReconciliationObservation values
  -> framework validates observation identity
  -> compose strategy-specific invariant metrics
  -> evaluate configured tolerance/severity
  -> PASS / WARN / FAIL
  -> apply required_for_state_commit authority at publication/state gate
```

Portable check kinds are `ROW_COUNT_MATCH`, `UNIQUE_KEY`, `NULL_RATE`, `AGGREGATE_MATCH`, `CHECKSUM_MATCH`, and `CUSTOM`. Numeric count/aggregate checks support absolute and relative tolerance. Partitioned checks require exact partition-key identity and reject duplicate partitions. Missing configured evidence, unknown check IDs, duplicate unpartitioned observations, malformed numeric evidence, and other structurally invalid observations fail closed.

`WARNING` failures produce `WARN` and do not block publication. `ERROR` failures produce `FAIL`. When `required_for_state_commit=true` (the default), FAIL blocks publication/state advance; when explicitly false, reconciliation remains durable observability evidence but does not own state-gate authority. Independent DQ/apply/target/rebuild gates remain authoritative.

Declarative checks do not replace strategy-specific correctness. FULL snapshot completeness/candidate accounting, APPEND identity/accounting, SCD2 one-current-row, and SNAPSHOT_DIFF structural metrics remain composed base invariants.

The complete policy participates in DatasetConfig/config identity and is materialized into the existing Control Plane `reconciliation_policy.definition` JSON column. Control Plane schema remains v6.

Primary files:

```text
src/fabric_data_framework/contracts/reconciliation.py
src/fabric_data_framework/metadata/config.py
src/fabric_data_framework/quality/reconciliation/engine.py
src/fabric_data_framework/quality/reconciliation/scd2.py
src/fabric_data_framework/quality/reconciliation/full_replace.py
src/fabric_data_framework/quality/reconciliation/append.py
src/fabric_data_framework/quality/reconciliation/snapshot_diff.py
tests/test_reconciliation_engine.py
tests/test_reconciliation_execution_gate.py
tests/test_reconciliation_metadata.py
```

Canonical guide: `docs/RECONCILIATION.md`.

## Quarantine governance

Quarantine is immutable evidence, not an editable staging area. Human remediation is a separate governed lifecycle:

```text
OPEN
  -> UNDER_REVIEW
      -> RESOLVED
      -> REJECTED
      -> WAIVED
```

`REPLAYED` is derived only after replay target mutation and required reconciliation pass. Manual correction writes a new governed correction reference plus exact SHA256 and never mutates Bronze/original quarantine. Original evidence is retained until explicit retention/governance cleanup.

Canonical operational procedure: `docs/OPERATIONS.md`.

## Rebuild / repair boundary

`FULL_REBUILD` remains one run mode with `TARGET_ONLY`, `CAPTURE_AND_TARGET`, and `AUTHORITATIVE_RESET`. Rebuild/cutover never implies automatic purge or old-version deletion. See `docs/REPAIR_AND_REBUILD.md`.

## Real Fabric boundary

Do not upgrade source or installed-wheel proof into a Fabric claim:

```text
source/contract proof        != real Fabric proof
installed-wheel acceptance   != real Fabric proof
provider Completed           != framework semantic PASS
selected exact wheel         != certified Fabric candidate evidence
```

Until the selected wheel is bound to a real `integration_inputs_hash` and required authorized stages execute in isolated DEV Fabric with retained identity-bound evidence, status remains:

```text
FABRIC CERTIFICATION REQUIRED
```

## Release boundary

`0.4.0` is not frozen and not release-authorized. The previously selected post-refactor executable candidate is superseded by the packaged SCD2 key-contract repair, so there is currently no exact current-source candidate. After this repair reaches `main`, both post-merge gates must pass and the retained main wheel must be independently verified before a new candidate is recorded.

Any packaged-code change invalidates a selected executable candidate and requires a new exact main wheel. A docs/test-only bookkeeping merge after candidate selection does not change selected wheel bytes. Release promotion must use the exact already-built/certified wheel bytes; no release-time rebuild.

## Documentation rule

Canonical user documentation is under `docs/*.md`; narrow contracts are under `docs/reference/`. Only three engineering-recovery documents live under `docs/internal/`:

```text
STATE.md
CAPABILITIES.md
IMPLEMENTATION_MAP.md
```

Do not add another state/evidence narrative document when code, executable schemas, one canonical topic doc, or one of these three internal files can own the information.
