from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}: {old!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


# metadata/config.py
path = "src/fabric_data_framework/metadata/config.py"
replace_once(
    path,
    "from ..contracts.base import FrozenModel as _FrozenModel\nfrom ..contracts.reconciliation import ReconciliationSeverity\n",
    "from ..contracts.base import FrozenModel as _FrozenModel\nfrom ..contracts.current_projection import CurrentProjectionConfig\nfrom ..contracts.reconciliation import ReconciliationSeverity\n",
)
replace_once(
    path,
    '    SNAPSHOT = "SNAPSHOT"\n',
    '    SNAPSHOT = "SNAPSHOT"\n    PROJECTION = "PROJECTION"\n',
)
replace_once(
    path,
    '    SNAPSHOT_DIFF = "SNAPSHOT_DIFF"\n',
    '    SNAPSHOT_DIFF = "SNAPSHOT_DIFF"\n    CURRENT_PROJECTION = "CURRENT_PROJECTION"\n',
)
replace_once(
    path,
    "    ApplyStrategy.SNAPSHOT_DIFF,\n}\n",
    "    ApplyStrategy.SNAPSHOT_DIFF,\n    ApplyStrategy.CURRENT_PROJECTION,\n}\n",
)
replace_once(
    path,
    """        if self.apply_strategy is ApplyStrategy.SCD2:\n            if not self.business_key:\n                raise ValueError(\"SCD2 apply requires business_key\")\n            if self.merge_key != self.business_key:\n                raise ValueError(\"SCD2 merge_key must equal business_key\")\n        if self.apply_strategy is ApplyStrategy.APPEND and not self.append_identity:\n""",
    """        if self.apply_strategy is ApplyStrategy.SCD2:\n            if not self.business_key:\n                raise ValueError(\"SCD2 apply requires business_key\")\n            if self.merge_key != self.business_key:\n                raise ValueError(\"SCD2 merge_key must equal business_key\")\n        if self.apply_strategy is ApplyStrategy.CURRENT_PROJECTION:\n            if self.capture_strategy is not CaptureStrategy.PROJECTION:\n                raise ValueError(\"CURRENT_PROJECTION requires PROJECTION capture\")\n            if not self.business_key:\n                raise ValueError(\"CURRENT_PROJECTION requires business_key\")\n            if self.merge_key != self.business_key:\n                raise ValueError(\"CURRENT_PROJECTION merge_key must equal business_key\")\n            if self.tracked_columns:\n                raise ValueError(\"CURRENT_PROJECTION does not accept tracked_columns\")\n            if self.ordering_columns:\n                raise ValueError(\"CURRENT_PROJECTION does not accept source ordering columns\")\n            if self.delete_policy != \"DERIVE_FROM_HISTORY\":\n                raise ValueError(\"CURRENT_PROJECTION delete_policy must be DERIVE_FROM_HISTORY\")\n        elif self.capture_strategy is CaptureStrategy.PROJECTION:\n            raise ValueError(\"PROJECTION capture is only valid for CURRENT_PROJECTION apply\")\n        if self.apply_strategy is ApplyStrategy.APPEND and not self.append_identity:\n""",
)
replace_once(
    path,
    """    reconciliation: ReconciliationPolicy\n    schema_contract: SchemaContract | None = None\n    execution: ExecutionPolicy = Field(default_factory=ExecutionPolicy)\n""",
    """    reconciliation: ReconciliationPolicy\n    schema_contract: SchemaContract | None = None\n    current_projection: CurrentProjectionConfig | None = None\n    execution: ExecutionPolicy = Field(default_factory=ExecutionPolicy)\n""",
)
replace_once(
    path,
    """        if (\n            self.execution.apply_engine is ExecutionEngine.CUSTOM\n            and not self.extensions.apply\n        ):\n            raise ValueError(\"CUSTOM apply execution requires extensions.apply\")\n        return self\n""",
    """        if (\n            self.execution.apply_engine is ExecutionEngine.CUSTOM\n            and not self.extensions.apply\n        ):\n            raise ValueError(\"CUSTOM apply execution requires extensions.apply\")\n        if self.load.apply_strategy is ApplyStrategy.CURRENT_PROJECTION:\n            if self.current_projection is None:\n                raise ValueError(\"CURRENT_PROJECTION requires current_projection configuration\")\n            if self.schema_contract is None:\n                raise ValueError(\"CURRENT_PROJECTION requires an explicit schema_contract\")\n            history_id = self.current_projection.authoritative_history_dataset_id\n            if history_id not in self.orchestration.dependencies:\n                raise ValueError(\n                    \"CURRENT_PROJECTION must depend on authoritative_history_dataset_id\"\n                )\n        elif self.current_projection is not None:\n            raise ValueError(\n                \"current_projection configuration is only valid for CURRENT_PROJECTION apply\"\n            )\n        return self\n""",
)

# metadata/capabilities.py
path = "src/fabric_data_framework/metadata/capabilities.py"
replace_once(
    path,
    "                CaptureStrategy.STREAM,\n            }\n",
    "                CaptureStrategy.STREAM,\n                CaptureStrategy.PROJECTION,\n            }\n",
)

# execution/plan_compiler.py
path = "src/fabric_data_framework/execution/plan_compiler.py"
replace_once(
    path,
    "from fabric_data_framework.contracts.execution_plan import (\n",
    "from fabric_data_framework.contracts.current_projection import CurrentProjectionMode\nfrom fabric_data_framework.contracts.execution_plan import (\n",
)
replace_once(
    path,
    """    capture_kind = _ENGINE_TO_KIND[capture_engine]\n    apply_kind = _ENGINE_TO_KIND[apply_engine]\n\n    if capture_engine is ExecutionEngine.SPARK and apply_engine is ExecutionEngine.SPARK:\n""",
    """    capture_kind = _ENGINE_TO_KIND[capture_engine]\n    apply_kind = _ENGINE_TO_KIND[apply_engine]\n\n    if config.load.apply_strategy.value == \"CURRENT_PROJECTION\":\n        projection = config.current_projection\n        if projection is None:\n            raise ValueError(\"CURRENT_PROJECTION execution requires projection metadata\")\n        if projection.mode in {CurrentProjectionMode.VIEW, CurrentProjectionMode.MATERIALIZED}:\n            units = (\n                _unit(\n                    unit_id=\"current_projection_publish\",\n                    roles=(ExecutionRole.PREPARE, ExecutionRole.APPLY, ExecutionRole.PUBLISH, ExecutionRole.RECONCILE),\n                    execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,\n                    retry_count=retry_count,\n                    timeout_seconds=timeout_seconds,\n                    reconciliation_gate=reconciliation_gate,\n                    state_commit_boundary=False,\n                ),\n            )\n        else:\n            units = (\n                _unit(\n                    unit_id=\"current_projection_incremental\",\n                    roles=(\n                        ExecutionRole.EXTRACT,\n                        ExecutionRole.NORMALIZE,\n                        ExecutionRole.VALIDATE,\n                        ExecutionRole.APPLY,\n                        ExecutionRole.RECONCILE,\n                        ExecutionRole.COMMIT_STATE,\n                    ),\n                    execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,\n                    retry_count=retry_count,\n                    timeout_seconds=timeout_seconds,\n                    reconciliation_gate=reconciliation_gate,\n                    state_commit_boundary=True,\n                ),\n            )\n    elif capture_engine is ExecutionEngine.SPARK and apply_engine is ExecutionEngine.SPARK:\n""",
)
replace_once(
    path,
    """    return ExecutionPlan(\n        dataset_id=config.dataset_id,\n        run_mode=run_mode,\n        capture_strategy=config.load.capture_strategy,\n        apply_strategy=config.load.apply_strategy,\n        capture_engine=capture_engine,\n        apply_engine=apply_engine,\n        capture_capability_profile=config.execution.capability_profile,\n        apply_capability_profile=config.execution.apply_capability_profile,\n        effective_config_hash=effective.effective_config_hash,\n        units=(\n            ExecutionUnit(\n                unit_id=\"dataset_execute\",\n                execution_kind=execution_kind,\n                retry_count=config.orchestration.retry_count,\n                timeout_seconds=config.orchestration.timeout_seconds,\n                reconciliation_gate=config.reconciliation.required_for_state_commit,\n                state_commit_boundary=True,\n            ),\n        ),\n        required_bindings=required_bindings,\n    )\n""",
    """    if config.load.apply_strategy.value == \"CURRENT_PROJECTION\":\n        projection = config.current_projection\n        if projection is None:\n            raise ValueError(\"CURRENT_PROJECTION execution requires projection metadata\")\n        is_incremental = projection.mode is CurrentProjectionMode.DELTA_PROJECTION\n        units = (\n            ExecutionUnit(\n                unit_id=(\n                    \"current_projection_incremental\"\n                    if is_incremental\n                    else \"current_projection_publish\"\n                ),\n                roles=(\n                    (\n                        ExecutionRole.EXTRACT,\n                        ExecutionRole.NORMALIZE,\n                        ExecutionRole.VALIDATE,\n                        ExecutionRole.APPLY,\n                        ExecutionRole.RECONCILE,\n                        ExecutionRole.COMMIT_STATE,\n                    )\n                    if is_incremental\n                    else (ExecutionRole.PREPARE, ExecutionRole.APPLY, ExecutionRole.PUBLISH, ExecutionRole.RECONCILE)\n                ),\n                execution_kind=execution_kind,\n                retry_count=config.orchestration.retry_count,\n                timeout_seconds=config.orchestration.timeout_seconds,\n                reconciliation_gate=config.reconciliation.required_for_state_commit,\n                state_commit_boundary=is_incremental,\n            ),\n        )\n    else:\n        units = (\n            ExecutionUnit(\n                unit_id=\"dataset_execute\",\n                execution_kind=execution_kind,\n                retry_count=config.orchestration.retry_count,\n                timeout_seconds=config.orchestration.timeout_seconds,\n                reconciliation_gate=config.reconciliation.required_for_state_commit,\n                state_commit_boundary=True,\n            ),\n        )\n    return ExecutionPlan(\n        dataset_id=config.dataset_id,\n        run_mode=run_mode,\n        capture_strategy=config.load.capture_strategy,\n        apply_strategy=config.load.apply_strategy,\n        capture_engine=capture_engine,\n        apply_engine=apply_engine,\n        capture_capability_profile=config.execution.capability_profile,\n        apply_capability_profile=config.execution.apply_capability_profile,\n        effective_config_hash=effective.effective_config_hash,\n        units=units,\n        required_bindings=required_bindings,\n    )\n""",
)

# control_plane/schema.py
path = "src/fabric_data_framework/control_plane/schema.py"
replace_once(path, "CONTROL_PLANE_SCHEMA_VERSION = 6\n", "CONTROL_PLANE_SCHEMA_VERSION = 7\n")
replace_once(
    path,
    '    (6, "quarantine_review_and_manual_correction_governance"),\n)',
    '    (6, "quarantine_review_and_manual_correction_governance"),\n    (7, "current_projection_semantics"),\n)',
)
replace_once(
    path,
    """reconciliation_policy = Table(\n    \"reconciliation_policy\",\n    metadata,\n    Column(\"dataset_id\", String(255), ForeignKey(\"dataset.dataset_id\"), primary_key=True),\n    Column(\"policy_name\", String(128), nullable=False),\n    Column(\"required_for_state_commit\", Boolean, nullable=False),\n    Column(\"definition\", JSON, nullable=True),\n    *_audit_columns(),\n)\n\nruntime_override = Table(\n""",
    """reconciliation_policy = Table(\n    \"reconciliation_policy\",\n    metadata,\n    Column(\"dataset_id\", String(255), ForeignKey(\"dataset.dataset_id\"), primary_key=True),\n    Column(\"policy_name\", String(128), nullable=False),\n    Column(\"required_for_state_commit\", Boolean, nullable=False),\n    Column(\"definition\", JSON, nullable=True),\n    *_audit_columns(),\n)\n\ncurrent_projection_policy = Table(\n    \"current_projection_policy\",\n    metadata,\n    Column(\"dataset_id\", String(255), ForeignKey(\"dataset.dataset_id\"), primary_key=True),\n    Column(\"authoritative_history_dataset_id\", String(255), nullable=False),\n    Column(\"mode\", String(64), nullable=False),\n    Column(\"definition\", JSON, nullable=False),\n    *_audit_columns(),\n)\n\nruntime_override = Table(\n""",
)
replace_once(
    path,
    '        "reconciliation_policy",\n    }\n)',
    '        "reconciliation_policy",\n        "current_projection_policy",\n    }\n)',
)
replace_once(
    path,
    '    "current_schema_version",\n    "dataset_attempt_lineage",\n',
    '    "current_schema_version",\n    "current_projection_policy",\n    "dataset_attempt_lineage",\n',
)

# deployment/delivery.py
path = "src/fabric_data_framework/deployment/delivery.py"
replace_once(
    path,
    "from sqlalchemy import Engine, and_, select, update\n",
    "from sqlalchemy import Engine, and_, delete, select, update\n",
)
replace_once(
    path,
    "    data_quality_policy,\n    dataset,\n",
    "    current_projection_policy,\n    data_quality_policy,\n    dataset,\n",
)
replace_once(
    path,
    """            _upsert_definition(\n                connection,\n                reconciliation_policy,\n                {\"dataset_id\": config.dataset_id},\n                reconciliation_values,\n                {**reconciliation_values, **common_audit},\n            )\n\n    return bundle_hash\n""",
    """            _upsert_definition(\n                connection,\n                reconciliation_policy,\n                {\"dataset_id\": config.dataset_id},\n                reconciliation_values,\n                {**reconciliation_values, **common_audit},\n            )\n\n            if config.current_projection is None:\n                connection.execute(\n                    delete(current_projection_policy).where(\n                        current_projection_policy.c.dataset_id == config.dataset_id\n                    )\n                )\n            else:\n                projection_values = {\n                    \"dataset_id\": config.dataset_id,\n                    \"authoritative_history_dataset_id\": (\n                        config.current_projection.authoritative_history_dataset_id\n                    ),\n                    \"mode\": config.current_projection.mode.value,\n                    \"definition\": config.current_projection.model_dump(mode=\"json\"),\n                    \"created_at\": now,\n                    \"updated_at\": None,\n                }\n                _upsert_definition(\n                    connection,\n                    current_projection_policy,\n                    {\"dataset_id\": config.dataset_id},\n                    projection_values,\n                    {**projection_values, **common_audit},\n                )\n\n    return bundle_hash\n""",
)

# deployment/project.py
path = "src/fabric_data_framework/deployment/project.py"
replace_once(
    path,
    "from fabric_data_framework.deployment.delivery import load_dataset_configs\n",
    "from fabric_data_framework.deployment.current_projection import validate_current_projection_bundle\nfrom fabric_data_framework.deployment.delivery import load_dataset_configs\n",
)
replace_once(
    path,
    """    configs = load_dataset_configs(dataset_dir)\n    _validate_dependency_graph(configs)\n\n    capture_engines: list[str] = []\n""",
    """    configs = load_dataset_configs(dataset_dir)\n    _validate_dependency_graph(configs)\n    projection_warnings = validate_current_projection_bundle(configs)\n\n    capture_engines: list[str] = []\n""",
)
replace_once(
    path,
    """    selected_ids = {selection.dataset_id for selection in selections}\n    unknown = sorted(selected_ids - set(configs_by_id))\n    if unknown:\n        raise ValueError(\n            \"semantic selections reference unknown datasets: \" + \", \".join(unknown)\n        )\n    missing = sorted(set(configs_by_id) - selected_ids)\n    if missing:\n        raise ValueError(\n            \"DatasetConfig values missing semantic capture selection: \" + \", \".join(missing)\n        )\n\n    warnings: list[str] = []\n    for selection in selections:\n        report = validate_semantic_capture_selection(\n            configs_by_id[selection.dataset_id], selection\n        )\n""",
    """    selected_ids = {selection.dataset_id for selection in selections}\n    source_dataset_ids = {\n        config.dataset_id for config in configs if config.current_projection is None\n    }\n    unknown = sorted(selected_ids - set(configs_by_id))\n    if unknown:\n        raise ValueError(\n            \"semantic selections reference unknown datasets: \" + \", \".join(unknown)\n        )\n    projection_selected = sorted(selected_ids - source_dataset_ids)\n    if projection_selected:\n        raise ValueError(\n            \"current projection datasets derive capture semantics from authoritative history and \"\n            \"must not have source semantic selections: \" + \", \".join(projection_selected)\n        )\n    missing = sorted(source_dataset_ids - selected_ids)\n    if missing:\n        raise ValueError(\n            \"source DatasetConfig values missing semantic capture selection: \" + \", \".join(missing)\n        )\n\n    warnings: list[str] = list(projection_warnings)\n    for selection in selections:\n        report = validate_semantic_capture_selection(\n            configs_by_id[selection.dataset_id], selection\n        )\n""",
)

# Update hard-coded current control-plane version assertions.
for path in (
    "tests/test_append_metadata.py",
    "tests/test_target_operation_journal.py",
    "tests/test_control_plane_certification.py",
    "tests/test_control_plane_certification_cli.py",
):
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if "CONTROL_PLANE_SCHEMA_VERSION == 6" not in text:
        raise SystemExit(f"{path}: expected v6 assertion")
    target.write_text(text.replace("CONTROL_PLANE_SCHEMA_VERSION == 6", "CONTROL_PLANE_SCHEMA_VERSION == 7"), encoding="utf-8")

# docs index / root navigation
path = "docs/README.md"
replace_once(
    path,
    "| Configure source/target reconciliation, tolerances, warnings and state gates | [`RECONCILIATION.md`](RECONCILIATION.md) |\n",
    "| Configure source/target reconciliation, tolerances, warnings and state gates | [`RECONCILIATION.md`](RECONCILIATION.md) |\n| Derive canonical current representations from authoritative SCD2 history | [`CURRENT_PROJECTIONS.md`](CURRENT_PROJECTIONS.md) |\n",
)
replace_once(
    path,
    "RECONCILIATION.md\n  reconciliation policy/check/tolerance/severity/observation/state-gate semantics\n\nOPERATIONS.md\n",
    "RECONCILIATION.md\n  reconciliation policy/check/tolerance/severity/observation/state-gate semantics\n\nCURRENT_PROJECTIONS.md\n  authoritative SCD2 history + VIEW/MATERIALIZED/DELTA_PROJECTION current semantics\n\nOPERATIONS.md\n",
)
replace_once(
    path,
    "`RECONCILIATION.md` is a dedicated topic because reconciliation spans source-controlled DatasetConfig, provider observation collection, framework evaluation, runtime publication/state gates, and implementation-owned business controls; mixing that contract into source-pattern selection or transient recovery would create duplicate ownership. `REPAIR_AND_REBUILD.md`",
    "`RECONCILIATION.md` is a dedicated topic because reconciliation spans source-controlled DatasetConfig, provider observation collection, framework evaluation, runtime publication/state gates, and implementation-owned business controls; mixing that contract into source-pattern selection or transient recovery would create duplicate ownership. `CURRENT_PROJECTIONS.md` is dedicated because current/history semantics span metadata, deployment physicalization, Delta CDF checkpointing, rebuild, and operations. `REPAIR_AND_REBUILD.md`",
)

path = "README.md"
replace_once(
    path,
    "- [`docs/RECONCILIATION.md`](docs/RECONCILIATION.md) — configure reconciliation checks, tolerance, partitioning, WARN/FAIL semantics, provider observations, and state-gate authority.\n",
    "- [`docs/RECONCILIATION.md`](docs/RECONCILIATION.md) — configure reconciliation checks, tolerance, partitioning, WARN/FAIL semantics, provider observations, and state-gate authority.\n- [`docs/CURRENT_PROJECTIONS.md`](docs/CURRENT_PROJECTIONS.md) — derive stable current objects from authoritative SCD2 history using VIEW, materialized, or incremental Delta projection modes.\n",
)

# docs consistency index
path = "tests/test_current_docs_consistency.py"
replace_once(
    path,
    '    "RECONCILIATION.md",\n    "OPERATIONS.md",\n',
    '    "RECONCILIATION.md",\n    "CURRENT_PROJECTIONS.md",\n    "OPERATIONS.md",\n',
)
replace_once(
    path,
    '        "RECONCILIATION.md",\n        "OPERATIONS.md",\n',
    '        "RECONCILIATION.md",\n        "CURRENT_PROJECTIONS.md",\n        "OPERATIONS.md",\n',
)

# Canonical STATE: packaged source changed; selected candidate becomes historical until exact post-merge wheel selection.
path = "docs/internal/STATE.md"
replace_once(path, "  exact_candidate_source_selected: true\n", "  exact_candidate_source_selected: false\n")
replace_once(
    path,
    "  current_source_candidate_git_sha: b1b69c6ecd465b63c7e83d8405733a0c34962c8c\n",
    "  current_source_candidate_git_sha: not_selected_after_current_projection_feature\n",
)
replace_once(
    path,
    "  current_source_framework_artifact_sha256: 3bfa738f63ae2b85228174dcd4b0949618d4e3f52212e8dc1deae01465860ab2\n",
    "  current_source_framework_artifact_sha256: not_selected_after_current_projection_feature\n",
)
replace_once(
    path,
    "  current_source_requires_new_exact_artifact_before_release_claim: false\n",
    "  current_source_requires_new_exact_artifact_before_release_claim: true\n",
)
replace_once(path, "  candidate_bytes_must_not_change: true\n", "  candidate_bytes_must_not_change: false\n")
replace_once(
    path,
    "    status: selected_not_frozen\n  superseded_scd2_key_contract_candidate:\n",
    "    status: superseded_by_current_projection_feature\n  superseded_scd2_key_contract_candidate:\n",
)
replace_once(path, "  control_plane_schema_version: 6\n", "  control_plane_schema_version: 7\n")
replace_once(path, "  exact_current_candidate_selected: true\n", "  exact_current_candidate_selected: false\n")
replace_once(
    path,
    "  current_source_installed_wheel_acceptance: passed\n",
    "  current_source_installed_wheel_acceptance: not_run_for_new_current_source\n",
)
replace_once(
    path,
    """next_boundary:\n  - obtain and live-verify the approved isolated DEV Fabric workspace/lakehouse identity and runtime credentials\n""",
    """next_boundary:\n  - merge current/history projection semantics only after exact PR-head framework and installed-wheel gates pass\n  - build and retain the exact post-merge main wheel and independently verify its inner SHA256\n  - select the new exact executable candidate before any live Fabric certification\n  - obtain and live-verify the approved isolated DEV Fabric workspace/lakehouse identity and runtime credentials\n""",
)
replace_once(
    path,
    "## Selected exact current candidate after runtime-safety hardening\n",
    "## Superseded runtime-safety candidate\n",
)
replace_once(
    path,
    "This selects the exact executable post-hardening candidate. It does **not** freeze 0.4, construct integration inputs, execute Microsoft Fabric, authorize release, or claim Fabric PASS. Candidate/evidence identity remains `framework_artifact_sha256 + integration_inputs_hash`; `integration_inputs_hash` is still not yet constructed.\n",
    "This wheel was the exact executable post-hardening candidate. The packaged current/history projection feature supersedes it, so it is historical provenance only until a new exact post-merge wheel is selected. It did **not** freeze 0.4, construct integration inputs, execute Microsoft Fabric, authorize release, or claim Fabric PASS. Candidate/evidence identity remains `framework_artifact_sha256 + integration_inputs_hash`; `integration_inputs_hash` is still not yet constructed.\n",
)

# Update STATE consistency expectations to the fail-closed branch state.
path = "tests/test_current_docs_consistency.py"
replace_once(path, '        "exact_candidate_source_selected: true",\n', '        "exact_candidate_source_selected: false",\n')
replace_once(
    path,
    '        "current_source_candidate_git_sha: b1b69c6ecd465b63c7e83d8405733a0c34962c8c",\n',
    '        "current_source_candidate_git_sha: not_selected_after_current_projection_feature",\n',
)
replace_once(
    path,
    '        "current_source_framework_artifact_sha256: 3bfa738f63ae2b85228174dcd4b0949618d4e3f52212e8dc1deae01465860ab2",\n',
    '        "current_source_framework_artifact_sha256: not_selected_after_current_projection_feature",\n',
)
replace_once(
    path,
    '        "current_source_requires_new_exact_artifact_before_release_claim: false",\n',
    '        "current_source_requires_new_exact_artifact_before_release_claim: true",\n',
)
replace_once(path, '        "status: selected_not_frozen",\n', '        "status: superseded_by_current_projection_feature",\n')
replace_once(path, '        "exact_current_candidate_selected: true",\n', '        "exact_current_candidate_selected: false",\n')
replace_once(
    path,
    '        "current_source_installed_wheel_acceptance: passed",\n',
    '        "current_source_installed_wheel_acceptance: not_run_for_new_current_source",\n',
)
replace_once(path, '        "control_plane_schema_version: 6",\n', '        "control_plane_schema_version: 7",\n')
