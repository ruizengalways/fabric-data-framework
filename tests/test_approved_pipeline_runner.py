from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select

from fabric_data_framework.adapters.fabric.rest import FabricJobInstance, FabricJobStatus
from fabric_data_framework.evidence.approved_pipeline_runner import execute_approved_pipeline
from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    PipelineStatus,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.control_plane.schema import pipeline_run, step_run
from fabric_data_framework.deployment.delivery import build_release_manifest, materialize_semantic_metadata
from fabric_data_framework.infrastructure import EnvironmentName
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
)
from fabric_data_framework.evidence.integration_runner import (
    ApprovedIntegrationRunnerConfig,
    IntegrationCheckPhysicalBinding,
)
from fabric_data_framework.operations import DatasetRunAudit
from fabric_data_framework.control_plane.sqlalchemy_repository import SqlAlchemyControlPlaneRepository


NOW = datetime(2026, 8, 29, 14, 0, tzinfo=timezone.utc)
DOMAIN_GIT_SHA = "1" * 40
FRAMEWORK_VERSION = "0.4.0"


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
        dataset_id="crm.customer",
        source=SourceConfig(system="crm", object="dbo.Customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(execution_group="daily"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="count"),
    )


def _release(configs: tuple[DatasetConfig, ...]):
    return build_release_manifest(
        domain="customer",
        domain_release_version="0.4.0-dev",
        domain_git_sha=DOMAIN_GIT_SHA,
        framework_version=FRAMEWORK_VERSION,
        configs=configs,
        config_schema_version=1,
        fabric_item_manifest_version="dev-v1",
        build_id="approved-pipeline-test",
        generated_at=NOW,
    )


def _spec(release_hash: str) -> IntegrationEvidenceSpec:
    return IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="customer",
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
                check_id="fabric.pipeline",
                kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
            ),
        ),
    )


def _prerequisite(
    spec: IntegrationEvidenceSpec,
    *,
    pipeline_status: IntegrationEvidenceStatus = IntegrationEvidenceStatus.NOT_RUN,
    control_status: IntegrationEvidenceStatus = IntegrationEvidenceStatus.PASS,
) -> IntegrationEvidenceManifest:
    results = (
        IntegrationEvidenceCheckResult(
            check_id="fabric.item.read",
            kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            status=IntegrationEvidenceStatus.PASS,
            started_at=NOW,
            completed_at=NOW,
            workspace_id=uuid4(),
            item_id=uuid4(),
            evidence_references=("artifact:item-read",),
        ),
        IntegrationEvidenceCheckResult(
            check_id="control-plane.certify",
            kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            status=control_status,
            started_at=NOW,
            completed_at=NOW,
            evidence_references=("artifact:control-plane-certification",)
            if control_status is IntegrationEvidenceStatus.PASS
            else (),
        ),
        IntegrationEvidenceCheckResult(
            check_id="fabric.pipeline",
            kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
            status=pipeline_status,
            started_at=NOW,
            completed_at=NOW,
            framework_pipeline_run_id=uuid4()
            if pipeline_status is IntegrationEvidenceStatus.PASS
            else None,
            dataset_run_id=uuid4()
            if pipeline_status is IntegrationEvidenceStatus.PASS
            else None,
            workspace_id=uuid4()
            if pipeline_status is IntegrationEvidenceStatus.PASS
            else None,
            item_id=uuid4()
            if pipeline_status is IntegrationEvidenceStatus.PASS
            else None,
            native_job_instance_id=uuid4()
            if pipeline_status is IntegrationEvidenceStatus.PASS
            else None,
            root_activity_id=uuid4()
            if pipeline_status is IntegrationEvidenceStatus.PASS
            else None,
            evidence_references=("artifact:old-pipeline",)
            if pipeline_status is IntegrationEvidenceStatus.PASS
            else (),
        ),
    )
    return IntegrationEvidenceManifest(
        environment=spec.environment,
        domain=spec.domain,
        framework_version=spec.framework_version,
        release_hash=spec.release_hash,
        started_at=NOW,
        completed_at=NOW,
        checks=spec.checks,
        results=results,
    )


def _runner_config(release_hash: str, workspace_id: UUID, item_id: UUID):
    return ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version=FRAMEWORK_VERSION,
        release_hash=release_hash,
        fabric_access_token_env_var="FABRIC_ACCESS_TOKEN",
        control_plane_profile="fabric_sql_database_v1",
        control_plane_database_url_env_var="CONTROL_PLANE_DATABASE_URL",
        bindings=(
            IntegrationCheckPhysicalBinding(
                check_id="fabric.pipeline",
                workspace_id=workspace_id,
                item_id=item_id,
            ),
        ),
    )


def _prepare_database(path: Path, configs: tuple[DatasetConfig, ...]) -> str:
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    try:
        materialize_semantic_metadata(
            engine,
            configs=configs,
            domain="customer",
            domain_git_sha=DOMAIN_GIT_SHA,
            framework_version=FRAMEWORK_VERSION,
        )
    finally:
        engine.dispose()
    return url


class _CompletedTransport:
    def __init__(
        self,
        *,
        database_url: str,
        configs: tuple[DatasetConfig, ...],
        persist_success: bool,
    ) -> None:
        self.database_url = database_url
        self.configs = configs
        self.persist_success = persist_success
        self.job_id = uuid4()
        self.root_id = uuid4()

    def invoke(self, invocation):
        if self.persist_success:
            engine = create_engine(self.database_url)
            try:
                repository = SqlAlchemyControlPlaneRepository(
                    engine,
                    domain="customer",
                    domain_git_sha=DOMAIN_GIT_SHA,
                    framework_version=FRAMEWORK_VERSION,
                    configs=self.configs,
                )
                repository.record_dataset_run(
                    DatasetRunAudit(
                        dataset_run_id=invocation.dataset_run_id,
                        pipeline_run_id=invocation.pipeline_run_id,
                        dataset_id=invocation.dataset_id,
                        attempt=1,
                        run_mode=invocation.run_mode,
                        status=DatasetStatus.SUCCEEDED,
                        effective_config_hash=invocation.effective_config_hash,
                    )
                )
            finally:
                engine.dispose()
        return FabricJobInstance(
            job_instance_id=self.job_id,
            item_id=invocation.binding.pipeline_item_id,
            job_type=invocation.binding.job_type,
            status=FabricJobStatus.COMPLETED,
            root_activity_id=self.root_id,
            start_time_utc=NOW,
            end_time_utc=NOW + timedelta(seconds=2),
            failure_reason=None,
        )


class _FailedTransport:
    def __init__(self) -> None:
        self.job_id = uuid4()
        self.root_id = uuid4()

    def invoke(self, invocation):
        return FabricJobInstance(
            job_instance_id=self.job_id,
            item_id=invocation.binding.pipeline_item_id,
            job_type=invocation.binding.job_type,
            status=FabricJobStatus.FAILED,
            root_activity_id=self.root_id,
            start_time_utc=NOW,
            end_time_utc=NOW + timedelta(seconds=1),
            failure_reason={"errorCode": "REMOTE_FAILED"},
        )


def test_pipeline_authorization_gate_prevents_runtime_database_url_retrieval():
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    env = TrackingEnvironment(
        {
            "FABRIC_ACCESS_TOKEN": "ephemeral",
            "CONTROL_PLANE_DATABASE_URL": "sqlite:///should-not-be-read.db",
        }
    )

    with pytest.raises(ValueError, match="not explicitly authorized"):
        execute_approved_pipeline(
            config=_runner_config(release.bundle.release_hash, uuid4(), uuid4()),
            spec=spec,
            prerequisite_manifest=_prerequisite(spec),
            release_manifest=release,
            configs=configs,
            check_id="fabric.pipeline",
            dataset_id="crm.customer",
            environ=env,
            evidence_references=("artifact:pipeline",),
            allow_pipeline_execution=False,
        )

    assert env.getitem_calls == []


def test_pipeline_requires_passed_item_and_control_plane_prerequisites_before_secret_read():
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    env = TrackingEnvironment(
        {
            "FABRIC_ACCESS_TOKEN": "ephemeral",
            "CONTROL_PLANE_DATABASE_URL": "sqlite:///should-not-be-read.db",
        }
    )

    with pytest.raises(ValueError, match="control-plane certification"):
        execute_approved_pipeline(
            config=_runner_config(release.bundle.release_hash, uuid4(), uuid4()),
            spec=spec,
            prerequisite_manifest=_prerequisite(
                spec,
                control_status=IntegrationEvidenceStatus.NOT_RUN,
            ),
            release_manifest=release,
            configs=configs,
            check_id="fabric.pipeline",
            dataset_id="crm.customer",
            environ=env,
            evidence_references=("artifact:pipeline",),
            allow_pipeline_execution=True,
        )

    assert env.getitem_calls == []


def test_pipeline_refuses_automatic_rerun_when_prerequisite_manifest_already_has_result():
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    env = TrackingEnvironment(
        {
            "FABRIC_ACCESS_TOKEN": "ephemeral",
            "CONTROL_PLANE_DATABASE_URL": "sqlite:///should-not-be-read.db",
        }
    )

    with pytest.raises(ValueError, match="remain NOT_RUN"):
        execute_approved_pipeline(
            config=_runner_config(release.bundle.release_hash, uuid4(), uuid4()),
            spec=spec,
            prerequisite_manifest=_prerequisite(
                spec,
                pipeline_status=IntegrationEvidenceStatus.PASS,
            ),
            release_manifest=release,
            configs=configs,
            check_id="fabric.pipeline",
            dataset_id="crm.customer",
            environ=env,
            evidence_references=("artifact:pipeline",),
            allow_pipeline_execution=True,
        )

    assert env.getitem_calls == []


def test_pipeline_exact_release_bundle_mismatch_is_rejected_before_database_url_read():
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    changed = configs[0].model_copy(
        update={"target": TargetConfig(layer="silver", object="customer_changed")}
    )
    env = TrackingEnvironment(
        {
            "FABRIC_ACCESS_TOKEN": "ephemeral",
            "CONTROL_PLANE_DATABASE_URL": "sqlite:///should-not-be-read.db",
        }
    )

    with pytest.raises(ValueError, match="bundle hash"):
        execute_approved_pipeline(
            config=_runner_config(release.bundle.release_hash, uuid4(), uuid4()),
            spec=spec,
            prerequisite_manifest=_prerequisite(spec),
            release_manifest=release,
            configs=(changed,),
            check_id="fabric.pipeline",
            dataset_id="crm.customer",
            environ=env,
            evidence_references=("artifact:pipeline",),
            allow_pipeline_execution=True,
        )

    assert env.getitem_calls == []


def test_completed_pipeline_pass_requires_exact_durable_child_outcome(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    workspace_id, item_id = uuid4(), uuid4()
    database_url = _prepare_database(tmp_path / "control.db", configs)
    transport = _CompletedTransport(
        database_url=database_url,
        configs=configs,
        persist_success=True,
    )

    execution = execute_approved_pipeline(
        config=_runner_config(release.bundle.release_hash, workspace_id, item_id),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        check_id="fabric.pipeline",
        dataset_id="crm.customer",
        environ={
            "FABRIC_ACCESS_TOKEN": "not-used-by-fake-transport",
            "CONTROL_PLANE_DATABASE_URL": database_url,
        },
        evidence_references=("artifact:pipeline-run",),
        allow_pipeline_execution=True,
        transport_factory=lambda _: transport,
    )

    result = next(item for item in execution.manifest.results if item.check_id == "fabric.pipeline")
    assert result.status is IntegrationEvidenceStatus.PASS
    assert result.workspace_id == workspace_id
    assert result.item_id == item_id
    assert result.native_job_instance_id == transport.job_id
    assert result.root_activity_id == transport.root_id
    assert result.framework_pipeline_run_id is not None
    assert result.dataset_run_id is not None
    assert "not-used-by-fake-transport" not in execution.manifest.model_dump_json()
    assert database_url not in execution.manifest.model_dump_json()

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            parent = connection.execute(
                select(pipeline_run).where(
                    pipeline_run.c.pipeline_run_id == str(result.framework_pipeline_run_id)
                )
            ).mappings().one()
            remote_step = connection.execute(
                select(step_run).where(
                    step_run.c.dataset_run_id == str(result.dataset_run_id)
                )
            ).mappings().one()
        assert parent["status"] == PipelineStatus.SUCCESS.value
        assert remote_step["details"]["job_instance_id"] == str(transport.job_id)
    finally:
        engine.dispose()


def test_provider_completed_without_durable_framework_outcome_is_retained_fail(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    workspace_id, item_id = uuid4(), uuid4()
    database_url = _prepare_database(tmp_path / "control.db", configs)
    transport = _CompletedTransport(
        database_url=database_url,
        configs=configs,
        persist_success=False,
    )

    execution = execute_approved_pipeline(
        config=_runner_config(release.bundle.release_hash, workspace_id, item_id),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        check_id="fabric.pipeline",
        dataset_id="crm.customer",
        environ={
            "FABRIC_ACCESS_TOKEN": "unused",
            "CONTROL_PLANE_DATABASE_URL": database_url,
        },
        evidence_references=("artifact:pipeline-run",),
        allow_pipeline_execution=True,
        transport_factory=lambda _: transport,
    )

    result = next(item for item in execution.manifest.results if item.check_id == "fabric.pipeline")
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert result.native_job_instance_id == transport.job_id
    assert "FABRIC_PIPELINE_RESULT_MISSING" in (result.detail or "")


def test_remote_failed_pipeline_is_fail_with_native_correlation(tmp_path: Path):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    database_url = _prepare_database(tmp_path / "control.db", configs)
    transport = _FailedTransport()

    execution = execute_approved_pipeline(
        config=_runner_config(release.bundle.release_hash, uuid4(), uuid4()),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        check_id="fabric.pipeline",
        dataset_id="crm.customer",
        environ={
            "FABRIC_ACCESS_TOKEN": "unused",
            "CONTROL_PLANE_DATABASE_URL": database_url,
        },
        evidence_references=("artifact:pipeline-run",),
        allow_pipeline_execution=True,
        transport_factory=lambda _: transport,
    )

    result = next(item for item in execution.manifest.results if item.check_id == "fabric.pipeline")
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert result.native_job_instance_id == transport.job_id
    assert result.root_activity_id == transport.root_id
    assert "FABRIC_PIPELINE_FAILED" in (result.detail or "")
