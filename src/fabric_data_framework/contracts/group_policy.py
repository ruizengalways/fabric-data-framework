"""Source-controlled execution-group policy contracts.

Execution groups model the Fabric parent-Pipeline boundary: many datasets share the
same operational defaults while individual datasets may explicitly override them.
Policy application happens before audited RuntimeOverride resolution, so the precedence
is deterministic and reviewable:

    DatasetConfig -> execution-group defaults -> group dataset override -> RuntimeOverride

The policy itself is immutable and hashable so release/evidence tooling can bind the
exact operational semantics used by a pipeline run.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from .base import FrozenModel
from fabric_data_framework.metadata.config import (
    DataQualityPolicy,
    DatasetConfig,
    QuarantineDetailMode,
    canonical_hash,
)


class PipelineFailurePolicy(str, Enum):
    """How terminal dataset outcomes determine the parent Pipeline status."""

    FAIL_AT_END = "FAIL_AT_END"
    CRITICALITY_AWARE = "CRITICALITY_AWARE"


class DataQualityPolicyPatch(FrozenModel):
    """Optional execution-group patch over a dataset's source-controlled DQ policy."""

    enabled: bool | None = None
    quarantine_enabled: bool | None = None
    quarantine_detail_mode: QuarantineDetailMode | None = None
    max_quarantine_rows: int | None = Field(default=None, ge=0)
    max_quarantine_fraction: float | None = Field(default=None, ge=0.0, le=1.0)

    def apply(self, policy: DataQualityPolicy) -> DataQualityPolicy:
        updates = {
            key: value
            for key, value in self.model_dump().items()
            if value is not None
        }
        return policy if not updates else policy.model_copy(update=updates)


class ExecutionGroupPolicy(FrozenModel):
    """Operational defaults for one parent Pipeline / execution group.

    ``quality_defaults`` apply to every dataset in the group. A dataset-specific patch
    then wins over those defaults. Audited RuntimeOverride values still have final
    precedence. ``max_concurrency`` is a group cap; it never raises a dataset's own
    concurrency limit.
    """

    execution_group: str = Field(min_length=1)
    failure_policy: PipelineFailurePolicy = PipelineFailurePolicy.FAIL_AT_END
    max_concurrency: int | None = Field(default=None, gt=0)
    quality_defaults: DataQualityPolicyPatch = Field(default_factory=DataQualityPolicyPatch)
    dataset_quality_overrides: dict[str, DataQualityPolicyPatch] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dataset_override_keys(self) -> "ExecutionGroupPolicy":
        bad = sorted(key for key in self.dataset_quality_overrides if not key.strip())
        if bad:
            raise ValueError("dataset_quality_overrides keys cannot be empty")
        return self

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))

    def apply_to(self, config: DatasetConfig) -> DatasetConfig:
        if config.orchestration.execution_group != self.execution_group:
            raise ValueError(
                f"execution-group policy {self.execution_group!r} cannot apply to "
                f"dataset {config.dataset_id!r} in group "
                f"{config.orchestration.execution_group!r}"
            )
        quality = self.quality_defaults.apply(config.quality)
        dataset_patch = self.dataset_quality_overrides.get(config.dataset_id)
        if dataset_patch is not None:
            quality = dataset_patch.apply(quality)
        return config.model_copy(update={"quality": quality})


__all__ = [
    "DataQualityPolicyPatch",
    "ExecutionGroupPolicy",
    "PipelineFailurePolicy",
]
