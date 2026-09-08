# Engineering state

This file is the **single current-state recovery checkpoint** for `fabric-data-framework`. Git history is the historical record; do not create PR-by-PR state documents.

```yaml
schema: fabric-data-framework-state-v5
updated: 2026-09-08

release:
  public_release: v0.3.0
  source_version: 0.4.0-development-unreleased
  candidate_status: not_frozen
  exact_candidate_source_selected: false
  release_allowed: false
  real_fabric_status: FABRIC_CERTIFICATION_REQUIRED

candidate_identity:
  current_source_candidate_git_sha: not_selected
  current_source_framework_artifact_sha256: not_selected
  integration_inputs_hash: not_constructed_for_current_source
  integration_inputs_status: blocked_pending_new_exact_current_source_artifact_then_approved_live_DEV_bindings
  current_source_requires_new_exact_artifact_before_release_claim: true
  candidate_bytes_must_not_change: true
  previous_selected_candidate:
    candidate_git_sha: 81f4d5f93983e8288246f5b1521f763091880297
    candidate_main_framework_ci_run: 34216247521
    candidate_main_installed_wheel_run: 34216247544
    candidate_wheel_artifact_id: 10051879910
    candidate_wheel_artifact_name: framework-wheel-81f4d5f93983e8288246f5b1521f763091880297
    candidate_wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    framework_artifact_sha256: 845f68d938a39ada944a1a71513b4f46b3a68416a5b53d60dbd10c2f6f95327c
    status: superseded_for_current_source_by_packaged_runtime_changes

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
  quarantine_governance:
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
  declarative_policy_engine_status: implementation_complete_pending_exact_head_pr_ci_and_merge
  pr: 133
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
  current_source_installed_wheel_acceptance: pending_new_exact_main_candidate
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
  - require exact-head framework-ci and installed-wheel-acceptance PASS for PR 133
  - merge PR 133 only after both exact-head gates are green
  - obtain successful post-merge current-main framework-ci and installed-wheel-acceptance
  - select and retain the new exact current-main wheel artifact and independently verify its framework_artifact_sha256
  - record that new exact candidate provenance before any 0.4 release claim
  - resolve and live-verify the approved isolated DEV Fabric workspace/lakehouse anchor
  - bootstrap/read back framework-owned certification assets using the new exact selected wheel
  - resolve exact item bindings by live Fabric item discovery
  - construct and retain framework-owned integration inputs
  - record integration_inputs_hash for the new selected candidate
  - install/attest the exact selected wheel in isolated DEV Fabric
  - run certify_installed bounded first
  - stop on any real FAIL
  - run only explicitly required and authorized integration stages
  - retain exact identity-bound evidence
```

## Current candidate interpretation

The previously selected executable candidate came from successful `main` CI at:

```text
81f4d5f93983e8288246f5b1521f763091880297
```

with retained wheel:

```text
fabric_data_framework-0.4.0-py3-none-any.whl
framework_artifact_sha256
= 845f68d938a39ada944a1a71513b4f46b3a68416a5b53d60dbd10c2f6f95327c
```

and provenance:

```text
framework-ci               34216247521  PASS
installed-wheel-acceptance 34216247544  PASS
```

That artifact is now **historical provenance, not the current-source candidate**. Main already contains packaged quarantine-governance runtime/schema changes, and PR #133 adds further packaged reconciliation runtime changes. The quarantine-only candidate-selection PR #132 was therefore closed without merge. No existing wheel may be treated as the candidate for the source that will exist after PR #133.

Therefore:

```text
exact_current_candidate_selected = false
current_source_requires_new_exact_artifact_before_release_claim = true
```

Do not silently reuse the previous wheel SHA, and do not fabricate a replacement SHA from source or a PR build. The next exact candidate must come from successful post-merge current-`main` CI and then pass the installed-wheel and Fabric evidence lifecycle.

Framework certification remains fully framework-owned. Once a new current-source candidate is selected, its complete candidate/evidence identity remains exactly:

```text
framework_artifact_sha256
+
integration_inputs_hash
```

No customer/domain release identity participates in framework candidate certification, and the framework release workflows do not depend on `fabric-customer` to produce certification inputs.

`fabric-customer` remains useful as an independent realistic source simulator. When an implementation compares framework versions against the same scenario, record the same verified `workload_digest`; that identity is independent from the framework wheel SHA.

## Declarative reconciliation

PR #133 productizes reconciliation as a source-controlled framework policy rather than a post-run dashboard or provider status check.

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
src/fabric_data_framework/quality/reconciliation_engine.py
src/fabric_data_framework/quality/reconciliation.py
src/fabric_data_framework/quality/full_refresh.py
src/fabric_data_framework/quality/append.py
src/fabric_data_framework/quality/snapshot_diff.py
tests/test_reconciliation_engine.py
tests/test_reconciliation_execution_gate.py
tests/test_reconciliation_metadata.py
```

Canonical guide: `docs/RECONCILIATION.md`.

## Quarantine governance

Quarantine is immutable evidence, not an editable staging area. The current source models human remediation as a separate governed lifecycle:

```text
OPEN
  -> UNDER_REVIEW
      -> RESOLVED
      -> REJECTED
      -> WAIVED
```

`REPLAYED` is deliberately excluded from operator review transitions. It is derived only when replay target mutation and required reconciliation pass and the original quarantine batch receives the semantic `replayed_by_dataset_run_id` correlation.

Manual correction does not mutate Bronze or the original quarantine payload. It records a new governed correction reference plus exact SHA256, actor, reason and optional ticket. A `RESOLVED + MANUAL_CORRECTION` case can replay only when the payload provider supplies the exact approved correction identity/reference/hash. Original quarantine and correction evidence remain retained; physical deletion belongs to explicit retention/governance policy.

Primary files:

```text
src/fabric_data_framework/contracts/quarantine.py
src/fabric_data_framework/contracts/replay.py
src/fabric_data_framework/control_plane/quarantine_governance.py
src/fabric_data_framework/recovery/replay.py
tests/test_quarantine_governance.py
```

Canonical operational procedure: `docs/OPERATIONS.md`.

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

Canonical repair documentation: `docs/REPAIR_AND_REBUILD.md`.

## Purge boundary

The framework deliberately does not automate irreversible business-data purge. Dataset pause/stop remains metadata/override driven, but permanent hard deletion of Bronze/Silver/Gold or control-plane state is a manual, environment-specific operator/governance action.

```text
rebuild != purge
cutover != delete old version
FULL_REBUILD != automatic DROP/DELETE lifecycle
```

Quarantine review follows the same governance principle: `RESOLVED` or `REPLAYED` does not mean physical deletion. Retention policy owns eventual cleanup.

## Real Fabric boundary

Do not upgrade local or CI proof into a Fabric claim. There is currently **no exact current-source candidate selected**, and no current-source real Fabric evidence has been retained after the packaged quarantine/reconciliation changes.

```text
source/contract proof        != real Fabric proof
installed-wheel acceptance   != real Fabric proof
provider Completed           != framework semantic PASS
historical selected wheel    != current-source candidate
```

Until a new exact post-merge current-main wheel is selected, installed/attested, bound to framework-owned integration inputs, and the required bounded/authorized stages actually execute in isolated DEV Fabric with retained identity-bound evidence, the status remains:

```text
FABRIC CERTIFICATION REQUIRED
```

## Release boundary

`0.4.0` is not frozen and not release-authorized. The previous selected executable wheel and the later quarantine-only candidate are both superseded for current-source purposes by packaged runtime changes. A new exact post-reconciliation current-main candidate must be selected before release certification can continue.

Any packaged-code change invalidates the selected executable candidate and requires a new exact wheel. Docs/test-only state bookkeeping may advance `main` without changing selected candidate bytes; release governance always remains bound to exact selected candidate source/artifact identity.

Release promotion must use the exact already-built/certified wheel bytes; no release-time wheel rebuild.

## Documentation rule

Canonical user documentation is under `docs/*.md`; narrow contracts are under `docs/reference/`. Only three engineering-recovery documents live under `docs/internal/`:

```text
STATE.md
CAPABILITIES.md
IMPLEMENTATION_MAP.md
```

Do not add another state/evidence narrative document when code, executable schemas, one canonical topic doc, or one of these three internal files can own the information.
