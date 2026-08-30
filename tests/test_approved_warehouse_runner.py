from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select

from fabric_data_framework.evidence.approved_warehouse_runner import (
    ApprovedWarehouseRunConfig,
    WarehouseAmbiguityOrigin,
    execute_approved_warehouse,
)
from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.deployment.delivery import build_release_manifest, materialize_semantic_metadata
from fabric_data_framework.extensions import ExtensionKind, ExtensionRegistry
from fabric_data_framework.infrastructure import EnvironmentName
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
)
from fabric_data_framework.evidence.integration_runner import ApprovedIntegrationRunnerConfig
from fabric_data_framework.recovery.fabric_warehouse import (
    FabricWarehouseMarkerStore,
    FabricWarehouseMutationEvidence,
    build_fabric_warehouse_operation_marker_table,
)
from fabric_data_framework.control_plane.target_operation_journal import (
    read_target_operation,
    read_target_operation_events,
)
from fabric_data_framework.target_operations import TargetOperationStatus


NOW = datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc)
FRAMEWORK_VERSION = "0.4.0"
DOMAIN_GIT_SHA = "1" * 40
EXTENSION_ARTIFACT = "fabric-customer-0.4.0.dev1-py3-none-any.whl"


class TrackingEnvironment(Mapping[str, str]):
    def __init__(self, values: dict[str, str]):
        self.values = values
        self.getitem_calls: list[str] = []
        self.presence_checks: list[str] = []

    def __getitem__(self, key: str) -> str:
        self.getitem_calls.append(key)
        return self.values[key]

    def get(self, key: str, default=None):
        self.presence_checks.append(key)
        return "present" if key in self.values and self.values[key].strip() else default

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


def _dataset() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="sales.order",
        source=SourceConfig(system="erp", object="dbo.SalesOrder"),
        target=TargetConfig(layer="gold", object="sales_order"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(execution_group="sales"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="count"),
    )


def _release(configs: tuple[DatasetConfig, ...], *, extension=True):
    release = build_release_manifest(
        domain="sales",
        domain_release_version="0.4.0-dev",
        domain_git_sha=DOMAIN_GIT_SHA,
        framework_version=FRAMEWORK_VERSION,
        configs=configs,
        config_schema_version=1,
        fabric_item_manifest_version="dev-v1",
        build_id="warehouse-runner-test",
        generated_at=NOW,
    )
    if extension:
        release = release.model_copy(
            update={"artifact_sha256": {EXTENSION_ARTIFACT: "a" * 64}}
        )
    return release


def _spec(release_hash: str) -> IntegrationEvidenceSpec:
    return IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="sales",
        framework_version=FRAMEWORK_VERSION,
        release_hash=release_hash,
        checks=(
            IntegrationEvidenceCheckSpec(
                check_id="fabric.item.read",
                kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            ),
            IntegrationEvidenceCheckSpec(
                check_id="control-plane.certify",
                kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            ),
            IntegrationEvidenceCheckSpec(
                check_id="warehouse.commit",
                kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
            ),
        ),
    )


def _prerequisite(
    spec: IntegrationEvidenceSpec,
    *,
    warehouse_status=IntegrationEvidenceStatus.NOT_RUN,
    control_status=IntegrationEvidenceStatus.PASS,
):
    return IntegrationEvidenceManifest(
        environment=spec.environment,
        domain=spec.domain,
        framework_version=spec.framework_version,
        release_hash=spec.release_hash,
        started_at=NOW,
        completed_at=NOW,
        checks=spec.checks,
        results=(
            IntegrationEvidenceCheckResult(
                check_id="fabric.item.read",
                kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
                status=IntegrationEvidenceStatus.PASS,
                workspace_id=uuid4(),
                item_id=uuid4(),
                evidence_references=("artifact:item-read",),
            ),
            IntegrationEvidenceCheckResult(
                check_id="control-plane.certify",
                kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
                status=control_status,
                evidence_references=("artifact:control-plane",)
                if control_status is IntegrationEvidenceStatus.PASS
                else (),
            ),
            IntegrationEvidenceCheckResult(
                check_id="warehouse.commit",
                kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
                status=warehouse_status,
                operation_key=("b" * 64)
                if warehouse_status is IntegrationEvidenceStatus.PASS
                else None,
                evidence_references=("artifact:old-warehouse",)
                if warehouse_status is IntegrationEvidenceStatus.PASS
                else (),
            ),
        ),
    )


def _runner_config(release_hash: str):
    return ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="sales",
        framework_version=FRAMEWORK_VERSION,
        release_hash=release_hash,
        control_plane_profile="fabric_sql_database_v1",
        control_plane_database_url_env_var="CONTROL_PLANE_DATABASE_URL",
        warehouse_database_url_env_var="WAREHOUSE_DATABASE_URL",
    )


def _run_config() -> ApprovedWarehouseRunConfig:
    return ApprovedWarehouseRunConfig(
        check_id="warehouse.commit",
        dataset_id="sales.order",
        operation_kind="EVIDENCE_MERGE",
        target_reference="warehouse.dbo.sales_order",
        mutation_extension="sales.order.evidence-mutation",
        extension_artifact_name=EXTENSION_ARTIFACT,
        mutation_payload={"order_id": 42, "value": "approved-evidence"},
        marker_schema=None,
    )


def _prepare_control(path: Path, configs: tuple[DatasetConfig, ...]) -> str:
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    try:
        materialize_semantic_metadata(
            engine,
            configs=configs,
            domain="sales",
            domain_git_sha=DOMAIN_GIT_SHA,
            framework_version=FRAMEWORK_VERSION,
        )
    finally:
        engine.dispose()
    return url


def _prepare_warehouse(path: Path):
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    metadata = MetaData()
    target = Table(
        "sales_order",
        metadata,
        Column("order_id", Integer, nullable=False),
        Column("value", String(100), nullable=False),
    )
    build_fabric_warehouse_operation_marker_table(metadata, schema=None)
    metadata.create_all(engine)
    engine.dispose()
    return url, target


def _registry(target: Table, *, raises: bool = False):
    registry = ExtensionRegistry()

    def mutation(connection, intent, payload):
        if raises:
            raise RuntimeError("mutation extension failed before commit")
        connection.execute(
            target.insert().values(
                order_id=int(payload["order_id"]),
                value=str(payload["value"]),
            )
        )
        return FabricWarehouseMutationEvidence(
            native_operation_id="statement-evidence-42",
            query_label="FDF_EVIDENCE_SALES_ORDER",
            detail="representative mutation completed before framework marker insert",
        )

    registry.register(
        ExtensionKind.WAREHOUSE_MUTATION,
        "sales.order.evidence-mutation",
        mutation,
    )
    return registry


def _result(execution):
    return next(
        item for item in execution.manifest.results if item.check_id == "warehouse.commit"
    )


def test_warehouse_preflight_requires_both_control_and_target_runtime_urls():
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)

    with pytest.raises(ValueError, match="missing runtime env vars") as exc:
        execute_approved_warehouse(
            config=_runner_config(release.bundle.release_hash),
            spec=spec,
            prerequisite_manifest=_prerequisite(spec),
            release_manifest=release,
            configs=configs,
            run_config=_run_config(),
            environ={},
            evidence_references=("artifact:warehouse",),
            allow_warehouse_execution=True,
            extension_registry=ExtensionRegistry(),
        )
    assert "CONTROL_PLANE_DATABASE_URL" in str(exc.value)
    assert "WAREHOUSE_DATABASE_URL" in str(exc.value)


def test_warehouse_authorization_gate_prevents_secret_url_retrieval():
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    env = TrackingEnvironment(
        {
            "CONTROL_PLANE_DATABASE_URL": "sqlite:///control-secret.db",
            "WAREHOUSE_DATABASE_URL": "sqlite:///warehouse-secret.db",
        }
    )

    with pytest.raises(ValueError, match="not explicitly authorized"):
        execute_approved_warehouse(
            config=_runner_config(release.bundle.release_hash),
            spec=spec,
            prerequisite_manifest=_prerequisite(spec),
            release_manifest=release,
            configs=configs,
            run_config=_run_config(),
            environ=env,
            evidence_references=("artifact:warehouse",),
            allow_warehouse_execution=False,
            extension_registry=ExtensionRegistry(),
        )
    assert env.getitem_calls == []


def test_warehouse_requires_prerequisite_pass_and_not_run_selected_check_before_secret_read():
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    env = TrackingEnvironment(
        {
            "CONTROL_PLANE_DATABASE_URL": "sqlite:///control-secret.db",
            "WAREHOUSE_DATABASE_URL": "sqlite:///warehouse-secret.db",
        }
    )
    common = dict(
        config=_runner_config(release.bundle.release_hash),
        spec=spec,
        release_manifest=release,
        configs=configs,
        run_config=_run_config(),
        environ=env,
        evidence_references=("artifact:warehouse",),
        allow_warehouse_execution=True,
        extension_registry=ExtensionRegistry(),
    )

    with pytest.raises(ValueError, match="control-plane certification"):
        execute_approved_warehouse(
            prerequisite_manifest=_prerequisite(
                spec, control_status=IntegrationEvidenceStatus.NOT_RUN
            ),
            **common,
        )
    with pytest.raises(ValueError, match="remain NOT_RUN"):
        execute_approved_warehouse(
            prerequisite_manifest=_prerequisite(
                spec, warehouse_status=IntegrationEvidenceStatus.PASS
            ),
            **common,
        )
    assert env.getitem_calls == []


def test_warehouse_extension_artifact_must_be_fingerprinted_before_secret_read():
    configs = (_dataset(),)
    release = _release(configs, extension=False)
    spec = _spec(release.bundle.release_hash)
    env = TrackingEnvironment(
        {
            "CONTROL_PLANE_DATABASE_URL": "sqlite:///control-secret.db",
            "WAREHOUSE_DATABASE_URL": "sqlite:///warehouse-secret.db",
        }
    )

    with pytest.raises(ValueError, match="not fingerprinted"):
        execute_approved_warehouse(
            config=_runner_config(release.bundle.release_hash),
            spec=spec,
            prerequisite_manifest=_prerequisite(spec),
            release_manifest=release,
            configs=configs,
            run_config=_run_config(),
            environ=env,
            evidence_references=("artifact:warehouse",),
            allow_warehouse_execution=True,
            extension_registry=ExtensionRegistry(),
        )
    assert env.getitem_calls == []


def test_same_transaction_commit_then_simulated_lost_ack_reconciles_and_blocks_reexecution(
    tmp_path: Path,
):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    control_url = _prepare_control(tmp_path / "control.db", configs)
    warehouse_url, target = _prepare_warehouse(tmp_path / "warehouse.db")

    execution = execute_approved_warehouse(
        config=_runner_config(release.bundle.release_hash),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        run_config=_run_config(),
        environ={
            "CONTROL_PLANE_DATABASE_URL": control_url,
            "WAREHOUSE_DATABASE_URL": warehouse_url,
        },
        evidence_references=("artifact:warehouse-transaction",),
        allow_warehouse_execution=True,
        extension_registry=_registry(target),
    )

    result = _result(execution)
    assert result.status is IntegrationEvidenceStatus.PASS
    assert result.operation_key
    assert result.native_operation_id == "statement-evidence-42"
    assert execution.report is not None
    assert (
        execution.report.ambiguity_origin
        is WarehouseAmbiguityOrigin.SIMULATED_FRAMEWORK_ACK_LOSS
    )
    assert execution.report.probe_resolution.value == "COMMITTED"
    assert execution.report.final_status is TargetOperationStatus.SUCCEEDED
    assert execution.report.reentry_action == "SKIP_SUCCEEDED"

    warehouse = create_engine(warehouse_url)
    try:
        with warehouse.connect() as connection:
            rows = connection.execute(select(target)).mappings().all()
        assert [dict(row) for row in rows] == [
            {"order_id": 42, "value": "approved-evidence"}
        ]
    finally:
        warehouse.dispose()

    control = create_engine(control_url)
    try:
        current = read_target_operation(control, result.operation_key)
        events = read_target_operation_events(control, result.operation_key)
        assert current is not None
        assert current.status is TargetOperationStatus.SUCCEEDED
        assert [event.to_status for event in events] == [
            TargetOperationStatus.IN_PROGRESS,
            TargetOperationStatus.UNKNOWN,
            TargetOperationStatus.SUCCEEDED,
        ]
    finally:
        control.dispose()


def test_provider_exception_after_committed_marker_is_recovered_without_leaking_message(
    tmp_path: Path,
):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    control_url = _prepare_control(tmp_path / "control.db", configs)
    warehouse_url, target = _prepare_warehouse(tmp_path / "warehouse.db")

    class LostAckStore:
        def __init__(self, inner):
            self.inner = inner

        def execute_atomic(self, **kwargs):
            self.inner.execute_atomic(**kwargs)
            raise RuntimeError("driver error password=should-never-be-retained")

        def read_markers(self, operation_key):
            return self.inner.read_markers(operation_key)

        def marker_reference(self, operation_key):
            return self.inner.marker_reference(operation_key)

    def factory(engine, run_config):
        marker = build_fabric_warehouse_operation_marker_table(
            MetaData(),
            table_name=run_config.marker_table_name,
            schema=run_config.marker_schema,
        )
        return LostAckStore(FabricWarehouseMarkerStore(engine, marker))

    execution = execute_approved_warehouse(
        config=_runner_config(release.bundle.release_hash),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        run_config=_run_config(),
        environ={
            "CONTROL_PLANE_DATABASE_URL": control_url,
            "WAREHOUSE_DATABASE_URL": warehouse_url,
        },
        evidence_references=("artifact:warehouse-provider-ambiguity",),
        allow_warehouse_execution=True,
        extension_registry=_registry(target),
        marker_store_factory=factory,
    )

    result = _result(execution)
    assert result.status is IntegrationEvidenceStatus.PASS
    assert execution.report is not None
    assert (
        execution.report.ambiguity_origin
        is WarehouseAmbiguityOrigin.PROVIDER_OR_DRIVER_EXCEPTION
    )
    assert execution.report.execution_exception_type == "RuntimeError"
    rendered = execution.report.model_dump_json() + execution.manifest.model_dump_json()
    assert "should-never-be-retained" not in rendered
    assert "password=" not in rendered.lower()


def test_provider_exception_with_absent_marker_remains_unknown_and_never_retries(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    control_url = _prepare_control(tmp_path / "control.db", configs)
    warehouse_url, target = _prepare_warehouse(tmp_path / "warehouse.db")

    class FailsBeforeTransactionStore:
        def __init__(self, inner):
            self.inner = inner

        def execute_atomic(self, **kwargs):
            raise RuntimeError("connection failed Authorization: Bearer should-not-leak")

        def read_markers(self, operation_key):
            return self.inner.read_markers(operation_key)

        def marker_reference(self, operation_key):
            return self.inner.marker_reference(operation_key)

    def factory(engine, run_config):
        marker = build_fabric_warehouse_operation_marker_table(
            MetaData(),
            table_name=run_config.marker_table_name,
            schema=run_config.marker_schema,
        )
        return FailsBeforeTransactionStore(FabricWarehouseMarkerStore(engine, marker))

    execution = execute_approved_warehouse(
        config=_runner_config(release.bundle.release_hash),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        run_config=_run_config(),
        environ={
            "CONTROL_PLANE_DATABASE_URL": control_url,
            "WAREHOUSE_DATABASE_URL": warehouse_url,
        },
        evidence_references=("artifact:warehouse-unresolved",),
        allow_warehouse_execution=True,
        extension_registry=_registry(target),
        marker_store_factory=factory,
    )

    result = _result(execution)
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert "UNRESOLVED" in (result.detail or "")
    assert execution.report is None
    assert "should-not-leak" not in execution.manifest.model_dump_json()

    control = create_engine(control_url)
    try:
        current = read_target_operation(control, result.operation_key)
        assert current is not None
        assert current.status is TargetOperationStatus.UNKNOWN
    finally:
        control.dispose()

    warehouse = create_engine(warehouse_url)
    try:
        with warehouse.connect() as connection:
            rows = connection.execute(select(target)).all()
        assert rows == []
    finally:
        warehouse.dispose()


def test_mutation_extension_exception_rolls_back_and_still_fails_closed_unknown(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    control_url = _prepare_control(tmp_path / "control.db", configs)
    warehouse_url, target = _prepare_warehouse(tmp_path / "warehouse.db")

    execution = execute_approved_warehouse(
        config=_runner_config(release.bundle.release_hash),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        run_config=_run_config(),
        environ={
            "CONTROL_PLANE_DATABASE_URL": control_url,
            "WAREHOUSE_DATABASE_URL": warehouse_url,
        },
        evidence_references=("artifact:warehouse-mutation-fail",),
        allow_warehouse_execution=True,
        extension_registry=_registry(target, raises=True),
    )

    result = _result(execution)
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert execution.report is None
    warehouse = create_engine(warehouse_url)
    try:
        with warehouse.connect() as connection:
            rows = connection.execute(select(target)).all()
        assert rows == []
    finally:
        warehouse.dispose()


def test_warehouse_run_config_rejects_credential_like_target_or_payload():
    with pytest.raises(ValidationError, match="credential material"):
        ApprovedWarehouseRunConfig(
            check_id="warehouse.commit",
            dataset_id="sales.order",
            operation_kind="EVIDENCE_MERGE",
            target_reference="https://example.test/path?sig=secret",
            mutation_extension="sales.order.evidence-mutation",
            extension_artifact_name=EXTENSION_ARTIFACT,
        )
