from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select

from fabric_data_framework.evidence.approved_warehouse_fault_runner import (
    ApprovedWarehouseFaultDrillConfig,
    execute_approved_warehouse_fault_drill,
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
from fabric_data_framework.delivery import build_release_manifest, materialize_semantic_metadata
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
from fabric_data_framework.recovery.warehouse_fault_injection import (
    FabricWarehouseCommitFaultArmEvidence,
    FabricWarehouseCommitFaultVerification,
    WarehouseCommitFaultPhase,
)
from fabric_data_framework.target_operation_io import read_target_operation
from fabric_data_framework.target_operations import TargetOperationStatus


NOW = datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc)
FRAMEWORK_VERSION = "0.4.0"
DOMAIN_GIT_SHA = "1" * 40
MUTATION_ARTIFACT = "fabric-customer-0.4.0.dev1-py3-none-any.whl"
FAULT_ARTIFACT = "fabric-customer-faults-0.4.0.dev1-py3-none-any.whl"


class TrackingEnvironment(Mapping[str, str]):
    def __init__(self, values: dict[str, str]):
        self.values = values
        self.getitem_calls: list[str] = []

    def __getitem__(self, key: str) -> str:
        self.getitem_calls.append(key)
        return self.values[key]

    def get(self, key: str, default=None):
        value = self.values.get(key)
        return "present" if value and value.strip() else default

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


def _release(configs: tuple[DatasetConfig, ...], *, include_fault=True):
    release = build_release_manifest(
        domain="sales",
        domain_release_version="0.4.0-dev",
        domain_git_sha=DOMAIN_GIT_SHA,
        framework_version=FRAMEWORK_VERSION,
        configs=configs,
        config_schema_version=1,
        fabric_item_manifest_version="dev-v1",
        build_id="warehouse-fault-runner-test",
        generated_at=NOW,
    )
    artifacts = {MUTATION_ARTIFACT: "a" * 64}
    if include_fault:
        artifacts[FAULT_ARTIFACT] = "b" * 64
    return release.model_copy(update={"artifact_sha256": artifacts})


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
            IntegrationEvidenceCheckSpec(
                check_id="warehouse.ambiguous-commit",
                kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL,
            ),
        ),
    )


def _prerequisite(
    spec: IntegrationEvidenceSpec,
    *,
    normal_warehouse_status=IntegrationEvidenceStatus.PASS,
    drill_status=IntegrationEvidenceStatus.NOT_RUN,
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
                status=IntegrationEvidenceStatus.PASS,
                evidence_references=("artifact:control-plane",),
            ),
            IntegrationEvidenceCheckResult(
                check_id="warehouse.commit",
                kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
                status=normal_warehouse_status,
                operation_key=("a" * 64)
                if normal_warehouse_status is IntegrationEvidenceStatus.PASS
                else None,
                evidence_references=("artifact:warehouse-normal",)
                if normal_warehouse_status is IntegrationEvidenceStatus.PASS
                else (),
            ),
            IntegrationEvidenceCheckResult(
                check_id="warehouse.ambiguous-commit",
                kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL,
                status=drill_status,
                operation_key=("b" * 64)
                if drill_status is IntegrationEvidenceStatus.PASS
                else None,
                dataset_run_id=uuid4()
                if drill_status is IntegrationEvidenceStatus.PASS
                else None,
                evidence_references=("artifact:old-fault-drill",)
                if drill_status is IntegrationEvidenceStatus.PASS
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


def _run_config() -> ApprovedWarehouseFaultDrillConfig:
    return ApprovedWarehouseFaultDrillConfig(
        check_id="warehouse.ambiguous-commit",
        dataset_id="sales.order",
        operation_kind="EVIDENCE_AMBIGUOUS_COMMIT_DRILL",
        target_reference="warehouse.dbo.sales_order",
        mutation_extension="sales.order.evidence-mutation",
        mutation_extension_artifact_name=MUTATION_ARTIFACT,
        mutation_payload={"order_id": 42, "value": "fault-evidence"},
        fault_injector_extension="sales.order.commit-ack-fault",
        fault_injector_artifact_name=FAULT_ARTIFACT,
        fault_payload={"fault_case": "commit-ack-disconnect"},
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


class FaultController:
    def __init__(self, *, triggered=True, armed=True, verify_id="fault-42"):
        self.triggered = triggered
        self.armed = armed
        self.verify_id = verify_id
        self.disarmed = False

    def arm(self, request):
        return FabricWarehouseCommitFaultArmEvidence(
            armed=self.armed,
            phase=WarehouseCommitFaultPhase.COMMIT_ACKNOWLEDGEMENT,
            evidence_reference="artifact:fault-42",
            provider_fault_id="fault-42",
        )

    def disarm(self, request):
        self.disarmed = True

    def verify(self, request, *, observed_exception_type, probe_evidence):
        assert self.disarmed
        return FabricWarehouseCommitFaultVerification(
            triggered=self.triggered,
            phase=WarehouseCommitFaultPhase.COMMIT_ACKNOWLEDGEMENT,
            evidence_reference="artifact:fault-42",
            provider_fault_id=self.verify_id,
        )


def _registry(target: Table, controller: FaultController):
    registry = ExtensionRegistry()

    def mutation(connection, intent, payload):
        connection.execute(
            target.insert().values(
                order_id=int(payload["order_id"]),
                value=str(payload["value"]),
            )
        )
        return FabricWarehouseMutationEvidence(native_operation_id="statement-42")

    def fault_factory(engine, request, payload):
        assert payload["fault_case"] == "commit-ack-disconnect"
        return controller

    registry.register(
        ExtensionKind.WAREHOUSE_MUTATION,
        "sales.order.evidence-mutation",
        mutation,
    )
    registry.register(
        ExtensionKind.WAREHOUSE_COMMIT_FAULT_INJECTOR,
        "sales.order.commit-ack-fault",
        fault_factory,
    )
    return registry


def _commit_then_raise_factory(engine, run_config):
    marker = build_fabric_warehouse_operation_marker_table(
        MetaData(),
        table_name=run_config.marker_table_name,
        schema=run_config.marker_schema,
    )
    inner = FabricWarehouseMarkerStore(engine, marker)

    class CommitThenRaiseStore:
        def execute_atomic(self, **kwargs):
            inner.execute_atomic(**kwargs)
            raise RuntimeError("driver disconnect password=must-not-persist")

        def read_markers(self, operation_key):
            return inner.read_markers(operation_key)

        def marker_reference(self, operation_key):
            return inner.marker_reference(operation_key)

    return CommitThenRaiseStore()


def _fails_before_commit_factory(engine, run_config):
    marker = build_fabric_warehouse_operation_marker_table(
        MetaData(),
        table_name=run_config.marker_table_name,
        schema=run_config.marker_schema,
    )
    inner = FabricWarehouseMarkerStore(engine, marker)

    class FailsBeforeCommitStore:
        def execute_atomic(self, **kwargs):
            raise RuntimeError("Authorization: Bearer must-not-persist")

        def read_markers(self, operation_key):
            return inner.read_markers(operation_key)

        def marker_reference(self, operation_key):
            return inner.marker_reference(operation_key)

    return FailsBeforeCommitStore()


def _result(execution):
    return next(
        item
        for item in execution.manifest.results
        if item.check_id == "warehouse.ambiguous-commit"
    )


def test_fault_drill_authorization_gate_prevents_secret_url_retrieval():
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
        execute_approved_warehouse_fault_drill(
            config=_runner_config(release.bundle.release_hash),
            spec=spec,
            prerequisite_manifest=_prerequisite(spec),
            release_manifest=release,
            configs=configs,
            run_config=_run_config(),
            environ=env,
            evidence_references=("artifact:fault-drill",),
            allow_warehouse_fault_injection=False,
            extension_registry=ExtensionRegistry(),
        )
    assert env.getitem_calls == []


def test_fault_drill_requires_normal_warehouse_pass_before_secret_read():
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    env = TrackingEnvironment(
        {
            "CONTROL_PLANE_DATABASE_URL": "sqlite:///control-secret.db",
            "WAREHOUSE_DATABASE_URL": "sqlite:///warehouse-secret.db",
        }
    )

    with pytest.raises(ValueError, match="normal approved Warehouse"):
        execute_approved_warehouse_fault_drill(
            config=_runner_config(release.bundle.release_hash),
            spec=spec,
            prerequisite_manifest=_prerequisite(
                spec, normal_warehouse_status=IntegrationEvidenceStatus.NOT_RUN
            ),
            release_manifest=release,
            configs=configs,
            run_config=_run_config(),
            environ=env,
            evidence_references=("artifact:fault-drill",),
            allow_warehouse_fault_injection=True,
            extension_registry=ExtensionRegistry(),
        )
    assert env.getitem_calls == []


def test_fault_injector_artifact_must_be_fingerprinted_before_secret_read():
    configs = (_dataset(),)
    release = _release(configs, include_fault=False)
    spec = _spec(release.bundle.release_hash)
    env = TrackingEnvironment(
        {
            "CONTROL_PLANE_DATABASE_URL": "sqlite:///control-secret.db",
            "WAREHOUSE_DATABASE_URL": "sqlite:///warehouse-secret.db",
        }
    )

    with pytest.raises(ValueError, match="fault injector extension artifact"):
        execute_approved_warehouse_fault_drill(
            config=_runner_config(release.bundle.release_hash),
            spec=spec,
            prerequisite_manifest=_prerequisite(spec),
            release_manifest=release,
            configs=configs,
            run_config=_run_config(),
            environ=env,
            evidence_references=("artifact:fault-drill",),
            allow_warehouse_fault_injection=True,
            extension_registry=ExtensionRegistry(),
        )
    assert env.getitem_calls == []


def test_actual_exception_committed_marker_and_verified_fault_pass(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    control_url = _prepare_control(tmp_path / "control.db", configs)
    warehouse_url, target = _prepare_warehouse(tmp_path / "warehouse.db")
    controller = FaultController()

    execution = execute_approved_warehouse_fault_drill(
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
        evidence_references=("artifact:real-fault-drill",),
        allow_warehouse_fault_injection=True,
        extension_registry=_registry(target, controller),
        marker_store_factory=_commit_then_raise_factory,
    )

    result = _result(execution)
    assert result.status is IntegrationEvidenceStatus.PASS
    assert execution.report is not None
    assert execution.report.provider_exception_observed is True
    assert execution.report.execution_exception_type == "RuntimeError"
    assert execution.report.fault_verified is True
    assert execution.report.fault_identity_matches is True
    assert execution.report.probe_resolution.value == "COMMITTED"
    assert execution.report.final_status is TargetOperationStatus.SUCCEEDED
    assert execution.report.reentry_action == "SKIP_SUCCEEDED"
    rendered = execution.report.model_dump_json() + execution.manifest.model_dump_json()
    assert "must-not-persist" not in rendered
    assert "password=" not in rendered.lower()

    warehouse = create_engine(warehouse_url)
    try:
        with warehouse.connect() as connection:
            rows = connection.execute(select(target)).mappings().all()
        assert [dict(row) for row in rows] == [
            {"order_id": 42, "value": "fault-evidence"}
        ]
    finally:
        warehouse.dispose()


def test_normal_return_can_never_masquerade_as_real_fault_pass(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    control_url = _prepare_control(tmp_path / "control.db", configs)
    warehouse_url, target = _prepare_warehouse(tmp_path / "warehouse.db")
    controller = FaultController(triggered=True)

    execution = execute_approved_warehouse_fault_drill(
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
        evidence_references=("artifact:no-real-fault",),
        allow_warehouse_fault_injection=True,
        extension_registry=_registry(target, controller),
    )

    result = _result(execution)
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert "NO_PROVIDER_OR_DRIVER_EXCEPTION" in (result.detail or "")
    assert execution.report is not None
    assert execution.report.provider_exception_observed is False
    assert execution.report.probe_resolution.value == "COMMITTED"
    assert execution.report.final_status is TargetOperationStatus.SUCCEEDED


def test_exception_with_absent_marker_remains_unknown_and_never_retries(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    control_url = _prepare_control(tmp_path / "control.db", configs)
    warehouse_url, target = _prepare_warehouse(tmp_path / "warehouse.db")
    controller = FaultController(triggered=True)

    execution = execute_approved_warehouse_fault_drill(
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
        evidence_references=("artifact:unresolved-fault",),
        allow_warehouse_fault_injection=True,
        extension_registry=_registry(target, controller),
        marker_store_factory=_fails_before_commit_factory,
    )

    result = _result(execution)
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert "MARKER_UNRESOLVED" in (result.detail or "")
    assert execution.report is not None
    assert execution.report.probe_resolution.value == "UNRESOLVED"
    assert execution.report.final_status is TargetOperationStatus.UNKNOWN
    assert execution.report.reentry_action is None

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
            assert connection.execute(select(target)).all() == []
    finally:
        warehouse.dispose()


def test_unverified_fault_fails_even_when_marker_committed_and_journal_recovers(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    control_url = _prepare_control(tmp_path / "control.db", configs)
    warehouse_url, target = _prepare_warehouse(tmp_path / "warehouse.db")
    controller = FaultController(triggered=False)

    execution = execute_approved_warehouse_fault_drill(
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
        evidence_references=("artifact:unverified-fault",),
        allow_warehouse_fault_injection=True,
        extension_registry=_registry(target, controller),
        marker_store_factory=_commit_then_raise_factory,
    )

    result = _result(execution)
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert "FAULT_NOT_VERIFIED" in (result.detail or "")
    assert execution.report is not None
    assert execution.report.probe_resolution.value == "COMMITTED"
    assert execution.report.final_status is TargetOperationStatus.SUCCEEDED
    assert execution.report.reentry_action == "SKIP_SUCCEEDED"


def test_fault_identity_mismatch_fails_closed(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    control_url = _prepare_control(tmp_path / "control.db", configs)
    warehouse_url, target = _prepare_warehouse(tmp_path / "warehouse.db")
    controller = FaultController(triggered=True, verify_id="different-fault")

    execution = execute_approved_warehouse_fault_drill(
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
        evidence_references=("artifact:fault-id-mismatch",),
        allow_warehouse_fault_injection=True,
        extension_registry=_registry(target, controller),
        marker_store_factory=_commit_then_raise_factory,
    )

    assert _result(execution).status is IntegrationEvidenceStatus.FAIL
    assert execution.report is not None
    assert execution.report.fault_identity_matches is False
    assert execution.report.failure_reason == "FAULT_IDENTITY_MISMATCH"


def test_fault_drill_config_rejects_credential_like_payload():
    with pytest.raises(ValidationError, match="credential material"):
        ApprovedWarehouseFaultDrillConfig(
            check_id="warehouse.ambiguous-commit",
            dataset_id="sales.order",
            operation_kind="EVIDENCE_AMBIGUOUS_COMMIT_DRILL",
            target_reference="warehouse.dbo.sales_order",
            mutation_extension="sales.order.evidence-mutation",
            mutation_extension_artifact_name=MUTATION_ARTIFACT,
            fault_injector_extension="sales.order.commit-ack-fault",
            fault_injector_artifact_name=FAULT_ARTIFACT,
            fault_payload={"password": "should-not-exist"},
        )
