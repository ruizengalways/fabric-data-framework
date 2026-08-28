from __future__ import annotations

from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.contracts.execution_plan import ExecutionKind
from fabric_data_framework.dispatcher import DatasetDispatchOutcome, dispatch_datasets
from fabric_data_framework.repository import InMemoryControlPlane


def test_in_process_backend_attaches_immutable_execution_plan_to_dataset_request():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(
        DatasetConfig(
            dataset_id="crm.customer",
            source=SourceConfig(
                system="crm",
                object="dbo.Customer",
                connection_ref="crm-readonly",
            ),
            target=TargetConfig(layer="silver", object="customer"),
            load=LoadPolicy(
                capture_strategy=CaptureStrategy.FULL,
                apply_strategy=ApplyStrategy.REPLACE,
            ),
            orchestration=OrchestrationPolicy(
                execution_group="daily",
                criticality=Criticality.HIGH,
            ),
            quality=DataQualityPolicy(
                policy_name="standard",
                quarantine_policy="reject",
            ),
            reconciliation=ReconciliationPolicy(policy_name="standard"),
        )
    )
    captured = []

    def resolver(_effective):
        def execute(request):
            captured.append(request)
            return DatasetDispatchOutcome(
                dataset_run_id=request.dataset_run_id,
                status=DatasetStatus.SUCCEEDED,
            )

        return execute

    result = dispatch_datasets(
        repository=repository,
        executor_resolver=resolver,
        environment="dev",
        domain="customer",
        domain_git_sha="abcdef0",
        framework_version="0.4.0",
        config_bundle_hash="a" * 64,
    )

    assert result.status.value == "SUCCESS"
    assert len(captured) == 1
    request = captured[0]
    assert request.execution_plan.dataset_id == request.dataset_id
    assert request.execution_plan.effective_config_hash == request.effective_config.effective_config_hash
    assert request.execution_plan.units[0].execution_kind is ExecutionKind.IN_PROCESS
    assert request.execution_plan.required_bindings == ("crm-readonly",)
