"""Provider-neutral current-projection execution contracts."""

from __future__ import annotations

from pydantic import Field

from .audit import MutationCounts
from .base import FrozenModel


class CurrentProjectionExecutionError(RuntimeError):
    """Failure raised by provider-neutral or provider current-projection execution."""


class CurrentProjectionExecutionResult(FrozenModel):
    dataset_id: str = Field(min_length=1)
    lower_processed_version: int | None = Field(default=None, ge=0)
    upper_processed_version: int = Field(ge=0)
    affected_keys: int = Field(ge=0)
    mutations: MutationCounts
    checkpoint_version: int = Field(ge=0)
    no_work: bool = False


__all__ = ["CurrentProjectionExecutionError", "CurrentProjectionExecutionResult"]
