import json

import pytest

from fabric_data_framework.capture.onboarding import (
    DatasetCaptureSelection,
    load_capture_selections,
    validate_capture_selection,
)
from fabric_data_framework.capture.patterns import (
    BronzeWriteMode,
    CapturePattern,
    DeleteVisibility,
    HistoryFidelity,
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
    WatermarkConfig,
)


def _watermark_config(dataset_id="crm.customer"):
    return DatasetConfig(
        dataset_id=dataset_id,
        source=SourceConfig(system="crm", object="dbo.customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.SCD2,
            business_key=("customer_id",),
            merge_key=("customer_id",),
            watermark=WatermarkConfig(
                column="updated_at",
                tie_breaker=("customer_id",),
                overlap_window_seconds=600,
            ),
            event_time_column="updated_at",
        ),
        orchestration=OrchestrationPolicy(execution_group="crm"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="quarantine"),
        reconciliation=ReconciliationPolicy(policy_name="row_accounting"),
    )


def test_selection_validates_truthful_history_and_delete_claims():
    selection = DatasetCaptureSelection(
        dataset_id="crm.customer",
        capture_pattern=CapturePattern.WATERMARK_LOOKBACK,
        bronze_write_mode=BronzeWriteMode.MERGE,
        history_claim=HistoryFidelity.OBSERVED_CHANGES,
        delete_claim=DeleteVisibility.NONE,
        rationale="Source exposes updated_at but no physical delete feed.",
        known_limitations=("Hard deletes are not visible.",),
    )
    report = validate_capture_selection(_watermark_config(), selection)
    assert report.canonical_history_fidelity is HistoryFidelity.OBSERVED_CHANGES
    assert report.canonical_delete_visibility is DeleteVisibility.NONE


def test_selection_rejects_overstated_full_event_history():
    selection = DatasetCaptureSelection(
        dataset_id="crm.customer",
        capture_pattern=CapturePattern.WATERMARK_LOOKBACK,
        history_claim=HistoryFidelity.FULL_EVENT,
        rationale="incorrect claim",
    )
    with pytest.raises(ValueError, match="overstates/contradicts"):
        validate_capture_selection(_watermark_config(), selection)


def test_selection_rejects_delete_claim_that_source_pattern_cannot_support():
    selection = DatasetCaptureSelection(
        dataset_id="crm.customer",
        capture_pattern=CapturePattern.WATERMARK_LOOKBACK,
        delete_claim=DeleteVisibility.EXPLICIT_EVENT,
        rationale="incorrect delete claim",
    )
    with pytest.raises(ValueError, match="delete claim"):
        validate_capture_selection(_watermark_config(), selection)


def test_selection_requires_matching_dataset_id():
    selection = DatasetCaptureSelection(
        dataset_id="crm.other",
        capture_pattern=CapturePattern.WATERMARK_LOOKBACK,
        rationale="wrong dataset",
    )
    with pytest.raises(ValueError, match="does not match"):
        validate_capture_selection(_watermark_config(), selection)


def test_bounded_history_without_documented_limitation_generates_review_warning():
    selection = DatasetCaptureSelection(
        dataset_id="crm.customer",
        capture_pattern=CapturePattern.WATERMARK_LOOKBACK,
        rationale="Watermark is the only source capability.",
    )
    report = validate_capture_selection(_watermark_config(), selection)
    assert any("known_limitations" in item for item in report.review_warnings)


def test_capture_selection_file_loads_sorted_and_rejects_duplicates(tmp_path):
    path = tmp_path / "capture-selections.json"
    path.write_text(
        json.dumps(
            [
                {
                    "dataset_id": "z.dataset",
                    "capture_pattern": "WATERMARK_LOOKBACK",
                    "rationale": "z",
                },
                {
                    "dataset_id": "a.dataset",
                    "capture_pattern": "FULL_SNAPSHOT",
                    "rationale": "a",
                },
            ]
        ),
        encoding="utf-8",
    )
    loaded = load_capture_selections(path)
    assert [item.dataset_id for item in loaded] == ["a.dataset", "z.dataset"]

    path.write_text(
        json.dumps(
            [
                {
                    "dataset_id": "a.dataset",
                    "capture_pattern": "FULL_SNAPSHOT",
                    "rationale": "a",
                },
                {
                    "dataset_id": "a.dataset",
                    "capture_pattern": "FULL_SNAPSHOT",
                    "rationale": "duplicate",
                },
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must be unique"):
        load_capture_selections(path)
