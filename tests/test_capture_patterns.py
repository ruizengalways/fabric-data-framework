import pytest

from fabric_data_framework.capture.patterns import (
    BronzeWriteMode,
    CapturePattern,
    ChangeFidelity,
    DeleteVisibility,
    HistoryFidelity,
    assess_dataset_capture_pattern,
    capture_pattern_catalog,
    capture_pattern_spec,
)
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
)


def _dataset(
    capture: CaptureStrategy,
    apply: ApplyStrategy,
    *,
    overlap: int = 0,
    delete_policy: str = "IGNORE",
) -> DatasetConfig:
    watermark = None
    if capture is CaptureStrategy.WATERMARK:
        watermark = WatermarkConfig(
            column="updated_at",
            tie_breaker=("id",),
            overlap_window_seconds=overlap,
        )
    return DatasetConfig(
        dataset_id="sales.customer",
        source=SourceConfig(system="sales", object="dbo.customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=capture,
            apply_strategy=apply,
            business_key=("id",),
            merge_key=("id",) if apply in {
                ApplyStrategy.UPSERT,
                ApplyStrategy.SCD1,
                ApplyStrategy.SCD2,
                ApplyStrategy.SNAPSHOT_DIFF,
            } else (),
            append_identity=("event_id",) if apply is ApplyStrategy.APPEND else (),
            watermark=watermark,
            event_time_column="updated_at" if capture is CaptureStrategy.WATERMARK else None,
            delete_policy=delete_policy,
        ),
        orchestration=OrchestrationPolicy(execution_group="sales"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="quarantine"),
        reconciliation=ReconciliationPolicy(policy_name="row_accounting"),
    )


def test_catalog_has_exactly_fourteen_mainstream_patterns():
    specs = capture_pattern_catalog()
    assert len(specs) == 14
    assert {item.pattern for item in specs} == set(CapturePattern)


def test_full_snapshot_is_current_state_and_snapshot_grain_history():
    spec = capture_pattern_spec(CapturePattern.FULL_SNAPSHOT)
    assert spec.change_fidelity is ChangeFidelity.CURRENT_STATE
    assert spec.delete_visibility is DeleteVisibility.SNAPSHOT_INFERRED
    assert spec.default_bronze_write_mode is BronzeWriteMode.OVERWRITE
    assert spec.scd2_history_fidelity is HistoryFidelity.SNAPSHOT_GRAIN


def test_watermark_has_no_hard_delete_visibility_and_observed_history_only():
    spec = capture_pattern_spec(CapturePattern.WATERMARK_INCREMENTAL)
    assert spec.delete_visibility is DeleteVisibility.NONE
    assert spec.scd2_history_fidelity is HistoryFidelity.OBSERVED_CHANGES


def test_watermark_lookback_requires_positive_overlap():
    config = _dataset(CaptureStrategy.WATERMARK, ApplyStrategy.SCD1, overlap=0)
    with pytest.raises(ValueError, match="positive watermark overlap"):
        assess_dataset_capture_pattern(config, CapturePattern.WATERMARK_LOOKBACK)

    config = _dataset(CaptureStrategy.WATERMARK, ApplyStrategy.SCD1, overlap=120)
    assessment = assess_dataset_capture_pattern(config, CapturePattern.WATERMARK_LOOKBACK)
    assert assessment.valid is True


def test_net_cdc_current_and_observation_have_same_fidelity_but_different_bronze():
    current = capture_pattern_spec(CapturePattern.CDC_NET_CURRENT)
    observation = capture_pattern_spec(CapturePattern.CDC_NET_OBSERVATION)
    assert current.change_fidelity is ChangeFidelity.NET_CHANGE
    assert observation.change_fidelity is ChangeFidelity.NET_CHANGE
    assert current.default_bronze_write_mode is BronzeWriteMode.MERGE
    assert observation.default_bronze_write_mode is BronzeWriteMode.APPEND
    assert current.scd2_history_fidelity is HistoryFidelity.BATCH_GRAIN
    assert observation.scd2_history_fidelity is HistoryFidelity.BATCH_GRAIN


def test_full_cdc_transaction_log_debezium_and_delta_cdf_preserve_full_event_history():
    for pattern in (
        CapturePattern.CDC_FULL,
        CapturePattern.TRANSACTION_LOG_CDC,
        CapturePattern.DEBEZIUM_KAFKA,
        CapturePattern.DELTA_CDF,
    ):
        spec = capture_pattern_spec(pattern)
        assert spec.change_fidelity is ChangeFidelity.FULL_CHANGE
        assert spec.delete_visibility is DeleteVisibility.EXPLICIT_EVENT
        assert spec.default_bronze_write_mode is BronzeWriteMode.APPEND
        assert spec.scd2_history_fidelity is HistoryFidelity.FULL_EVENT


def test_event_source_is_stream_append_and_source_defined_delete():
    spec = capture_pattern_spec(CapturePattern.EVENT_SOURCE)
    assert spec.compatible_capture_strategies == frozenset({CaptureStrategy.STREAM})
    assert spec.change_fidelity is ChangeFidelity.FULL_EVENT
    assert spec.delete_visibility is DeleteVisibility.SOURCE_DEFINED
    assert spec.default_bronze_write_mode is BronzeWriteMode.APPEND


def test_snapshot_diff_can_infer_delete_but_only_at_snapshot_grain():
    spec = capture_pattern_spec(CapturePattern.SNAPSHOT_DIFF)
    assert spec.delete_visibility is DeleteVisibility.SNAPSHOT_INFERRED
    assert spec.change_fidelity is ChangeFidelity.NET_CHANGE
    assert spec.scd2_history_fidelity is HistoryFidelity.SNAPSHOT_GRAIN
    assert BronzeWriteMode.MERGE in spec.allowed_bronze_write_modes
    assert BronzeWriteMode.APPEND in spec.allowed_bronze_write_modes


def test_api_and_file_history_are_source_defined_not_overclaimed():
    api = capture_pattern_spec(CapturePattern.API_CURSOR_INCREMENTAL)
    files = capture_pattern_spec(CapturePattern.FILE_INCREMENTAL)
    assert api.scd2_history_fidelity is HistoryFidelity.SOURCE_DEFINED
    assert files.scd2_history_fidelity is HistoryFidelity.SOURCE_DEFINED
    assert api.delete_visibility is DeleteVisibility.SOURCE_DEFINED
    assert files.delete_visibility is DeleteVisibility.SOURCE_DEFINED


def test_pattern_rejects_wrong_coarse_capture_strategy():
    config = _dataset(CaptureStrategy.FULL, ApplyStrategy.REPLACE)
    with pytest.raises(ValueError, match="expects capture strategy"):
        assess_dataset_capture_pattern(config, CapturePattern.DEBEZIUM_KAFKA)


def test_pattern_rejects_invalid_bronze_mode():
    config = _dataset(CaptureStrategy.CDC, ApplyStrategy.SCD1)
    with pytest.raises(ValueError, match="does not allow Bronze MERGE"):
        assess_dataset_capture_pattern(
            config,
            CapturePattern.CDC_FULL,
            bronze_write_mode=BronzeWriteMode.MERGE,
        )


def test_scd2_warning_is_explicit_for_watermark_observed_change_history():
    config = _dataset(CaptureStrategy.WATERMARK, ApplyStrategy.SCD2)
    assessment = assess_dataset_capture_pattern(config, CapturePattern.WATERMARK_INCREMENTAL)
    assert assessment.scd2_history_fidelity is HistoryFidelity.OBSERVED_CHANGES
    assert any("only changes observed" in item for item in assessment.warnings)


def test_scd2_warning_is_explicit_for_net_cdc_batch_grain_history():
    config = _dataset(CaptureStrategy.CDC, ApplyStrategy.SCD2)
    assessment = assess_dataset_capture_pattern(config, CapturePattern.CDC_NET_CURRENT)
    assert assessment.scd2_history_fidelity is HistoryFidelity.BATCH_GRAIN
    assert any("net/batch-grain" in item for item in assessment.warnings)


def test_full_event_cdc_does_not_warn_about_history_loss():
    config = _dataset(CaptureStrategy.CDC, ApplyStrategy.SCD2)
    assessment = assess_dataset_capture_pattern(config, CapturePattern.CDC_FULL)
    assert assessment.scd2_history_fidelity is HistoryFidelity.FULL_EVENT
    assert assessment.warnings == ()


def test_no_delete_visibility_warns_when_delete_policy_claims_more():
    config = _dataset(
        CaptureStrategy.WATERMARK,
        ApplyStrategy.SCD1,
        delete_policy="APPLY",
    )
    assessment = assess_dataset_capture_pattern(config, CapturePattern.WATERMARK_INCREMENTAL)
    assert any("does not expose hard deletes" in item for item in assessment.warnings)


def test_api_cursor_accepts_watermark_or_stream_semantic_mapping():
    watermark = _dataset(CaptureStrategy.WATERMARK, ApplyStrategy.SCD1)
    stream = _dataset(CaptureStrategy.STREAM, ApplyStrategy.APPEND)
    assert assess_dataset_capture_pattern(
        watermark, CapturePattern.API_CURSOR_INCREMENTAL
    ).valid
    assert assess_dataset_capture_pattern(
        stream, CapturePattern.API_CURSOR_INCREMENTAL,
        bronze_write_mode=BronzeWriteMode.APPEND,
    ).valid


def test_file_incremental_accepts_snapshot_or_stream_semantic_mapping():
    snapshot = _dataset(CaptureStrategy.SNAPSHOT, ApplyStrategy.SCD1)
    stream = _dataset(CaptureStrategy.STREAM, ApplyStrategy.APPEND)
    assert assess_dataset_capture_pattern(snapshot, CapturePattern.FILE_INCREMENTAL).valid
    assert assess_dataset_capture_pattern(stream, CapturePattern.FILE_INCREMENTAL).valid
