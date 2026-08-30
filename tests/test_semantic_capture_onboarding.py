import json

import pytest

from fabric_data_framework.capture.onboarding import (
    DatasetSemanticCaptureSelection,
    load_semantic_capture_selections,
    validate_semantic_capture_selection,
)
from fabric_data_framework.capture.patterns import HistoryFidelity
from fabric_data_framework.capture.semantic_contracts import (
    BronzeContract,
    CheatsheetPattern,
    DeleteSemantics,
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
    *,
    overlap: int = 0,
    delete_policy: str = "IGNORE",
) -> DatasetConfig:
    watermark = None
    if capture is CaptureStrategy.WATERMARK:
        watermark = WatermarkConfig(
            column="updated_at",
            tie_breaker=("customer_id",),
            overlap_window_seconds=overlap,
        )
    return DatasetConfig(
        dataset_id="crm.customer",
        source=SourceConfig(system="crm", object="dbo.customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=capture,
            apply_strategy=ApplyStrategy.SCD1,
            business_key=("customer_id",),
            merge_key=("customer_id",),
            watermark=watermark,
            event_time_column="updated_at" if capture is CaptureStrategy.WATERMARK else None,
            delete_policy=delete_policy,
        ),
        orchestration=OrchestrationPolicy(execution_group="crm"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="quarantine"),
        reconciliation=ReconciliationPolicy(policy_name="row_accounting"),
    )


def test_watermark_lookback_raw_onboarding_accepts_exact_semantic_combination():
    selection = DatasetSemanticCaptureSelection(
        dataset_id="crm.customer",
        cheatsheet_pattern=CheatsheetPattern.WATERMARK_LOOKBACK_RAW,
        history_claim=HistoryFidelity.OBSERVED_CHANGES,
        delete_claim=DeleteSemantics.NONE,
        rationale="Keep extraction observations and collapse rereads in Silver.",
        known_limitations=("Hard deletes are not visible.",),
    )

    report = validate_semantic_capture_selection(
        _dataset(CaptureStrategy.WATERMARK, overlap=900),
        selection,
    )
    assert report.contract.bronze_contract is BronzeContract.RAW_OBSERVATION
    assert report.contract.history_fidelity is HistoryFidelity.OBSERVED_CHANGES
    assert report.review_warnings == ()


def test_watermark_lookback_semantic_preset_requires_positive_overlap():
    selection = DatasetSemanticCaptureSelection(
        dataset_id="crm.customer",
        cheatsheet_pattern=CheatsheetPattern.WATERMARK_LOOKBACK_CURRENT,
        rationale="Look back for late source commits.",
    )
    with pytest.raises(ValueError, match="positive watermark overlap"):
        validate_semantic_capture_selection(
            _dataset(CaptureStrategy.WATERMARK, overlap=0),
            selection,
        )


def test_strict_watermark_preset_rejects_positive_overlap():
    selection = DatasetSemanticCaptureSelection(
        dataset_id="crm.customer",
        cheatsheet_pattern=CheatsheetPattern.WATERMARK_CURRENT,
        rationale="Strict source watermark.",
    )
    with pytest.raises(ValueError, match="select a WATERMARK_LOOKBACK preset"):
        validate_semantic_capture_selection(
            _dataset(CaptureStrategy.WATERMARK, overlap=60),
            selection,
        )


def test_semantic_onboarding_rejects_wrong_coarse_capture_strategy():
    selection = DatasetSemanticCaptureSelection(
        dataset_id="crm.customer",
        cheatsheet_pattern=CheatsheetPattern.FULL_SNAPSHOT_HISTORY,
        rationale="Periodic complete snapshots.",
    )
    with pytest.raises(ValueError, match="expects capture strategy FULL"):
        validate_semantic_capture_selection(
            _dataset(CaptureStrategy.WATERMARK, overlap=60),
            selection,
        )


def test_semantic_onboarding_rejects_overstated_history_and_delete_claims():
    history = DatasetSemanticCaptureSelection(
        dataset_id="crm.customer",
        cheatsheet_pattern=CheatsheetPattern.WATERMARK_LOOKBACK_RAW,
        history_claim=HistoryFidelity.FULL_EVENT,
        rationale="Incorrect history claim.",
    )
    with pytest.raises(ValueError, match="overstates/contradicts"):
        validate_semantic_capture_selection(
            _dataset(CaptureStrategy.WATERMARK, overlap=60),
            history,
        )

    delete = DatasetSemanticCaptureSelection(
        dataset_id="crm.customer",
        cheatsheet_pattern=CheatsheetPattern.WATERMARK_LOOKBACK_RAW,
        delete_claim=DeleteSemantics.EXPLICIT_EVENT,
        rationale="Incorrect delete claim.",
    )
    with pytest.raises(ValueError, match="delete claim"):
        validate_semantic_capture_selection(
            _dataset(CaptureStrategy.WATERMARK, overlap=60),
            delete,
        )


def test_soft_delete_semantics_warn_when_dataset_config_ignores_delete_state():
    selection = DatasetSemanticCaptureSelection(
        dataset_id="crm.customer",
        cheatsheet_pattern=CheatsheetPattern.WATERMARK_LOOKBACK_SOFT_DELETE_RAW,
        rationale="Source retains soft-delete rows.",
        known_limitations=("Source purges tombstones after its retention period.",),
    )
    report = validate_semantic_capture_selection(
        _dataset(CaptureStrategy.WATERMARK, overlap=60, delete_policy="IGNORE"),
        selection,
    )
    assert any("delete_policy=IGNORE" in item for item in report.review_warnings)


def test_intentionally_lossy_full_change_current_pattern_is_visible_in_review():
    selection = DatasetSemanticCaptureSelection(
        dataset_id="crm.customer",
        cheatsheet_pattern=CheatsheetPattern.FULL_CHANGES_CURRENT_LOSSY,
        rationale="Only current Bronze is required for this dataset.",
    )
    report = validate_semantic_capture_selection(_dataset(CaptureStrategy.CDC), selection)
    assert report.contract.intentionally_lossy is True
    assert any("intentionally collapses" in item for item in report.review_warnings)


def test_semantic_selection_file_loads_sorted_and_rejects_duplicates(tmp_path):
    path = tmp_path / "semantic-selections.json"
    path.write_text(
        json.dumps(
            [
                {
                    "dataset_id": "z.dataset",
                    "cheatsheet_pattern": "FULL_SNAPSHOT_HISTORY",
                    "rationale": "z",
                },
                {
                    "dataset_id": "a.dataset",
                    "cheatsheet_pattern": "WATERMARK_LOOKBACK_RAW",
                    "rationale": "a",
                },
            ]
        ),
        encoding="utf-8",
    )
    loaded = load_semantic_capture_selections(path)
    assert [item.dataset_id for item in loaded] == ["a.dataset", "z.dataset"]

    path.write_text(
        json.dumps(
            [
                {
                    "dataset_id": "a.dataset",
                    "cheatsheet_pattern": "FULL_SNAPSHOT_HISTORY",
                    "rationale": "a",
                },
                {
                    "dataset_id": "a.dataset",
                    "cheatsheet_pattern": "FULL_SNAPSHOT_CURRENT",
                    "rationale": "duplicate",
                },
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must be unique"):
        load_semantic_capture_selections(path)
