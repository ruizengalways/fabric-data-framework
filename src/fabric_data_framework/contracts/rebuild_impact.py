"""Provider-neutral contracts for dependency-aware rebuild impact planning."""

from __future__ import annotations

from enum import Enum
import hashlib
import json

from pydantic import Field, model_validator

from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.contracts.rebuild import RebuildScope


class RepairIssueOrigin(str, Enum):
    """Where authoritative trust first failed in a data-product chain."""

    TARGET_LOGIC = "TARGET_LOGIC"
    CAPTURE_DATA = "CAPTURE_DATA"
    CAPTURE_SEMANTICS = "CAPTURE_SEMANTICS"

    @property
    def root_rebuild_scope(self) -> RebuildScope:
        if self is RepairIssueOrigin.TARGET_LOGIC:
            return RebuildScope.TARGET_ONLY
        if self is RepairIssueOrigin.CAPTURE_DATA:
            return RebuildScope.CAPTURE_AND_TARGET
        return RebuildScope.AUTHORITATIVE_RESET


class RebuildImpactDataset(FrozenModel):
    dataset_id: str = Field(min_length=1)
    target_layer: str = Field(min_length=1)
    enabled: bool
    is_root: bool
    rebuild_scope: RebuildScope


class RebuildImpactPlan(FrozenModel):
    """Exact affected downstream subgraph and safe rebuild order."""

    issue_origin: RepairIssueOrigin
    root_dataset_ids: tuple[str, ...]
    datasets: tuple[RebuildImpactDataset, ...]
    waves: tuple[tuple[str, ...], ...]
    disabled_affected_dataset_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_plan(self) -> "RebuildImpactPlan":
        if not self.root_dataset_ids:
            raise ValueError("rebuild impact plan requires at least one root dataset")
        if len(set(self.root_dataset_ids)) != len(self.root_dataset_ids):
            raise ValueError("root_dataset_ids must be unique")
        dataset_ids = tuple(item.dataset_id for item in self.datasets)
        if len(set(dataset_ids)) != len(dataset_ids):
            raise ValueError("impact datasets must be unique")
        missing_roots = set(self.root_dataset_ids) - set(dataset_ids)
        if missing_roots:
            raise ValueError("all rebuild roots must appear in impact datasets")
        flattened = tuple(dataset_id for wave in self.waves for dataset_id in wave)
        if set(flattened) != set(dataset_ids) or len(flattened) != len(dataset_ids):
            raise ValueError("rebuild waves must contain each affected dataset exactly once")
        return self

    @property
    def affected_dataset_ids(self) -> tuple[str, ...]:
        return tuple(item.dataset_id for item in self.datasets)

    @property
    def plan_hash(self) -> str:
        payload = self.model_dump(mode="json")
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "RebuildImpactDataset",
    "RebuildImpactPlan",
    "RepairIssueOrigin",
]
