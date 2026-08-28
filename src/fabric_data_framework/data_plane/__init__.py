"""Reusable provider-neutral data-plane staging/publication contracts."""

from .staging import StagedBatch, stage_rows

__all__ = ["StagedBatch", "stage_rows"]
