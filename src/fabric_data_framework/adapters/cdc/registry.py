"""Explicit provider CDC adapter registry.

Provider adapters are resolved by physical execution engine plus capability profile.
No provider client, credential or parser is constructed implicitly from arbitrary
metadata strings.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Mapping

from ...config import ExecutionEngine
from ...metadata.capabilities import DEBEZIUM_KAFKA_PROFILE
from .debezium_kafka import (
    DebeziumKafkaBatchResult,
    DebeziumKafkaRecord,
    DebeziumSnapshotReadPolicy,
    normalize_debezium_kafka_batch,
)
from .delta_cdf import (
    DELTA_CDF_PROFILE,
    DeltaCDFBatchResult,
    DeltaCDFRecord,
    normalize_delta_cdf_batch,
)
from .resume import DebeziumKafkaResumePlan, plan_debezium_kafka_resume


class DebeziumKafkaCDCAdapter:
    """Built-in EXTERNAL_CDC adapter for Debezium records consumed from Kafka."""

    execution_engine = ExecutionEngine.EXTERNAL_CDC
    capability_profile = DEBEZIUM_KAFKA_PROFILE

    def normalize(
        self,
        records: Sequence[DebeziumKafkaRecord],
        *,
        topic: str,
        upper_offsets: Mapping[int, int],
        complete_through_upper: bool,
        lower_offsets: Mapping[int, int] | None = None,
        snapshot_read_policy: DebeziumSnapshotReadPolicy = DebeziumSnapshotReadPolicy.ERROR,
    ) -> DebeziumKafkaBatchResult:
        return normalize_debezium_kafka_batch(
            records,
            topic=topic,
            upper_offsets=upper_offsets,
            complete_through_upper=complete_through_upper,
            lower_offsets=lower_offsets,
            snapshot_read_policy=snapshot_read_policy,
        )

    def plan_resume(
        self,
        *,
        topic: str,
        committed_checkpoint,
        earliest_offsets: Mapping[int, int],
        latest_offsets: Mapping[int, int],
        requested_upper_offsets: Mapping[int, int] | None = None,
        allow_new_partitions: bool = False,
    ) -> DebeziumKafkaResumePlan:
        return plan_debezium_kafka_resume(
            topic=topic,
            committed_checkpoint=committed_checkpoint,
            earliest_offsets=earliest_offsets,
            latest_offsets=latest_offsets,
            requested_upper_offsets=requested_upper_offsets,
            allow_new_partitions=allow_new_partitions,
        )


class DeltaCDFCDCAdapter:
    """Built-in SPARK adapter for bounded Delta Change Data Feed reads."""

    execution_engine = ExecutionEngine.SPARK
    capability_profile = DELTA_CDF_PROFILE

    def normalize(
        self,
        records: Sequence[DeltaCDFRecord],
        *,
        table_reference: str,
        key_columns: tuple[str, ...],
        upper_commit_version: int,
        complete_through_upper: bool,
        lower_committed_version: int | None = None,
    ) -> DeltaCDFBatchResult:
        return normalize_delta_cdf_batch(
            records,
            table_reference=table_reference,
            key_columns=key_columns,
            upper_commit_version=upper_commit_version,
            complete_through_upper=complete_through_upper,
            lower_committed_version=lower_committed_version,
        )


class CDCProviderAdapterRegistry:
    """Explicit profile registry used by execution backends/provider transports."""

    def __init__(self, adapters: Iterable[Any] = ()) -> None:
        self._items: dict[tuple[ExecutionEngine, str], Any] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: Any) -> None:
        engine = getattr(adapter, "execution_engine", None)
        profile = getattr(adapter, "capability_profile", None)
        if not isinstance(engine, ExecutionEngine) or not isinstance(profile, str) or not profile:
            raise ValueError(
                "CDC provider adapter requires execution_engine and capability_profile"
            )
        key = (engine, profile)
        if key in self._items:
            raise ValueError(
                f"CDC provider adapter already registered for {engine.value}/{profile}"
            )
        self._items[key] = adapter

    @property
    def supported_profiles(self) -> frozenset[tuple[ExecutionEngine, str]]:
        return frozenset(self._items)

    def resolve(self, engine: ExecutionEngine, capability_profile: str) -> Any:
        try:
            return self._items[(engine, capability_profile)]
        except KeyError as exc:
            raise KeyError(
                f"no CDC provider adapter registered for {engine.value}/{capability_profile}"
            ) from exc


DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY = CDCProviderAdapterRegistry(
    (DebeziumKafkaCDCAdapter(), DeltaCDFCDCAdapter())
)


__all__ = [
    "CDCProviderAdapterRegistry",
    "DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY",
    "DebeziumKafkaCDCAdapter",
    "DeltaCDFCDCAdapter",
]
