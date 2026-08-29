"""Execution-engine capability registry and conservative metadata compiler."""

from __future__ import annotations

from pydantic import Field

from ..config import (
    ApplyStrategy,
    CaptureStrategy,
    DatasetConfig,
    ExecutionEngine,
    FrozenModel,
    ProgressOwner,
)


class UnsupportedExecutionCombination(ValueError):
    """Raised when metadata asks an engine to guarantee semantics it cannot prove."""


DEFAULT_CAPABILITY_PROFILE = "default"
DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE = "dataflow_gen2_incremental_bucket_v1"
DEBEZIUM_KAFKA_PROFILE = "debezium_kafka_v1"


class EngineCapability(FrozenModel):
    profile_name: str = Field(default=DEFAULT_CAPABILITY_PROFILE, min_length=1)
    engine: ExecutionEngine
    capture_strategies: frozenset[CaptureStrategy]
    apply_strategies: frozenset[ApplyStrategy] = frozenset()
    progress_owners: frozenset[ProgressOwner]
    supports_composite_watermark: bool = False
    supports_native_cdc: bool = False
    supports_complete_snapshot_evidence: bool = True
    notes: str = Field(default="", max_length=1000)


_FRAMEWORK_APPLY_STRATEGIES = frozenset(
    {
        ApplyStrategy.APPEND,
        ApplyStrategy.REPLACE,
        ApplyStrategy.UPSERT,
        ApplyStrategy.SCD1,
        ApplyStrategy.SCD2,
        ApplyStrategy.SNAPSHOT_DIFF,
    }
)


_DEFAULT_CAPABILITIES = (
    EngineCapability(
        engine=ExecutionEngine.FABRIC_COPY_JOB,
        capture_strategies=frozenset(
            {CaptureStrategy.FULL, CaptureStrategy.WATERMARK, CaptureStrategy.CDC}
        ),
        progress_owners=frozenset({ProgressOwner.FABRIC_NATIVE}),
        supports_native_cdc=True,
        supports_composite_watermark=False,
        notes=(
            "Conservative capture profile: native progress is authoritative. "
            "No final-target apply strategy is certified by the generic profile."
        ),
    ),
    EngineCapability(
        engine=ExecutionEngine.FABRIC_COPY_ACTIVITY,
        capture_strategies=frozenset(
            {CaptureStrategy.FULL, CaptureStrategy.WATERMARK, CaptureStrategy.SNAPSHOT}
        ),
        progress_owners=frozenset({ProgressOwner.FRAMEWORK}),
        supports_composite_watermark=True,
        notes=(
            "Framework supplies bounded source query/state where required. "
            "No generic native apply strategy is certified."
        ),
    ),
    EngineCapability(
        engine=ExecutionEngine.DATAFLOW_GEN2,
        capture_strategies=frozenset({CaptureStrategy.FULL, CaptureStrategy.SNAPSHOT}),
        progress_owners=frozenset(
            {ProgressOwner.FRAMEWORK, ProgressOwner.FABRIC_NATIVE}
        ),
        supports_composite_watermark=False,
        notes=(
            "Conservative baseline. Dataflow Gen2 incremental refresh is not assumed "
            "to satisfy the generic WATERMARK contract without an explicit profile."
        ),
    ),
    EngineCapability(
        profile_name=DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
        engine=ExecutionEngine.DATAFLOW_GEN2,
        capture_strategies=frozenset({CaptureStrategy.WATERMARK}),
        progress_owners=frozenset({ProgressOwner.FABRIC_NATIVE}),
        supports_composite_watermark=False,
        supports_complete_snapshot_evidence=False,
        notes=(
            "Fabric Dataflow Gen2 DateTime-bucket incremental refresh profile. "
            "This profile certifies capture/staging only; downstream SCD1/UPSERT/SCD2 "
            "remains framework-owned unless a separate native apply capability is certified."
        ),
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
        apply_strategies=_FRAMEWORK_APPLY_STRATEGIES,
        progress_owners=frozenset({ProgressOwner.FRAMEWORK, ProgressOwner.EXTERNAL}),
        supports_composite_watermark=True,
        notes=(
            "Framework-controlled programmable execution and the default portable "
            "apply authority for implemented framework apply strategies."
        ),
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
        notes=(
            "Generic external CDC boundary. A named provider profile is preferred when "
            "the framework ships a provider-specific adapter/certification."
        ),
    ),
    EngineCapability(
        profile_name=DEBEZIUM_KAFKA_PROFILE,
        engine=ExecutionEngine.EXTERNAL_CDC,
        capture_strategies=frozenset({CaptureStrategy.CDC}),
        progress_owners=frozenset({ProgressOwner.EXTERNAL}),
        supports_native_cdc=True,
        supports_complete_snapshot_evidence=False,
        notes=(
            "Debezium records consumed from Kafka. Canonical source ordering is Kafka "
            "topic/partition/offset; database LSN/binlog coordinates remain metadata. "
            "Downstream apply stays independently selected and framework-owned by default."
        ),
    ),
    EngineCapability(
        engine=ExecutionEngine.SQL,
        capture_strategies=frozenset(
            {CaptureStrategy.FULL, CaptureStrategy.WATERMARK, CaptureStrategy.SNAPSHOT}
        ),
        progress_owners=frozenset({ProgressOwner.FRAMEWORK}),
        supports_composite_watermark=True,
        notes=(
            "SQL is available as a physical execution kind, but generic target apply "
            "semantics remain uncertified until target-specific profiles are added."
        ),
    ),
    EngineCapability(
        engine=ExecutionEngine.CUSTOM,
        capture_strategies=frozenset(CaptureStrategy),
        apply_strategies=frozenset(ApplyStrategy),
        progress_owners=frozenset(
            {ProgressOwner.FRAMEWORK, ProgressOwner.FABRIC_NATIVE, ProgressOwner.EXTERNAL}
        ),
        supports_composite_watermark=True,
        supports_native_cdc=True,
        notes="Requires declared controlled domain extension for the selected stage.",
    ),
)


class CapabilityRegistry:
    """Immutable-by-convention registry used by metadata compilation.

    Capabilities are keyed by physical engine plus a named profile so product- or
    connector-specific behavior does not leak into global semantic assumptions.
    Capture and apply are validated independently.
    """

    def __init__(self, capabilities: tuple[EngineCapability, ...] = _DEFAULT_CAPABILITIES):
        self._by_key = {(item.engine, item.profile_name): item for item in capabilities}
        if len(self._by_key) != len(capabilities):
            raise ValueError("duplicate execution engine capability profile")

    def capability_for(
        self,
        engine: ExecutionEngine,
        profile_name: str | None = None,
    ) -> EngineCapability:
        profile = profile_name or DEFAULT_CAPABILITY_PROFILE
        try:
            return self._by_key[(engine, profile)]
        except KeyError as exc:
            raise UnsupportedExecutionCombination(
                f"no capability profile registered for {engine.value}/{profile}"
            ) from exc

    def resolve_capture_engine(self, config: DatasetConfig) -> ExecutionEngine:
        """Resolve capture AUTO conservatively when source capabilities are unknown."""

        if config.execution.engine is not ExecutionEngine.AUTO:
            return config.execution.engine

        if config.execution.capability_profile is not None:
            raise UnsupportedExecutionCombination(
                "capture capability_profile requires an explicit execution engine"
            )

        if config.load.capture_strategy is CaptureStrategy.MIRROR:
            return ExecutionEngine.FABRIC_MIRRORING
        return ExecutionEngine.SPARK

    def resolve_apply_engine(self, config: DatasetConfig) -> ExecutionEngine:
        """Resolve apply AUTO to the portable framework implementation authority."""

        if config.execution.apply_engine is not ExecutionEngine.AUTO:
            return config.execution.apply_engine
        if config.execution.apply_capability_profile is not None:
            raise UnsupportedExecutionCombination(
                "apply_capability_profile requires an explicit apply_engine"
            )
        return ExecutionEngine.SPARK

    def resolve_engine(self, config: DatasetConfig) -> ExecutionEngine:
        """Backward-compatible alias for capture-engine resolution."""

        return self.resolve_capture_engine(config)

    def validate_capture(self, config: DatasetConfig) -> ExecutionEngine:
        engine = self.resolve_capture_engine(config)
        capability = self.capability_for(engine, config.execution.capability_profile)
        capture = config.load.capture_strategy
        owner = config.execution.progress_owner

        if capture not in capability.capture_strategies:
            raise UnsupportedExecutionCombination(
                f"{engine.value}/{capability.profile_name} does not support capture "
                f"strategy {capture.value} under the registered capability profile"
            )
        if owner not in capability.progress_owners:
            raise UnsupportedExecutionCombination(
                f"{engine.value}/{capability.profile_name} does not allow progress "
                f"owner {owner.value}"
            )
        if (
            capture is CaptureStrategy.WATERMARK
            and config.load.watermark is not None
            and config.load.watermark.tie_breaker
            and not capability.supports_composite_watermark
        ):
            raise UnsupportedExecutionCombination(
                f"{engine.value}/{capability.profile_name} cannot prove composite "
                "WATERMARK ordering; use a framework-bounded engine or a stronger "
                "registered capability profile"
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
                "FABRIC_NATIVE progress owner requires a native Fabric capture authority"
            )
        return engine

    def validate_apply(self, config: DatasetConfig) -> ExecutionEngine:
        engine = self.resolve_apply_engine(config)
        capability = self.capability_for(
            engine,
            config.execution.apply_capability_profile,
        )
        apply_strategy = config.load.apply_strategy
        if apply_strategy not in capability.apply_strategies:
            raise UnsupportedExecutionCombination(
                f"{engine.value}/{capability.profile_name} does not certify apply "
                f"strategy {apply_strategy.value}; use the framework apply engine or "
                "an explicitly certified apply capability profile"
            )
        return engine

    def validate(self, config: DatasetConfig) -> ExecutionEngine:
        """Validate both stages and return capture engine for compatibility."""

        capture_engine = self.validate_capture(config)
        self.validate_apply(config)
        return capture_engine


DEFAULT_CAPABILITY_REGISTRY = CapabilityRegistry()


__all__ = [
    "CapabilityRegistry",
    "DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE",
    "DEBEZIUM_KAFKA_PROFILE",
    "DEFAULT_CAPABILITY_PROFILE",
    "DEFAULT_CAPABILITY_REGISTRY",
    "EngineCapability",
    "UnsupportedExecutionCombination",
]
