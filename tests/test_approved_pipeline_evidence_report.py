from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import create_engine

from fabric_data_framework.adapters.fabric.rest import FabricJobInstance, FabricJobStatus
from fabric_data_framework.contracts.audit import DatasetRunAudit
from fabric_data_framework.contracts.environment import EnvironmentName
from fabric_data_framework.control_plane.sqlalchemy_repository import SqlAlchemyControlPlaneRepository
from fabric_data_framework.deployment.delivery import build_release_manifest, materialize_semantic_metadata
from fabric_data_framework.evidence.approved_pipeline_runner import execute_approved_pipeline
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
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
)


NOW = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)
DOMAIN_SHA = "1" * 40
FRAMEWORK_VERSION = "0.4.0"


def _dataset() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="health.patient",
        source=SourceConfig(system="health", object="dbo.Patient"),
        target=TargetConfig(layer="silver", object="patient"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(execution_group="certification"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="count"),
    )


def _release(configs: tuple[DatasetConfig, ...]):
    return build_release_manifest(
        domain="customer",
        domain_release_version="0.4.0-dev",
        domain_git_sha=DOMAIN_SHA,
        framework_version=FRAMEWORK_VERSION,
        configs=configs,
        config_schema_version=1,
        fabric_item_manifest_version="business-path-v1",
        build_id="pipeline-report-test",
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
                check_id="control.cert",
                kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            ),
            IntegrationEvidenceCheckSpec(
                check_id="fabric.pipeline",
                kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
            ),
        ),
    )


def _prerequisite(spec: IntegrationEvidenceSpec) -> IntegrationEvidenceManifest:
    item_workspace = uuid4()
    item_id = uuid4()
    results = (
        IntegrationEvidenceCheckResult(
            check_id="fabric.item.read",
            kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            status=IntegrationEvidenceStatus.PASS,
            started_at=NOW,
            completed_at=NOW,
            workspace_id=item_workspace,
            item_id=item_id,
            evidence_references=("artifact://item-read",),
        ),
        IntegrationEvidenceCheckResult(
            check_id="control.cert",
            kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            status=IntegrationEvidenceStatus.PASS,
            started_at=NOW,
            completed_at=NOW,
            evidence_references=("artifact://control-cert",),
        ),
        IntegrationEvidenceCheckResult(
            check_id="fabric.pipeline",
            kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
            status=IntegrationEvidenceStatus.NOT_RUN,
            started_at=NOW,
            completed_at=NOW,
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


def _runner_config(release_hash: str, workspace_id: UUID, pipeline_id: UUID):
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
                item_id=pipeline_id,
            ),
        ),
    )


def _database(path: Path, configs: tuple[DatasetConfig, ...]) -> str:
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    try:
        materialize_semantic_metadata(
            engine,
            configs=configs,
            domain="customer",
            domain_git_sha=DOMAIN_SHA,
            framework_version=FRAMEWORK_VERSION,
        )
    finally:
        engine.dispose()
    return url


class _CompletedWithFrameworkOutcome:
    def __init__(
        self,
        *,
        database_url: str,
        configs: tuple[DatasetConfig, ...],
        framework_status: DatasetStatus,
        retryable: bool | None = None,
        error_code: str | None = None,
    ) -> None:
        self.database_url = database_url
        self.configs = configs
        self.framework_status = framework_status
        self.retryable = retryable
        self.error_code = error_code
        self.job_id = uuid4()
        self.root_id = uuid4()

    def invoke(self, invocation):
        engine = create_engine(self.database_url)
        try:
            repository = SqlAlchemyControlPlaneRepository(
                engine,
                domain="customer",
                domain_git_sha=DOMAIN_SHA,
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
                    status=self.framework_status,
                    effective_config_hash=invocation.effective_config_hash,
                    retryable=self.retryable,
                    error_code=self.error_code,
                    error_message="bounded test outcome" if self.error_code else None,
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


def _execute(tmp_path, *, framework_status, retryable=None, error_code=None):
    configs = (_dataset(),)
    release = _release(configs)
    spec = _spec(release.bundle.release_hash)
    workspace_id = uuid4()
    pipeline_id = uuid4()
    database_url = _database(tmp_path / f"{uuid4()}.db", configs)
    transport = _CompletedWithFrameworkOutcome(
        database_url=database_url,
        configs=configs,
        framework_status=framework_status,
        retryable=retryable,
        error_code=error_code,
    )
    execution = execute_approved_pipeline(
        config=_runner_config(release.bundle.release_hash, workspace_id, pipeline_id),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        check_id="fabric.pipeline",
        dataset_id="health.patient",
        environ={
            "FABRIC_ACCESS_TOKEN": "ephemeral-not-retained",
            "CONTROL_PLANE_DATABASE_URL": database_url,
        },
        evidence_references=("artifact://approved-pipeline-report",),
        allow_pipeline_execution=True,
        transport_factory=lambda _client: transport,
    )
    return execution, workspace_id, pipeline_id, transport


def test_pipeline_success_report_retains_native_and_framework_truth(tmp_path):
    execution, workspace_id, pipeline_id, transport = _execute(
        tmp_path,
        framework_status=DatasetStatus.SUCCEEDED,
    )

    assert execution.report is not None
    assert execution.report.remote_status is FabricJobStatus.COMPLETED
    assert execution.report.framework_status is DatasetStatus.SUCCEEDED
    assert execution.report.workspace_id == workspace_id
    assert execution.report.item_id == pipeline_id
    assert execution.report.native_job_instance_id == transport.job_id
    assert execution.report.root_activity_id == transport.root_id
    assert execution.report.dataset_run_id is not None
    assert len(execution.report.execution_plan_hash) == 64
    assert execution.manifest.results[-1].status is IntegrationEvidenceStatus.PASS


def test_pipeline_report_proves_provider_completed_can_still_be_framework_failed(tmp_path):
    execution, _, _, transport = _execute(
        tmp_path,
        framework_status=DatasetStatus.FAILED,
        retryable=False,
        error_code="RECONCILIATION_FAILED",
    )

    assert execution.report is not None
    assert execution.report.native_job_instance_id == transport.job_id
    assert execution.report.remote_status is FabricJobStatus.COMPLETED
    assert execution.report.framework_status is DatasetStatus.FAILED
    assert execution.report.retryable is False
    assert execution.report.error_code == "RECONCILIATION_FAILED"
    assert execution.manifest.results[-1].status is IntegrationEvidenceStatus.FAIL


def test_pipeline_report_redacts_credential_like_framework_error_code(tmp_path):
    execution, _, _, _ = _execute(
        tmp_path,
        framework_status=DatasetStatus.FAILED,
        retryable=True,
        error_code="access_token=should-not-be-retained",
    )

    assert execution.report is not None
    assert execution.report.error_code == "UNSAFE_PROVIDER_ERROR_CODE_REDACTED"
    assert "should-not-be-retained" not in execution.report.model_dump_json()
