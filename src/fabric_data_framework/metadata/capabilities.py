"""Execution-engine capability registry and conservative metadata compiler."""

from __future__ import annotations

from pydantic import Field

from ..config import (
    CaptureStrategy,
    DatasetConfig,
    ExecutionEngine,
    FrozenModel,
    ProgressOwner,
)


class UnsupportedExecutionCombination(ValueError):
    """Raised when metadata asks an engine to guarantee semantics it cannot prove."""


class EngineCapability(FrozenModel):
    engine: ExecutionEngine
    capture_strategies: frozenset[CaptureStrategy]
    progress_owners: frozenset[ProgressOwner]
    supports_composite_watermark: bool = False
    supports_native_cdc: bool = False
    supports_complete_snapshot_evidence: bool = True
    notes: str = Field(default="", max_length=1000)


_DEFAULT_CAPABILITIES = (
    EngineCapability(
        engine=ExecutionEngine.FABRIC_COPY_JOB,
        capture_strategies=frozenset(
            {CaptureStrategy.FULL, CaptureStrategy.WATERMARK, CaptureStrategy.CDC}
        ),
        progress_owners=frozenset({ProgressOwner.FABRIC_NATIVE}),
        supports_native_cdc=True,
        supports_composite_watermark=False,
        notes="Conservative built-in profile: native progress is authoritative.",
    ),
    EngineCapability(
        engine=ExecutionEngine.FABRIC_COPY_ACTIVITY,
        capture_strategies=frozenset(
            {CaptureStrategy.FULL, CaptureStrategy.WATERMARK, CaptureStrategy.SNAPSHOT}
        ),
        progress_owners=frozenset({ProgressOwner.FRAMEWORK}),
        supports_composite_watermark=True,
        notes="Framework supplies bounded source query/state where required.",
    ),
    EngineCapability(
        engine=ExecutionEngine.DATAFLOW_GEN2,
        capture_strategies=frozenset({CaptureStrategy.FULL, CaptureStrategy.SNAPSHOT}),
        progress_owners=frozenset(
            {ProgressOwner.FRAMEWORK, ProgressOwner.FABRIC_NATIVE}
        ),
        supports_composite_watermark=False,
        notes="Conservative baseline; connector/profile-specific incremental support may extend this.",
    ),
    EngineCapability(
        engine=ExecutionEngine.SPARK,
        capture_strategies=frozenset(
            {
                CaptureStrategy.FULL,
                CaptureStrategy.WATERMARK,
                CaptureStrategy.CDC,
                CaptureStrategy.SNAPSHOT,
                CaptureStrategy.STREAM,
            }
        ),
        progress_owners=frozenset({ProgressOwner.FRAMEWORK, ProgressOwner.EXTERNAL}),
        supports_composite_watermark=True,
        notes="Framework-controlled programmable execution.",
    ),
    EngineCapability(
        engine=ExecutionEngine.FABRIC_MIRRORING,
        capture_strategies=frozenset({CaptureStrategy.MIRROR, CaptureStrategy.CDC}),
        progress_owners=frozenset({ProgressOwner.FABRIC_NATIVE}),
        supports_native_cdc=True,
    ),
    EngineCapability(
        engine=ExecutionEngine.EXTERNAL_CDC,
        capture_strategies=frozenset({CaptureStrategy.CDC, CaptureStrategy.STREAM}),
        progress_owners=frozenset({ProgressOwner.EXTERNAL}),
        supports_native_cdc=True,
    ),
    EngineCapability(
        engine=ExecutionEngine.SQL,
        capture_strategies=frozenset(
            {CaptureStrategy.FULL, CaptureStrategy.WATERMARK, CaptureStrategy.SNAPSHOT}
        ),
        progress_owners=frozenset({ProgressOwner.FRAMEWORK}),
        supports_composite_watermark=True,
    ),
    EngineCapability(
        engine=ExecutionEngine.CUSTOM,
        capture_strategies=frozenset(CaptureStrategy),
        progress_owners=frozenset(
            {ProgressOwner.FRAMEWORK, ProgressOwner.FABRIC_NATIVE, ProgressOwner.EXTERNAL}
        ),
        supports_composite_watermark=True,
        supports_native_cdc=True,
        notes="Requires declared domain capture extension.",
    ),
)


class CapabilityRegistry:
    """Immutable-by-convention registry used by metadata compilation."""

    def __init__(self, capabilities: tuple[EngineCapability, ...] = _DEFAULT_CAPABILITIES):
        self._by_engine = {item.engine: item for item in capabilities}
        if len(self._by_engine) != len(capabilities):
            raise ValueError("duplicate execution engine capability")

    def capability_for(self, engine: ExecutionEngine) -> EngineCapability:
        try:
            return self._by_engine[engine]
        except KeyError as exc:
            raise UnsupportedExecutionCombination(
                f"no capability profile registered for {engine.value}"
            ) from exc

    def resolve_engine(self, config: DatasetConfig) -> ExecutionEngine:
        """Resolve AUTO conservatively when source-specific capabilities are unknown."""

        if config.execution.engine is not ExecutionEngine.AUTO:
            return config.execution.engine

        capture = config.load.capture_strategy
        if capture is CaptureStrategy.MIRROR:
            return ExecutionEngine.FABRIC_MIRRORING
        return ExecutionEngine.SPARK

    def validate(self, config: DatasetConfig) -> ExecutionEngine:
        engine = self.resolve_engine(config)
        capability = self.capability_for(engine)
        capture = config.load.capture_strategy
        owner = config.execution.progress_owner

        if capture not in capability.capture_strategies:
            raise UnsupportedExecutionCombination(
                f"{engine.value} does not support capture strategy {capture.value} "
                "under the registered capability profile"
            )
        if owner not in capability.progress_owners:
            raise UnsupportedExecutionCombination(
                f"{engine.value} does not allow progress owner {owner.value}"
            )
        if (
            capture is CaptureStrategy.WATERMARK
            and config.load.watermark is not None
            and config.load.watermark.tie_breaker
            and not capability.supports_composite_watermark
        ):
            raise UnsupportedExecutionCombination(
                f"{engine.value} cannot prove composite WATERMARK ordering; "
                "use a framework-bounded engine or a stronger registered capability profile"
            )
        if (
            owner is ProgressOwner.FABRIC_NATIVE
            and engine
            not in {
                ExecutionEngine.FABRIC_COPY_JOB,
                ExecutionEngine.DATAFLOW_GEN2,
                ExecutionEngine.FABRIC_MIRRORING,
                ExecutionEngine.CUSTOM,
            }
        ):
            raise UnsupportedExecutionCombination(
                "FABRIC_NATIVE progress owner requires a native Fabric execution authority"
            )
        return engine


DEFAULT_CAPABILITY_REGISTRY = CapabilityRegistry()
