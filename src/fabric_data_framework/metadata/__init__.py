"""Metadata compilation and execution capability contracts."""

from .capabilities import (
    CapabilityRegistry,
    DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
    DEBEZIUM_KAFKA_PROFILE,
    DEFAULT_CAPABILITY_PROFILE,
    DEFAULT_CAPABILITY_REGISTRY,
    EngineCapability,
    UnsupportedExecutionCombination,
)

__all__ = [
    "CapabilityRegistry",
    "DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE",
    "DEBEZIUM_KAFKA_PROFILE",
    "DEFAULT_CAPABILITY_PROFILE",
    "DEFAULT_CAPABILITY_REGISTRY",
    "EngineCapability",
    "UnsupportedExecutionCombination",
]
