"""Provider CDC envelope adapters.

Canonical CDC correctness remains in :mod:`fabric_data_framework.capture.cdc`.
"""

from .debezium_kafka import (
    DebeziumKafkaAdapterError,
    DebeziumKafkaBatchResult,
    DebeziumKafkaRecord,
    DebeziumSnapshotReadPolicy,
    normalize_debezium_kafka_batch,
)
from .registry import (
    CDCProviderAdapterRegistry,
    DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY,
    DebeziumKafkaCDCAdapter,
)
from .resume import (
    DebeziumKafkaPartitionResume,
    DebeziumKafkaResumeGapError,
    DebeziumKafkaResumePlan,
    plan_debezium_kafka_resume,
)

__all__ = [
    "CDCProviderAdapterRegistry",
    "DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY",
    "DebeziumKafkaAdapterError",
    "DebeziumKafkaBatchResult",
    "DebeziumKafkaCDCAdapter",
    "DebeziumKafkaPartitionResume",
    "DebeziumKafkaRecord",
    "DebeziumKafkaResumeGapError",
    "DebeziumKafkaResumePlan",
    "DebeziumSnapshotReadPolicy",
    "normalize_debezium_kafka_batch",
    "plan_debezium_kafka_resume",
]
