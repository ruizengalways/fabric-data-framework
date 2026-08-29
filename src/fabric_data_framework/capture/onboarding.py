"""Source-controlled onboarding declarations for capture pattern truth claims."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field, model_validator

from ..config import DatasetConfig, FrozenModel
from .patterns import (
    BronzeWriteMode,
    CapturePattern,
    CapturePatternAssessment,
    DeleteVisibility,
    HistoryFidelity,
    assess_dataset_capture_pattern,
    capture_pattern_spec,
)


class DatasetCaptureSelection(FrozenModel):
    """Reviewable source-fidelity declaration stored in the domain repository."""

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


def validate_capture_selection(
    config: DatasetConfig,
    selection: DatasetCaptureSelection,
) -> CaptureOnboardingReport:
    """Validate a source-controlled onboarding claim against framework semantics."""

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
    if spec.scd2_history_fidelity in {
        HistoryFidelity.OBSERVED_CHANGES,
        HistoryFidelity.BATCH_GRAIN,
        HistoryFidelity.SNAPSHOT_GRAIN,
        HistoryFidelity.SOURCE_DEFINED,
    } and not selection.known_limitations:
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


def load_capture_selections(path: str | Path) -> tuple[DatasetCaptureSelection, ...]:
    """Load a deterministic JSON list of source-controlled capture selections."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("capture selection file must contain a JSON list")
    selections = tuple(DatasetCaptureSelection.model_validate(item) for item in raw)
    dataset_ids = tuple(item.dataset_id for item in selections)
    if len(set(dataset_ids)) != len(dataset_ids):
        raise ValueError("capture selection dataset_id values must be unique")
    return tuple(sorted(selections, key=lambda item: item.dataset_id))


__all__ = [
    "CaptureOnboardingReport",
    "DatasetCaptureSelection",
    "load_capture_selections",
    "validate_capture_selection",
]
