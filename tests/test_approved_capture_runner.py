from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fabric_data_framework.adapters.fabric.capture_transports import FabricCaptureObservation
from fabric_data_framework.adapters.fabric.rest import FabricJobInstance, FabricJobStatus
from fabric_data_framework.evidence.approved_capture_runner import (
    ApprovedCaptureRunConfig,
    execute_approved_capture,
)
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    ExecutionEngine,
    ExecutionPolicy,
    ExtensionConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ProgressOwner,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
)
from fabric_data_framework.deployment.delivery import build_release_manifest
from fabric_data_framework.extensions import ExtensionKind, ExtensionRegistry
from fabric_data_framework.contracts.environment import EnvironmentName
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


NOW = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
FRAMEWORK_VERSION = "0.4.0"
DOMAIN_GIT_SHA = "1" * 40
EXTENSION_ARTIFACT = "fabric-customer-0.4.0.dev1-py3-none-any.whl"


def _copy_dataset() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="crm.customer_copy",
        source=SourceConfig(system="crm", object="dbo.Customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.REPLACE,
            watermark=WatermarkConfig(
                column="updated_at",
                overlap_window_seconds=60,
            ),
        ),
        orchestration=OrchestrationPolicy(execution_group="daily"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="count"),
        execution=ExecutionPolicy(
            engine=ExecutionEngine.FABRIC_COPY_JOB,
            progress_owner=ProgressOwner.FABRIC_NATIVE,
        ),
    )


def _spark_dataset(*, combined: bool = False) -> DatasetConfig:
    execution = ExecutionPolicy(
        engine=ExecutionEngine.SPARK,
        progress_owner=ProgressOwner.FRAMEWORK,
        apply_engine=ExecutionEngine.AUTO if combined else ExecutionEngine.CUSTOM,
    )
    extensions = ExtensionConfig() if combined else ExtensionConfig(apply="test.apply")
    return DatasetConfig(
        dataset_id="crm.customer_spark",
        source=SourceConfig(system="crm", object="dbo.Customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.REPLACE,
            watermark=WatermarkConfig(
                column="updated_at",
                tie_breaker=("customer_id",),
            ),
        ),
        orchestration=OrchestrationPolicy(execution_group="daily"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="count"),
        execution=execution,
        extensions=extensions,
    )


def _release(configs: tuple[DatasetConfig, ...], *, include_extension: bool = True):
    release = build_release_manifest(
        domain="customer",
        domain_release_version="0.4.0-dev",
        domain_git_sha=DOMAIN_GIT_SHA,
        framework_version=FRAMEWORK_VERSION,
        configs=configs,
        config_schema_version=1,
        fabric_item_manifest_version="dev-v1",
        build_id="approved-capture-test",
        generated_at=NOW,
    )
    if include_extension:
        release = release.model_copy(
            update={"artifact_sha256": {EXTENSION_ARTIFACT: "a" * 64}}
        )
    return release


def _spec(release_hash: str, kind: IntegrationEvidenceCheckKind, check_id: str):
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
            IntegrationEvidenceCheckSpec(check_id=check_id, kind=kind),
        ),
    )


def _prerequisite(
    spec: IntegrationEvidenceSpec,
    *,
    selected_status: IntegrationEvidenceStatus = IntegrationEvidenceStatus.NOT_RUN,
    control_status: IntegrationEvidenceStatus = IntegrationEvidenceStatus.PASS,
):
    selected_spec = spec.checks[-1]
    now = NOW
    item_id = uuid4()
    results = (
        IntegrationEvidenceCheckResult(
            check_id="fabric.item.read",
            kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            status=IntegrationEvidenceStatus.PASS,
            started_at=now,
            completed_at=now,
            workspace_id=uuid4(),
            item_id=item_id,
            evidence_references=("artifact:item-read",),
        ),
        IntegrationEvidenceCheckResult(
            check_id="control-plane.certify",
            kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            status=control_status,
            started_at=now,
            completed_at=now,
            evidence_references=("artifact:control-plane",)
            if control_status is IntegrationEvidenceStatus.PASS
            else (),
        ),
        IntegrationEvidenceCheckResult(
            check_id=selected_spec.check_id,
            kind=selected_spec.kind,
            status=selected_status,
            started_at=now,
            completed_at=now,
            dataset_run_id=uuid4()
            if selected_status is IntegrationEvidenceStatus.PASS
            else None,
            workspace_id=uuid4()
            if selected_status is IntegrationEvidenceStatus.PASS
            else None,
            item_id=uuid4()
            if selected_status is IntegrationEvidenceStatus.PASS
            else None,
            native_job_instance_id=uuid4()
            if selected_status is IntegrationEvidenceStatus.PASS
            else None,
            root_activity_id=uuid4()
            if selected_status is IntegrationEvidenceStatus.PASS
            else None,
            evidence_references=("artifact:old-capture",)
            if selected_status is IntegrationEvidenceStatus.PASS
            else (),
        ),
    )
    return IntegrationEvidenceManifest(
        environment=spec.environment,
        domain=spec.domain,
        framework_version=spec.framework_version,
        release_hash=spec.release_hash,
        started_at=now,
        completed_at=now,
        checks=spec.checks,
        results=results,
    )


def _runner_config(release_hash: str, check_id: str, workspace_id, item_id):
    return ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version=FRAMEWORK_VERSION,
        release_hash=release_hash,
        fabric_access_token_env_var="FABRIC_ACCESS_TOKEN",
        bindings=(
            IntegrationCheckPhysicalBinding(
                check_id=check_id,
                workspace_id=workspace_id,
                item_id=item_id,
            ),
        ),
    )


def _copy_capture_config() -> ApprovedCaptureRunConfig:
    return ApprovedCaptureRunConfig(
        check_id="fabric.copy",
        dataset_id="crm.customer_copy",
        landing_reference="bronze.crm_customer_copy",
        observation_extension="crm.copy.observe",
        extension_artifact_name=EXTENSION_ARTIFACT,
    )


def _spark_capture_config() -> ApprovedCaptureRunConfig:
    return ApprovedCaptureRunConfig(
        check_id="fabric.spark",
        dataset_id="crm.customer_spark",
        landing_reference="bronze.crm_customer_spark",
        observation_extension="crm.spark.observe",
        extension_artifact_name=EXTENSION_ARTIFACT,
        spark_execution_data_extension="crm.spark.execution-data",
        source_lower_bound={"updated_at": "2026-08-29T00:00:00Z", "customer_id": 10},
        source_upper_bound={"updated_at": "2026-08-30T00:00:00Z", "customer_id": 99},
        parameters={"mode": "approved-evidence"},
    )


class _Client:
    def __init__(self, *, item_id, status=FabricJobStatus.COMPLETED, job_type="CopyJob"):
        self.job = FabricJobInstance(
            job_instance_id=uuid4(),
            item_id=item_id,
            job_type=job_type,
            status=status,
            root_activity_id=uuid4(),
            start_time_utc=NOW,
            end_time_utc=NOW,
            failure_reason=None if status is FabricJobStatus.COMPLETED else {"code": "REMOTE"},
        )
        self.copy_calls = []
        self.spark_calls = []

    def run_and_wait_copy_job(self, **kwargs):
        self.copy_calls.append(kwargs)
        return self.job

    def run_and_wait_spark_job_definition(self, **kwargs):
        self.spark_calls.append(kwargs)
        return self.job


def _copy_registry(*, observer=None) -> ExtensionRegistry:
    registry = ExtensionRegistry()
    registry.register(
        ExtensionKind.CAPTURE_OBSERVER,
        "crm.copy.observe",
        observer
        or (
            lambda request, job: FabricCaptureObservation(
                rows_read=12,
                rows_written=12,
                source_reference="crm.dbo.Customer",
                landing_reference=request.landing_reference,
                external_checkpoint_reference=f"copy-native:{job.job_instance_id}",
                diagnostics={"observer": "copy-manifest"},
            )
        ),
    )
    return registry


def _spark_registry(*, wrong_upper: bool = False) -> ExtensionRegistry:
    registry = ExtensionRegistry()

    def observe(request, job):
        upper = (
            {"updated_at": "2026-08-30T00:00:01Z", "customer_id": 99}
            if wrong_upper
            else request.source_upper_bound
        )
        return FabricCaptureObservation(
            rows_read=9,
            rows_written=9,
            source_reference="crm.dbo.Customer",
            landing_reference=request.landing_reference,
            source_lower_bound=request.source_lower_bound,
            source_upper_bound=upper,
            diagnostics={"observer": "spark-manifest"},
        )

    registry.register(ExtensionKind.CAPTURE_OBSERVER, "crm.spark.observe", observe)
    registry.register(
        ExtensionKind.SPARK_EXECUTION_DATA,
        "crm.spark.execution-data",
        lambda request, binding: {
            "commandLineArguments": (
                f"--lower {request.source_lower_bound!r} --upper {request.source_upper_bound!r}"
            )
        },
    )
    return registry


def _result(execution, check_id: str):
    return next(item for item in execution.manifest.results if item.check_id == check_id)


def test_capture_requires_explicit_authorization_before_rest_client_creation():
    configs = (_copy_dataset(),)
    release = _release(configs)
    spec = _spec(
        release.bundle.release_hash,
        IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
        "fabric.copy",
    )
    called = []

    with pytest.raises(ValueError, match="not explicitly authorized"):
        execute_approved_capture(
            config=_runner_config(release.bundle.release_hash, "fabric.copy", uuid4(), uuid4()),
            spec=spec,
            prerequisite_manifest=_prerequisite(spec),
            release_manifest=release,
            configs=configs,
            capture_config=_copy_capture_config(),
            environ={"FABRIC_ACCESS_TOKEN": "ephemeral"},
            evidence_references=("artifact:copy",),
            allow_capture_execution=False,
            extension_registry=_copy_registry(),
            rest_client_factory=lambda _: called.append(True),
        )

    assert called == []


def test_capture_requires_passed_prerequisites_and_not_run_selected_check():
    configs = (_copy_dataset(),)
    release = _release(configs)
    spec = _spec(
        release.bundle.release_hash,
        IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
        "fabric.copy",
    )
    common = dict(
        config=_runner_config(release.bundle.release_hash, "fabric.copy", uuid4(), uuid4()),
        spec=spec,
        release_manifest=release,
        configs=configs,
        capture_config=_copy_capture_config(),
        environ={"FABRIC_ACCESS_TOKEN": "ephemeral"},
        evidence_references=("artifact:copy",),
        allow_capture_execution=True,
        extension_registry=_copy_registry(),
        rest_client_factory=lambda _: pytest.fail("REST client must not be created"),
    )

    with pytest.raises(ValueError, match="control-plane certification"):
        execute_approved_capture(
            prerequisite_manifest=_prerequisite(
                spec,
                control_status=IntegrationEvidenceStatus.NOT_RUN,
            ),
            **common,
        )

    with pytest.raises(ValueError, match="remain NOT_RUN"):
        execute_approved_capture(
            prerequisite_manifest=_prerequisite(
                spec,
                selected_status=IntegrationEvidenceStatus.PASS,
            ),
            **common,
        )


def test_capture_extension_artifact_must_be_fingerprinted_in_exact_release():
    configs = (_copy_dataset(),)
    release = _release(configs, include_extension=False)
    spec = _spec(
        release.bundle.release_hash,
        IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
        "fabric.copy",
    )

    with pytest.raises(ValueError, match="not fingerprinted"):
        execute_approved_capture(
            config=_runner_config(release.bundle.release_hash, "fabric.copy", uuid4(), uuid4()),
            spec=spec,
            prerequisite_manifest=_prerequisite(spec),
            release_manifest=release,
            configs=configs,
            capture_config=_copy_capture_config(),
            environ={"FABRIC_ACCESS_TOKEN": "ephemeral"},
            evidence_references=("artifact:copy",),
            allow_capture_execution=True,
            extension_registry=_copy_registry(),
            rest_client_factory=lambda _: pytest.fail("REST client must not be created"),
        )


def test_copy_job_pass_requires_verified_observation_and_native_correlation():
    configs = (_copy_dataset(),)
    release = _release(configs)
    spec = _spec(
        release.bundle.release_hash,
        IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
        "fabric.copy",
    )
    workspace_id, item_id = uuid4(), uuid4()
    client = _Client(item_id=item_id)

    execution = execute_approved_capture(
        config=_runner_config(release.bundle.release_hash, "fabric.copy", workspace_id, item_id),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        capture_config=_copy_capture_config(),
        environ={"FABRIC_ACCESS_TOKEN": "ephemeral-secret"},
        evidence_references=("artifact:copy-manifest",),
        allow_capture_execution=True,
        extension_registry=_copy_registry(),
        rest_client_factory=lambda _: client,
    )

    result = _result(execution, "fabric.copy")
    assert result.status is IntegrationEvidenceStatus.PASS
    assert result.workspace_id == workspace_id
    assert result.item_id == item_id
    assert result.native_job_instance_id == client.job.job_instance_id
    assert result.root_activity_id == client.job.root_activity_id
    assert execution.report is not None
    assert execution.report.receipt.rows_read == 12
    assert execution.report.receipt.rows_written == 12
    assert execution.report.receipt.landing_reference == "bronze.crm_customer_copy"
    rendered = execution.report.model_dump_json() + execution.manifest.model_dump_json()
    assert "ephemeral-secret" not in rendered
    assert len(client.copy_calls) == 1


def test_copy_remote_failure_never_calls_success_observer_and_is_retained_fail():
    configs = (_copy_dataset(),)
    release = _release(configs)
    spec = _spec(
        release.bundle.release_hash,
        IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
        "fabric.copy",
    )
    workspace_id, item_id = uuid4(), uuid4()
    client = _Client(item_id=item_id, status=FabricJobStatus.FAILED)
    observed = []
    registry = _copy_registry(observer=lambda *args: observed.append(args))

    execution = execute_approved_capture(
        config=_runner_config(release.bundle.release_hash, "fabric.copy", workspace_id, item_id),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        capture_config=_copy_capture_config(),
        environ={"FABRIC_ACCESS_TOKEN": "ephemeral"},
        evidence_references=("artifact:copy-fail",),
        allow_capture_execution=True,
        extension_registry=registry,
        rest_client_factory=lambda _: client,
    )

    result = _result(execution, "fabric.copy")
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert result.native_job_instance_id == client.job.job_instance_id
    assert result.root_activity_id == client.job.root_activity_id
    assert execution.report is None
    assert observed == []


def test_provider_completed_but_observer_exception_is_correlated_fail_not_pass():
    configs = (_copy_dataset(),)
    release = _release(configs)
    spec = _spec(
        release.bundle.release_hash,
        IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
        "fabric.copy",
    )
    workspace_id, item_id = uuid4(), uuid4()
    client = _Client(item_id=item_id)

    def broken_observer(*_):
        raise RuntimeError("observer failed after provider completion")

    execution = execute_approved_capture(
        config=_runner_config(release.bundle.release_hash, "fabric.copy", workspace_id, item_id),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        capture_config=_copy_capture_config(),
        environ={"FABRIC_ACCESS_TOKEN": "ephemeral"},
        evidence_references=("artifact:copy-observer-fail",),
        allow_capture_execution=True,
        extension_registry=_copy_registry(observer=broken_observer),
        rest_client_factory=lambda _: client,
    )

    result = _result(execution, "fabric.copy")
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert result.native_job_instance_id == client.job.job_instance_id
    assert result.root_activity_id == client.job.root_activity_id
    assert "RuntimeError" in (result.detail or "")
    assert execution.report is None


def test_spark_bounded_capture_passes_execution_data_and_requires_matching_bounds():
    configs = (_spark_dataset(),)
    release = _release(configs)
    spec = _spec(
        release.bundle.release_hash,
        IntegrationEvidenceCheckKind.FABRIC_SPARK_CAPTURE,
        "fabric.spark",
    )
    workspace_id, item_id = uuid4(), uuid4()
    client = _Client(item_id=item_id, job_type="SparkJobDefinition")
    capture_config = _spark_capture_config()

    execution = execute_approved_capture(
        config=_runner_config(release.bundle.release_hash, "fabric.spark", workspace_id, item_id),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        capture_config=capture_config,
        environ={"FABRIC_ACCESS_TOKEN": "ephemeral"},
        evidence_references=("artifact:spark-manifest",),
        allow_capture_execution=True,
        extension_registry=_spark_registry(),
        rest_client_factory=lambda _: client,
    )

    result = _result(execution, "fabric.spark")
    assert result.status is IntegrationEvidenceStatus.PASS
    assert execution.report is not None
    assert execution.report.receipt.source_lower_bound == capture_config.source_lower_bound
    assert execution.report.receipt.source_upper_bound == capture_config.source_upper_bound
    assert len(client.spark_calls) == 1
    assert client.spark_calls[0]["execution_data"] is not None


def test_spark_wrong_observed_bound_fails_closed_with_native_correlation():
    configs = (_spark_dataset(),)
    release = _release(configs)
    spec = _spec(
        release.bundle.release_hash,
        IntegrationEvidenceCheckKind.FABRIC_SPARK_CAPTURE,
        "fabric.spark",
    )
    workspace_id, item_id = uuid4(), uuid4()
    client = _Client(item_id=item_id, job_type="SparkJobDefinition")

    execution = execute_approved_capture(
        config=_runner_config(release.bundle.release_hash, "fabric.spark", workspace_id, item_id),
        spec=spec,
        prerequisite_manifest=_prerequisite(spec),
        release_manifest=release,
        configs=configs,
        capture_config=_spark_capture_config(),
        environ={"FABRIC_ACCESS_TOKEN": "ephemeral"},
        evidence_references=("artifact:spark-bound-fail",),
        allow_capture_execution=True,
        extension_registry=_spark_registry(wrong_upper=True),
        rest_client_factory=lambda _: client,
    )

    result = _result(execution, "fabric.spark")
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert result.native_job_instance_id == client.job.job_instance_id
    assert result.root_activity_id == client.job.root_activity_id
    assert execution.report is None


def test_spark_combined_dataset_execute_unit_cannot_be_reused_as_capture_only_evidence():
    configs = (_spark_dataset(combined=True),)
    release = _release(configs)
    spec = _spec(
        release.bundle.release_hash,
        IntegrationEvidenceCheckKind.FABRIC_SPARK_CAPTURE,
        "fabric.spark",
    )

    with pytest.raises(ValueError, match="dedicated capture-only"):
        execute_approved_capture(
            config=_runner_config(release.bundle.release_hash, "fabric.spark", uuid4(), uuid4()),
            spec=spec,
            prerequisite_manifest=_prerequisite(spec),
            release_manifest=release,
            configs=configs,
            capture_config=_spark_capture_config(),
            environ={"FABRIC_ACCESS_TOKEN": "ephemeral"},
            evidence_references=("artifact:spark",),
            allow_capture_execution=True,
            extension_registry=_spark_registry(),
            rest_client_factory=lambda _: pytest.fail("REST client must not be created"),
        )


def test_capture_run_config_rejects_credential_like_retained_values():
    with pytest.raises(ValidationError, match="credential material"):
        ApprovedCaptureRunConfig(
            check_id="fabric.copy",
            dataset_id="crm.customer_copy",
            landing_reference="https://example.test/path?sig=secret",
            observation_extension="crm.copy.observe",
            extension_artifact_name=EXTENSION_ARTIFACT,
        )
