"""Operational delivery helpers shared by GitHub, Azure Pipelines and Fabric-native adapters."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable

from sqlalchemy import Engine, and_, select, update

from .config import DatasetConfig, canonical_hash
from .control_plane import (
    CONTROL_PLANE_SCHEMA_VERSION,
    apply_baseline_schema,
    data_quality_policy,
    dataset,
    dataset_contract,
    deployment_history,
    execution_policy,
    load_policy,
    orchestration_policy,
    ordering_policy,
    reconciliation_policy,
)
from .control_plane_stage_policy import apply_execution_policy
from .deployment import (
    DeploymentPlan,
    DeploymentProvenance,
    EnvironmentBindings,
    ReleaseBundleIdentity,
    ReleaseManifest,
    build_deployment_plan,
)


def load_dataset_configs(config_dir: str | Path) -> tuple[DatasetConfig, ...]:
    root = Path(config_dir)
    paths = sorted(root.glob("*.json"))
    if not paths:
        raise ValueError(f"no dataset JSON files found in {root}")
    configs = tuple(
        DatasetConfig.model_validate_json(path.read_text(encoding="utf-8")) for path in paths
    )
    dataset_ids = [config.dataset_id for config in configs]
    if len(set(dataset_ids)) != len(dataset_ids):
        raise ValueError("dataset config bundle contains duplicate dataset_id values")
    return tuple(sorted(configs, key=lambda config: config.dataset_id))


def config_bundle_hash(configs: Iterable[DatasetConfig]) -> str:
    ordered = sorted(configs, key=lambda config: config.dataset_id)
    if not ordered:
        raise ValueError("config bundle must contain at least one dataset")
    return canonical_hash([config.model_dump(mode="json") for config in ordered])


def artifact_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release_manifest(
    *,
    domain: str,
    domain_release_version: str,
    domain_git_sha: str,
    framework_version: str,
    configs: Iterable[DatasetConfig],
    config_schema_version: int,
    fabric_item_manifest_version: str,
    build_id: str,
    artifacts: dict[str, str | Path] | None = None,
    generated_at: datetime | None = None,
) -> ReleaseManifest:
    config_tuple = tuple(configs)
    digests = {
        name: artifact_sha256(path) for name, path in sorted((artifacts or {}).items())
    }
    return ReleaseManifest(
        domain=domain,
        bundle=ReleaseBundleIdentity(
            domain_release_version=domain_release_version,
            domain_git_sha=domain_git_sha,
            framework_version=framework_version,
            config_bundle_hash=config_bundle_hash(config_tuple),
            config_schema_version=config_schema_version,
            control_plane_schema_version=CONTROL_PLANE_SCHEMA_VERSION,
            fabric_item_manifest_version=fabric_item_manifest_version,
            build_id=build_id,
        ),
        generated_at=generated_at or datetime.now(timezone.utc),
        artifact_sha256=digests,
    )


def write_json_model(model: object, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(model, "model_dump_json"):
        payload = model.model_dump_json(indent=2)  # type: ignore[attr-defined]
    else:
        payload = json.dumps(model, indent=2, sort_keys=True)
    output.write_text(payload + "\n", encoding="utf-8")


def load_release_manifest(path: str | Path) -> ReleaseManifest:
    return ReleaseManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_environment_bindings(path: str | Path) -> EnvironmentBindings:
    return EnvironmentBindings.model_validate_json(Path(path).read_text(encoding="utf-8"))


def validate_release_tag(tag: str, package_version: str) -> None:
    expected = f"v{package_version}"
    if tag != expected:
        raise ValueError(f"release tag {tag!r} does not match package version {expected!r}")


def _upsert_definition(
    connection,
    table,
    key: dict[str, object],
    insert_values: dict[str, object],
    update_values: dict[str, object],
) -> None:
    predicate = and_(*(table.c[column] == value for column, value in key.items()))
    exists = connection.execute(select(table).where(predicate).limit(1)).first() is not None
    if exists:
        connection.execute(update(table).where(predicate).values(**update_values))
    else:
        connection.execute(table.insert().values(**insert_values))


def materialize_semantic_metadata(
    engine: Engine,
    *,
    configs: Iterable[DatasetConfig],
    domain: str,
    domain_git_sha: str,
    framework_version: str,
) -> str:
    """Idempotently materialize Git semantic definitions while preserving runtime state."""

    config_tuple = tuple(sorted(configs, key=lambda config: config.dataset_id))
    bundle_hash = config_bundle_hash(config_tuple)
    apply_baseline_schema(engine)
    now = datetime.now(timezone.utc)

    with engine.begin() as connection:
        for config in config_tuple:
            common_audit = {"updated_at": now}
            dataset_insert = {
                "dataset_id": config.dataset_id,
                "domain": domain,
                "source_system": config.source.system,
                "source_object": config.source.object,
                "target_layer": config.target.layer,
                "target_object": config.target.object,
                "enabled_default": config.enabled,
                "criticality": config.orchestration.criticality.value,
                "execution_group": config.orchestration.execution_group,
                "config_schema_version": config.config_schema_version,
                "config_hash": config.config_hash,
                "domain_git_sha": domain_git_sha,
                "framework_version": framework_version,
                "created_at": now,
                "updated_at": None,
            }
            _upsert_definition(
                connection,
                dataset,
                {"dataset_id": config.dataset_id},
                dataset_insert,
                {**dataset_insert, **common_audit},
            )

            if config.schema_contract is not None:
                contract = config.schema_contract
                contract_values = {
                    "dataset_id": config.dataset_id,
                    "contract_version": contract.contract_version,
                    "schema_fingerprint": contract.fingerprint,
                    "compatibility_policy": contract.compatibility_policy.value,
                    "definition": contract.persisted_definition(),
                    "created_at": now,
                    "updated_at": None,
                }
                _upsert_definition(
                    connection,
                    dataset_contract,
                    {
                        "dataset_id": config.dataset_id,
                        "contract_version": contract.contract_version,
                    },
                    contract_values,
                    {**contract_values, **common_audit},
                )

            watermark_config = config.load.watermark
            load_values = {
                "dataset_id": config.dataset_id,
                "capture_strategy": config.load.capture_strategy.value,
                "apply_strategy": config.load.apply_strategy.value,
                "business_key": list(config.load.business_key),
                "merge_key": list(config.load.merge_key),
                "append_identity": list(config.load.append_identity),
                "watermark_column": watermark_config.column if watermark_config else None,
                "watermark_tie_breaker": list(watermark_config.tie_breaker)
                if watermark_config
                else None,
                "watermark_overlap_seconds": watermark_config.overlap_window_seconds
                if watermark_config
                else 0,
                "event_time_column": config.load.event_time_column,
                "tracked_columns": list(config.load.tracked_columns),
                "delete_policy": config.load.delete_policy,
                "created_at": now,
                "updated_at": None,
            }
            _upsert_definition(
                connection,
                load_policy,
                {"dataset_id": config.dataset_id},
                load_values,
                {**load_values, **common_audit},
            )

            ordering_values = {
                "dataset_id": config.dataset_id,
                "event_time_column": config.load.event_time_column,
                "version_column": config.load.version_column,
                "sequence_column": config.load.sequence_column,
                "created_at": now,
                "updated_at": None,
            }
            _upsert_definition(
                connection,
                ordering_policy,
                {"dataset_id": config.dataset_id},
                ordering_values,
                {**ordering_values, **common_audit},
            )

            execution_values = {
                "dataset_id": config.dataset_id,
                "execution_engine": config.execution.engine.value,
                "progress_owner": config.execution.progress_owner.value,
                "capability_profile": config.execution.capability_profile,
                "extensions": config.extensions.model_dump(mode="json"),
                "created_at": now,
                "updated_at": None,
            }
            _upsert_definition(
                connection,
                execution_policy,
                {"dataset_id": config.dataset_id},
                execution_values,
                {**execution_values, **common_audit},
            )

            apply_execution_values = {
                "dataset_id": config.dataset_id,
                "execution_engine": config.execution.apply_engine.value,
                "capability_profile": config.execution.apply_capability_profile,
                "created_at": now,
                "updated_at": None,
            }
            _upsert_definition(
                connection,
                apply_execution_policy,
                {"dataset_id": config.dataset_id},
                apply_execution_values,
                {**apply_execution_values, **common_audit},
            )

            orchestration_values = {
                "dataset_id": config.dataset_id,
                "execution_group": config.orchestration.execution_group,
                "criticality": config.orchestration.criticality.value,
                "dependencies": list(config.orchestration.dependencies),
                "priority": config.orchestration.priority,
                "retry_count": config.orchestration.retry_count,
                "timeout_seconds": config.orchestration.timeout_seconds,
                "batch_size": config.orchestration.batch_size,
                "max_concurrency": config.orchestration.max_concurrency,
                "created_at": now,
                "updated_at": None,
            }
            _upsert_definition(
                connection,
                orchestration_policy,
                {"dataset_id": config.dataset_id},
                orchestration_values,
                {**orchestration_values, **common_audit},
            )

            quality_values = {
                "dataset_id": config.dataset_id,
                "policy_name": config.quality.policy_name,
                "quarantine_policy": config.quality.quarantine_policy,
                "definition": None,
                "created_at": now,
                "updated_at": None,
            }
            _upsert_definition(
                connection,
                data_quality_policy,
                {"dataset_id": config.dataset_id},
                quality_values,
                {**quality_values, **common_audit},
            )

            reconciliation_values = {
                "dataset_id": config.dataset_id,
                "policy_name": config.reconciliation.policy_name,
                "required_for_state_commit": config.reconciliation.required_for_state_commit,
                "definition": None,
                "created_at": now,
                "updated_at": None,
            }
            _upsert_definition(
                connection,
                reconciliation_policy,
                {"dataset_id": config.dataset_id},
                reconciliation_values,
                {**reconciliation_values, **common_audit},
            )

    return bundle_hash


def record_deployment_history(engine: Engine, provenance: DeploymentProvenance) -> None:
    apply_baseline_schema(engine)
    bundle = provenance.bundle
    with engine.begin() as connection:
        existing = connection.execute(
            select(deployment_history.c.deployment_id).where(
                deployment_history.c.deployment_id == str(provenance.deployment_id)
            )
        ).first()
        if existing is not None:
            raise ValueError(f"deployment {provenance.deployment_id} is already recorded")
        connection.execute(
            deployment_history.insert().values(
                deployment_id=str(provenance.deployment_id),
                environment=provenance.environment.value,
                domain=provenance.domain,
                domain_release_version=bundle.domain_release_version,
                domain_git_sha=bundle.domain_git_sha,
                framework_version=bundle.framework_version,
                config_bundle_hash=bundle.config_bundle_hash,
                control_plane_schema_version=bundle.control_plane_schema_version,
                fabric_item_manifest_version=bundle.fabric_item_manifest_version,
                deployment_mechanism=provenance.deployment_mechanism.value,
                ci_provider=provenance.ci_provider.value,
                build_id=bundle.build_id,
                initiated_by=provenance.initiated_by,
                approved_by=provenance.approved_by,
                started_at=provenance.started_at,
                completed_at=provenance.completed_at,
                status=provenance.status,
                previous_deployment_id=(
                    str(provenance.previous_deployment_id)
                    if provenance.previous_deployment_id
                    else None
                ),
            )
        )


def plan_deployment(
    manifest: ReleaseManifest,
    bindings: EnvironmentBindings,
) -> DeploymentPlan:
    return build_deployment_plan(manifest, bindings)
