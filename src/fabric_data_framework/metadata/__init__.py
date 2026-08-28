"""Metadata compilation and execution capability contracts."""

from .capabilities import (
    CapabilityRegistry,
    DEFAULT_CAPABILITY_REGISTRY,
    EngineCapability,
    UnsupportedExecutionCombination,
)

__all__ = [
    "CapabilityRegistry",
    "DEFAULT_CAPABILITY_REGISTRY",
    "EngineCapability",
    "UnsupportedExecutionCombination",
]
