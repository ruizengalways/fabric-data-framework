"""Source-controlled onboarding declarations for capture pattern truth claims."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field, model_validator

from ..config import CaptureStrategy, DatasetConfig, FrozenModel
from .patterns import (
    BronzeWriteMode,
    CapturePattern,
    CapturePatternAssessment,
    DeleteVisibility,
    HistoryFidelity,
    assess_dataset_capture_pattern,
    capture_pattern_spec,
)
from .semantic_contracts import (
    CaptureSemanticContract,
    CheatsheetPattern,
    DeleteSemantics,
    ReadStrategy,
    cheatsheet_pattern_contract,
)


class DatasetCaptureSelection(FrozenModel):
    """Reviewable legacy source-fidelity declaration stored in the domain repository."""

    dataset_id: str = Field(min_length=1)
    capture_pattern: CapturePattern
    bronze_write_mode: BronzeWriteMode | None = None
    history_claim: HistoryFidelity | None = None
    delete_claim: DeleteVisibility | None = None
    rationale: str = Field(min_length=1)
    known_limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_limitations(self) -> "DatasetCaptureSelection":
        if any(not item.strip() for item in self.known_limitations):
            raise ValueError("known_limitations cannot contain blank entries")
        return self


class CaptureOnboardingReport(FrozenModel):
    dataset_id: str
    selection: DatasetCaptureSelection
    assessment: CapturePatternAssessment
    canonical_history_fidelity: HistoryFidelity
    canonical_delete_visibility: DeleteVisibility
    review_warnings: tuple[str, ...] = ()


class DatasetSemanticCaptureSelection(FrozenModel):
    """Cheatsheet-aligned onboarding selection using orthogonal semantic presets."""

    dataset_id: str = Field(min_length=1)
    cheatsheet_pattern: CheatsheetPattern
    history_claim: HistoryFidelity | None = None
    delete_claim: DeleteSemantics | None = None
    rationale: str = Field(min_length=1)
    known_limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_limitations(self) -> "DatasetSemanticCaptureSelection":
        if any(not item.strip() for item in self.known_limitations):
            raise ValueError("known_limitations cannot contain blank entries")
        return self


class SemanticCaptureOnboardingReport(FrozenModel):
    dataset_id: str
    selection: DatasetSemanticCaptureSelection
    contract: CaptureSemanticContract
    review_warnings: tuple[str, ...] = ()


_EXPECTED_CAPTURE_STRATEGY: dict[CheatsheetPattern, CaptureStrategy] = {
    CheatsheetPattern.FULL_SNAPSHOT_CURRENT: CaptureStrategy.FULL,
    CheatsheetPattern.FULL_SNAPSHOT_HISTORY: CaptureStrategy.FULL,
    CheatsheetPattern.WATERMARK_CURRENT: CaptureStrategy.WATERMARK,
    CheatsheetPattern.WATERMARK_LOOKBACK_CURRENT: CaptureStrategy.WATERMARK,
    CheatsheetPattern.WATERMARK_LOOKBACK_RAW: CaptureStrategy.WATERMARK,
    CheatsheetPattern.WATERMARK_SOFT_DELETE_CURRENT: CaptureStrategy.WATERMARK,
    CheatsheetPattern.WATERMARK_LOOKBACK_SOFT_DELETE_RAW: CaptureStrategy.WATERMARK,
    CheatsheetPattern.NET_CHANGES_CURRENT: CaptureStrategy.CDC,
    CheatsheetPattern.NET_CHANGES_APPEND: CaptureStrategy.CDC,
    CheatsheetPattern.FULL_CHANGES_EVENT: CaptureStrategy.CDC,
    CheatsheetPattern.FULL_CHANGES_CURRENT_LOSSY: CaptureStrategy.CDC,
    CheatsheetPattern.BUSINESS_EVENTS: CaptureStrategy.STREAM,
    CheatsheetPattern.SNAPSHOT_DIFF_CURRENT: CaptureStrategy.SNAPSHOT,
    CheatsheetPattern.SNAPSHOT_DIFF_APPEND: CaptureStrategy.SNAPSHOT,
}

_BOUNDED_HISTORY = {
    HistoryFidelity.OBSERVED_CHANGES,
    HistoryFidelity.BATCH_GRAIN,
    HistoryFidelity.SNAPSHOT_GRAIN,
    HistoryFidelity.SOURCE_DEFINED,
}


def validate_capture_selection(
    config: DatasetConfig,
    selection: DatasetCaptureSelection,
) -> CaptureOnboardingReport:
    """Validate a legacy source-controlled onboarding claim against framework semantics."""

    if selection.dataset_id != config.dataset_id:
        raise ValueError(
            f"capture selection dataset_id {selection.dataset_id!r} does not match "
            f"DatasetConfig {config.dataset_id!r}"
        )

    spec = capture_pattern_spec(selection.capture_pattern)
    assessment = assess_dataset_capture_pattern(
        config,
        selection.capture_pattern,
        bronze_write_mode=selection.bronze_write_mode,
    )

    if selection.history_claim is not None and selection.history_claim is not spec.scd2_history_fidelity:
        raise ValueError(
            f"history claim {selection.history_claim.value} overstates/contradicts capture "
            f"pattern {selection.capture_pattern.value}; canonical claim is "
            f"{spec.scd2_history_fidelity.value}"
        )
    if selection.delete_claim is not None and selection.delete_claim is not spec.delete_visibility:
        raise ValueError(
            f"delete claim {selection.delete_claim.value} contradicts capture pattern "
            f"{selection.capture_pattern.value}; canonical claim is {spec.delete_visibility.value}"
        )

    warnings = list(assessment.warnings)
    if spec.scd2_history_fidelity in _BOUNDED_HISTORY and not selection.known_limitations:
        warnings.append(
            "capture pattern has bounded/source-defined history fidelity; record the limitation "
            "explicitly in known_limitations before production review"
        )

    return CaptureOnboardingReport(
        dataset_id=config.dataset_id,
        selection=selection,
        assessment=assessment,
        canonical_history_fidelity=spec.scd2_history_fidelity,
        canonical_delete_visibility=spec.delete_visibility,
        review_warnings=tuple(warnings),
    )


def validate_semantic_capture_selection(
    config: DatasetConfig,
    selection: DatasetSemanticCaptureSelection,
) -> SemanticCaptureOnboardingReport:
    """Validate one cheatsheet semantic preset against DatasetConfig without provider overclaims."""

    if selection.dataset_id != config.dataset_id:
        raise ValueError(
            f"semantic capture selection dataset_id {selection.dataset_id!r} does not match "
            f"DatasetConfig {config.dataset_id!r}"
        )

    expected_capture = _EXPECTED_CAPTURE_STRATEGY[selection.cheatsheet_pattern]
    if config.load.capture_strategy is not expected_capture:
        raise ValueError(
            f"cheatsheet pattern {selection.cheatsheet_pattern.value} expects capture strategy "
            f"{expected_capture.value}, got {config.load.capture_strategy.value}"
        )

    contract = cheatsheet_pattern_contract(selection.cheatsheet_pattern)
    watermark = config.load.watermark
    if contract.read_strategy is ReadStrategy.WATERMARK_LOOKBACK:
        if watermark is None or watermark.overlap_window_seconds <= 0:
            raise ValueError(
                f"cheatsheet pattern {selection.cheatsheet_pattern.value} requires a positive "
                "watermark overlap window"
            )
    elif contract.read_strategy is ReadStrategy.WATERMARK:
        if watermark is None:
            raise ValueError(
                f"cheatsheet pattern {selection.cheatsheet_pattern.value} requires watermark configuration"
            )
        if watermark.overlap_window_seconds > 0:
            raise ValueError(
                f"cheatsheet pattern {selection.cheatsheet_pattern.value} is strict WATERMARK; "
                "select a WATERMARK_LOOKBACK preset when overlap_window_seconds is positive"
            )

    if selection.history_claim is not None and selection.history_claim is not contract.history_fidelity:
        raise ValueError(
            f"history claim {selection.history_claim.value} overstates/contradicts cheatsheet pattern "
            f"{selection.cheatsheet_pattern.value}; canonical claim is {contract.history_fidelity.value}"
        )
    if selection.delete_claim is not None and selection.delete_claim is not contract.delete_semantics:
        raise ValueError(
            f"delete claim {selection.delete_claim.value} contradicts cheatsheet pattern "
            f"{selection.cheatsheet_pattern.value}; canonical claim is {contract.delete_semantics.value}"
        )

    warnings: list[str] = []
    if contract.history_fidelity in _BOUNDED_HISTORY and not selection.known_limitations:
        warnings.append(
            "semantic pattern has bounded/source-defined history fidelity; record the limitation "
            "explicitly in known_limitations before production review"
        )
    if contract.delete_semantics is DeleteSemantics.NONE and config.load.delete_policy != "IGNORE":
        warnings.append(
            "selected semantic pattern cannot observe hard deletes; configured delete policy cannot "
            "discover source rows that are already absent"
        )
    if contract.delete_semantics is DeleteSemantics.SOFT_DELETE and config.load.delete_policy == "IGNORE":
        warnings.append(
            "selected semantic pattern exposes soft-delete state but DatasetConfig delete_policy=IGNORE"
        )
    if contract.intentionally_lossy:
        warnings.append(
            "selected semantic pattern intentionally collapses full change history before current Bronze"
        )

    return SemanticCaptureOnboardingReport(
        dataset_id=config.dataset_id,
        selection=selection,
        contract=contract,
        review_warnings=tuple(warnings),
    )


def load_capture_selections(path: str | Path) -> tuple[DatasetCaptureSelection, ...]:
    """Load a deterministic JSON list of legacy source-controlled capture selections."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("capture selection file must contain a JSON list")
    selections = tuple(DatasetCaptureSelection.model_validate(item) for item in raw)
    dataset_ids = tuple(item.dataset_id for item in selections)
    if len(set(dataset_ids)) != len(dataset_ids):
        raise ValueError("capture selection dataset_id values must be unique")
    return tuple(sorted(selections, key=lambda item: item.dataset_id))


def load_semantic_capture_selections(
    path: str | Path,
) -> tuple[DatasetSemanticCaptureSelection, ...]:
    """Load deterministic cheatsheet-aligned onboarding selections."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("semantic capture selection file must contain a JSON list")
    selections = tuple(DatasetSemanticCaptureSelection.model_validate(item) for item in raw)
    dataset_ids = tuple(item.dataset_id for item in selections)
    if len(set(dataset_ids)) != len(dataset_ids):
        raise ValueError("semantic capture selection dataset_id values must be unique")
    return tuple(sorted(selections, key=lambda item: item.dataset_id))


__all__ = [
    "CaptureOnboardingReport",
    "DatasetCaptureSelection",
    "DatasetSemanticCaptureSelection",
    "SemanticCaptureOnboardingReport",
    "load_capture_selections",
    "load_semantic_capture_selections",
    "validate_capture_selection",
    "validate_semantic_capture_selection",
]
