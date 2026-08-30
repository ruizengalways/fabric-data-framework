from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

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
from fabric_data_framework.recovery.fabric_warehouse_session_absence import (
    FabricWarehouseSessionBinding,
    FabricWarehouseSessionState,
)
from fabric_data_framework.recovery.warehouse_fault_injection import (
    FabricWarehouseCommitFaultArmEvidence,
    FabricWarehouseCommitFaultVerification,
    WarehouseCommitFaultPhase,
)
from fabric_data_framework.control_plane.target_operation_journal import read_target_operation
from fabric_data_framework.target_operations import TargetOperationStatus


NOW = datetime(2026, 8, 30, 11, 0, tzinfo=timezone.utc)
FRAMEWORK_VERSION = "0.4.0"
DOMAIN_GIT_SHA = "1" * 40
MUTATION_ARTIFACT = "fabric-customer-0.4.0.dev1-py3-none-any.whl"
FAULT_ARTIFACT = "fabric-customer-faults-0.4.0.dev1-py3-none-any.whl"
SESSION_BINDING = FabricWarehouseSessionBinding(
    session_id=81,
    connection_id=UUID("11111111-2222-3333-4444-555555555555"),
)


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
        value = self.values.get(key)
        return "present" if value and value.strip() else default

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


class FaultController:
    def __init__(self):
        self.disarmed = False

    def arm(self, request):
        return FabricWarehouseCommitFaultArmEvidence(
            armed=True,
            phase=WarehouseCommitFaultPhase.COMMIT_ACKNOWLEDGEMENT,
            evidence_reference="artifact:fault-42",
            provider_fault_id="fault-42",
        )

    def disarm(self, request):
        self.disarmed = True

    def verify(self, request, *, observed_exception_type, probe_evidence):
        assert self.disarmed
        assert observed_exception_type == "RuntimeError"
        return FabricWarehouseCommitFaultVerification(
            triggered=True,
            phase=WarehouseCommitFaultPhase.COMMIT_ACKNOWLEDGEMENT,
            evidence_reference="artifact:fault-42",
            provider_fault_id="fault-42",
        )


class FakeSessionAuthority:
    def __init__(self):
        self.observations = deque(
            [
                FabricWarehouseSessionState(
                    session_id=SESSION_BINDING.session_id,
                    connection_id=SESSION_BINDING.connection_id,
                    open_transaction_count=1,
                ),
                None,
            ]
        )
        self.terminated = []

    def observe(self, binding):
        assert binding == SESSION_BINDING
        return self.observations.popleft()

    def terminate(self, binding):
        assert binding == SESSION_BINDING
        self.terminated.append(binding)


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


def _release(configs: tuple[DatasetConfig, ...]):
    return build_release_manifest(
        domain="sales",
        domain_release_version="0.4.0-dev",
        domain_git_sha=DOMAIN_GIT_SHA,
        framework_version=FRAMEWORK_VERSION,
        configs=configs,
        config_schema_version=1,
        fabric_item_manifest_version="dev-v1",
        build_id="warehouse-session-recovery-test",
        generated_at=NOW,
    ).model_copy(
        update={
            "artifact_sha256": {
                MUTATION_ARTIFACT: "a" * 64,
                FAULT_ARTIFACT: "b" * 64,
            }
        }
    )


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


def _prerequisite(spec: IntegrationEvidenceSpec) -> IntegrationEvidenceManifest:
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
                status=IntegrationEvidenceStatus.PASS,
                operation_key="a" * 64,
                evidence_references=("artifact:warehouse-normal",),
            ),
            IntegrationEvidenceCheckResult(
                check_id="warehouse.ambiguous-commit",
                kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL,
                status=IntegrationEvidenceStatus.NOT_RUN,
            ),
        ),
    )


def _runner_config(release_hash: str, *, admin=True):
    return ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="sales",
        framework_version=FRAMEWORK_VERSION,
        release_hash=release_hash,
        control_plane_profile="fabric_sql_database_v1",
        control_plane_database_url_env_var="CONTROL_PLANE_DATABASE_URL",
        warehouse_database_url_env_var="WAREHOUSE_DATABASE_URL",
        warehouse_admin_database_url_env_var=(
            "WAREHOUSE_ADMIN_DATABASE_URL" if admin else None
        ),
    )


def _run_config(*, session_recovery=True) -> ApprovedWarehouseFaultDrillConfig:
    return ApprovedWarehouseFaultDrillConfig(
        check_id="warehouse.ambiguous-commit",
        dataset_id="sales.order",
        operation_kind="EVIDENCE_AMBIGUOUS_COMMIT_DRILL",
        target_reference="warehouse.dbo.sales_order",
        mutation_extension="sales.order.evidence-mutation",
        mutation_extension_artifact_name=MUTATION_ARTIFACT,
        mutation_payload={"order_id": 42, "value": "session-recovery"},
        fault_injector_extension="sales.order.commit-ack-fault",
        fault_injector_artifact_name=FAULT_ARTIFACT,
        fault_payload={"fault_case": "commit-ack-disconnect"},
        enable_session_termination_recovery=session_recovery,
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


def _rollback_after_mutation_factory(engine, run_config):
    marker = build_fabric_warehouse_operation_marker_table(
        MetaData(),
        table_name=run_config.marker_table_name,
        schema=run_config.marker_schema,
    )
    inner = FabricWarehouseMarkerStore(engine, marker)

    class RollbackAfterMutationStore:
        def execute_atomic(self, *, intent, dataset_run_id, attempt, mutation):
            del dataset_run_id, attempt
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    mutation(connection, intent)
                finally:
                    transaction.rollback()
            raise RuntimeError("provider disconnect Authorization: Bearer must-not-persist")

        def read_markers(self, operation_key):
            return inner.read_markers(operation_key)

        def marker_reference(self, operation_key):
            return inner.marker_reference(operation_key)

    return RollbackAfterMutationStore()


def _fails_before_mutation_factory(engine, run_config):
    marker = build_fabric_warehouse_operation_marker_table(
        MetaData(),
        table_name=run_config.marker_table_name,
        schema=run_config.marker_schema,
    )
    inner = FabricWarehouseMarkerStore(engine, marker)

    class FailsBeforeMutationStore:
        def execute_atomic(self, **kwargs):
            raise RuntimeError("connection failed before mutation")

        def read_markers(self, operation_key):
            return inner.read_markers(operation_key)

        def marker_reference(self, operation_key):
            return inner.marker_reference(operation_key)

    return FailsBeforeMutationStore()


def _result(execution):
    return next(
        item
        for item in execution.manifest.results
        if item.check_id == "warehouse.ambiguous-commit"
    )


def _env(control_url: str, warehouse_url: str) -> TrackingEnvironment:
    return TrackingEnvironment(
        {
            "CONTROL_PLANE_DATABASE_URL": control_url,
            "WAREHOUSE_DATABASE_URL": warehouse_url,
            "WAREHOUSE_ADMIN_DATABASE_URL": "sqlite:///admin-secret.db",
        }
    )


def test_runner_config_requires_admin_and_target_env_var_names_to_be_distinct():
    with pytest.raises(ValidationError, match="must differ"):
        ApprovedIntegrationRunnerConfig(
            environment=EnvironmentName.DEV,
            domain="sales",
            framework_version=FRAMEWORK_VERSION,
            release_hash="a" * 64,
            control_plane_profile="fabric_sql_database_v1",
            control_plane_database_url_env_var="CONTROL_PLANE_DATABASE_URL",
            warehouse_database_url_env_var="WAREHOUSE_DATABASE_URL",
            warehouse_admin_database_url_env_var="WAREHOUSE_DATABASE_URL",
        )


def test_session_termination_authorization_gate_prevents_all_secret_value_reads():
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    env = TrackingEnvironment(
        {
            "CONTROL_PLANE_DATABASE_URL": "sqlite:///control-secret.db",
            "WAREHOUSE_DATABASE_URL": "sqlite:///warehouse-secret.db",
            "WAREHOUSE_ADMIN_DATABASE_URL": "sqlite:///admin-secret.db",
        }
    )

    with pytest.raises(ValueError, match="session termination recovery is not explicitly authorized"):
        execute_approved_warehouse_fault_drill(
            config=_runner_config(release.bundle.release_hash),
            spec=spec,
            prerequisite_manifest=_prerequisite(spec),
            release_manifest=release,
            configs=configs,
            run_config=_run_config(),
            environ=env,
            evidence_references=("artifact:session-recovery",),
            allow_warehouse_fault_injection=True,
            allow_warehouse_session_termination=False,
            extension_registry=ExtensionRegistry(),
        )
    assert env.getitem_calls == []


def test_session_recovery_requires_admin_env_name_before_secret_read():
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    env = TrackingEnvironment(
        {
            "CONTROL_PLANE_DATABASE_URL": "sqlite:///control-secret.db",
            "WAREHOUSE_DATABASE_URL": "sqlite:///warehouse-secret.db",
        }
    )

    with pytest.raises(ValueError, match="warehouse_admin_database_url_env_var"):
        execute_approved_warehouse_fault_drill(
            config=_runner_config(release.bundle.release_hash, admin=False),
            spec=spec,
            prerequisite_manifest=_prerequisite(spec),
            release_manifest=release,
            configs=configs,
            run_config=_run_config(),
            environ=env,
            evidence_references=("artifact:session-recovery",),
            allow_warehouse_fault_injection=True,
            allow_warehouse_session_termination=True,
            extension_registry=ExtensionRegistry(),
        )
    assert env.getitem_calls == []


def test_committed_marker_path_never_reads_admin_secret_even_when_recovery_enabled(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    control_url = _prepare_control(tmp_path / "control.db", configs)
    warehouse_url, target = _prepare_warehouse(tmp_path / "warehouse.db")
    env = _env(control_url, warehouse_url)
    controller = FaultController()

    execution = execute_approved_warehouse_fault_drill(
        config=_runner_config(release.bundle.release_hash),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        run_config=_run_config(),
        environ=env,
        evidence_references=("artifact:committed-fault",),
        allow_warehouse_fault_injection=True,
        allow_warehouse_session_termination=True,
        extension_registry=_registry(target, controller),
        marker_store_factory=_commit_then_raise_factory,
        session_binding_capture=lambda connection: SESSION_BINDING,
        session_authority_factory=lambda engine: (_ for _ in ()).throw(
            AssertionError("Admin authority must not be constructed for COMMITTED marker")
        ),
    )

    assert _result(execution).status is IntegrationEvidenceStatus.PASS
    assert execution.report is not None
    assert execution.report.session_binding_captured is True
    assert execution.report.session_termination_recovery_attempted is False
    assert "WAREHOUSE_ADMIN_DATABASE_URL" not in env.getitem_calls


def test_verified_unresolved_fault_can_reconcile_to_not_committed_without_reexecution(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    control_url = _prepare_control(tmp_path / "control.db", configs)
    warehouse_url, target = _prepare_warehouse(tmp_path / "warehouse.db")
    env = _env(control_url, warehouse_url)
    controller = FaultController()
    authority = FakeSessionAuthority()
    admin_urls = []

    def admin_engine_factory(url):
        admin_urls.append(url)
        return create_engine("sqlite://")

    execution = execute_approved_warehouse_fault_drill(
        config=_runner_config(release.bundle.release_hash),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        run_config=_run_config(),
        environ=env,
        evidence_references=("artifact:not-committed-recovery",),
        allow_warehouse_fault_injection=True,
        allow_warehouse_session_termination=True,
        extension_registry=_registry(target, controller),
        marker_store_factory=_rollback_after_mutation_factory,
        session_binding_capture=lambda connection: SESSION_BINDING,
        warehouse_admin_engine_factory=admin_engine_factory,
        session_authority_factory=lambda engine: authority,
    )

    result = _result(execution)
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert "SAFE_NOT_COMMITTED_AFTER_SESSION_TERMINATION" in (result.detail or "")
    assert execution.report is not None
    assert execution.report.probe_resolution.value == "NOT_COMMITTED"
    assert execution.report.final_status is TargetOperationStatus.NOT_COMMITTED
    assert execution.report.retry_eligible is True
    assert execution.report.absence_safe_to_retry is True
    assert execution.report.session_termination_recovery_attempted is True
    assert execution.report.reentry_action is None
    assert authority.terminated == [SESSION_BINDING]
    assert admin_urls == ["sqlite:///admin-secret.db"]
    assert env.getitem_calls.count("WAREHOUSE_ADMIN_DATABASE_URL") == 1

    control = create_engine(control_url)
    try:
        current = read_target_operation(control, result.operation_key)
        assert current is not None
        assert current.status is TargetOperationStatus.NOT_COMMITTED
    finally:
        control.dispose()

    warehouse = create_engine(warehouse_url)
    try:
        with warehouse.connect() as connection:
            assert connection.execute(target.select()).all() == []
    finally:
        warehouse.dispose()


def test_unresolved_fault_without_session_binding_never_reads_admin_secret(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    control_url = _prepare_control(tmp_path / "control.db", configs)
    warehouse_url, target = _prepare_warehouse(tmp_path / "warehouse.db")
    env = _env(control_url, warehouse_url)

    execution = execute_approved_warehouse_fault_drill(
        config=_runner_config(release.bundle.release_hash),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        run_config=_run_config(),
        environ=env,
        evidence_references=("artifact:no-session-binding",),
        allow_warehouse_fault_injection=True,
        allow_warehouse_session_termination=True,
        extension_registry=_registry(target, FaultController()),
        marker_store_factory=_fails_before_mutation_factory,
        session_binding_capture=lambda connection: SESSION_BINDING,
    )

    result = _result(execution)
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert "SESSION_BINDING_NOT_CAPTURED" in (result.detail or "")
    assert execution.report is not None
    assert execution.report.final_status is TargetOperationStatus.UNKNOWN
    assert execution.report.session_termination_recovery_attempted is False
    assert "WAREHOUSE_ADMIN_DATABASE_URL" not in env.getitem_calls


def test_session_recovery_flag_is_part_of_run_config_hash_but_not_operation_input_fingerprint():
    enabled = _run_config(session_recovery=True)
    disabled = _run_config(session_recovery=False)

    assert enabled.run_config_hash != disabled.run_config_hash
    assert enabled.input_fingerprint == disabled.input_fingerprint
