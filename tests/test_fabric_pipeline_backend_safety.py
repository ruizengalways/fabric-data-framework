from fabric_data_framework.adapters.fabric.pipeline import FabricPipelineBinding
from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
    resolve_effective_config,
)
from fabric_data_framework.execution.backends.fabric_pipeline import FabricPipelineBackend
from fabric_data_framework.control_plane.repository import InMemoryControlPlane
from uuid import uuid4


def _effective():
    return resolve_effective_config(
        DatasetConfig(
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
    )


class _SecretErrorTransport:
    def invoke(self, invocation):
        raise RuntimeError(
            "connection failed Authorization: Bearer abc.def password=super-secret"
        )


def test_pipeline_backend_redacts_credential_like_provider_exception_before_audit():
    repository = InMemoryControlPlane()
    effective = _effective()
    repository.deploy_dataset(effective.config)
    backend = FabricPipelineBackend(
        transport=_SecretErrorTransport(),
        binding_resolver=lambda _: FabricPipelineBinding(
            workspace_id=uuid4(),
            pipeline_item_id=uuid4(),
        ),
        outcome_reader=lambda _: None,
    )

    outcome = backend.execute_one(
        repository=repository,
        pipeline_run_id=uuid4(),
        effective=effective,
        run_mode=RunMode.NORMAL,
    )

    assert outcome.status is DatasetStatus.FAILED
    assert outcome.error_code == "FABRIC_PIPELINE_EXCEPTION"
    assert outcome.error_message == "RuntimeError: provider error detail redacted"
    assert "Bearer" not in outcome.error_message
    assert "super-secret" not in outcome.error_message
    assert repository.dataset_runs[0].error_message == outcome.error_message
