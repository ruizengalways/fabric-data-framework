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
from .resume import (
    DebeziumKafkaPartitionResume,
    DebeziumKafkaResumeGapError,
    DebeziumKafkaResumePlan,
    plan_debezium_kafka_resume,
)

__all__ = [
    "DebeziumKafkaAdapterError",
    "DebeziumKafkaBatchResult",
    "DebeziumKafkaPartitionResume",
    "DebeziumKafkaRecord",
    "DebeziumKafkaResumeGapError",
    "DebeziumKafkaResumePlan",
    "DebeziumSnapshotReadPolicy",
    "normalize_debezium_kafka_batch",
    "plan_debezium_kafka_resume",
]
