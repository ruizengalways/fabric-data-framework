"""Shared immutable Pydantic base for provider-neutral framework contracts."""

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


__all__ = ["FrozenModel"]
