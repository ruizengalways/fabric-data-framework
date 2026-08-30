import pytest

from fabric_data_framework.adapters.cdc import (
    CDCProviderAdapterRegistry,
    DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY,
    DebeziumKafkaCDCAdapter,
    DebeziumKafkaRecord,
)
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    ExecutionEngine,
    ExecutionPolicy,
    LoadPolicy,
    OrchestrationPolicy,
    ProgressOwner,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
    resolve_effective_config,
)
from fabric_data_framework.contracts.execution_plan import (
    ExecutionKind,
    compile_execution_plan,
)
from fabric_data_framework.metadata import (
    DEBEZIUM_KAFKA_PROFILE,
    DEFAULT_CAPABILITY_REGISTRY,
    UnsupportedExecutionCombination,
)


def _config(
    *,
    capture: CaptureStrategy = CaptureStrategy.CDC,
    progress_owner: ProgressOwner = ProgressOwner.EXTERNAL,
) -> DatasetConfig:
    return DatasetConfig(
        dataset_id="crm.customer",
        source=SourceConfig(
            system="crm",
            object="customers",
            connection_ref="crm_cdc",
        ),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=capture,
            apply_strategy=ApplyStrategy.UPSERT,
            merge_key=("id",),
        ),
        orchestration=OrchestrationPolicy(execution_group="crm_cdc"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
        execution=ExecutionPolicy(
            engine=ExecutionEngine.EXTERNAL_CDC,
            progress_owner=progress_owner,
            capability_profile=DEBEZIUM_KAFKA_PROFILE,
        ),
    )


def test_debezium_profile_compiles_external_capture_then_framework_apply():
    config = _config()
    assert DEFAULT_CAPABILITY_REGISTRY.validate(config) is ExecutionEngine.EXTERNAL_CDC

    plan = compile_execution_plan(
        resolve_effective_config(config),
        run_mode=RunMode.NORMAL,
    )

    assert plan.capture_engine is ExecutionEngine.EXTERNAL_CDC
    assert plan.apply_engine is ExecutionEngine.SPARK
    assert plan.capture_capability_profile == DEBEZIUM_KAFKA_PROFILE
    assert [unit.execution_kind for unit in plan.units] == [
        ExecutionKind.EXTERNAL_CDC,
        ExecutionKind.SPARK_JOB_DEFINITION,
    ]
    assert plan.units[0].state_commit_boundary is False
    assert plan.units[1].state_commit_boundary is True


def test_debezium_profile_rejects_wrong_semantics_or_progress_owner():
    with pytest.raises(UnsupportedExecutionCombination, match="does not support capture"):
        DEFAULT_CAPABILITY_REGISTRY.validate_capture(
            _config(capture=CaptureStrategy.STREAM)
        )

    with pytest.raises(UnsupportedExecutionCombination, match="progress owner"):
        DEFAULT_CAPABILITY_REGISTRY.validate_capture(
            _config(progress_owner=ProgressOwner.FRAMEWORK)
        )


def test_default_provider_registry_resolves_debezium_profile_and_normalizes():
    adapter = DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY.resolve(
        ExecutionEngine.EXTERNAL_CDC,
        DEBEZIUM_KAFKA_PROFILE,
    )
    assert isinstance(adapter, DebeziumKafkaCDCAdapter)

    result = adapter.normalize(
        (
            DebeziumKafkaRecord(
                topic="crm.customer",
                partition=0,
                offset=11,
                key={"id": 1},
                value={
                    "before": None,
                    "after": {"id": 1, "name": "Ada"},
                    "op": "c",
                },
            ),
        ),
        topic="crm.customer",
        lower_offsets={0: 10},
        upper_offsets={0: 11},
        complete_through_upper=True,
    )

    assert result.normalized_batch.events[0].after["name"] == "Ada"


def test_provider_registry_rejects_duplicate_profile_registration():
    registry = CDCProviderAdapterRegistry((DebeziumKafkaCDCAdapter(),))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(DebeziumKafkaCDCAdapter())

    with pytest.raises(KeyError, match="no CDC provider adapter"):
        registry.resolve(ExecutionEngine.EXTERNAL_CDC, "unknown_profile")
