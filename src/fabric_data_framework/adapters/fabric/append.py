"""Distributed Fabric Spark/Delta APPEND physical runtime.

The runtime never materializes the target table or incoming batch in Python. Exact
incoming duplicates are collapsed in Spark, identity conflicts are detected with
null-safe distributed joins, and only genuinely new identities are inserted by Delta
MERGE. Python receives bounded scalar counts and LIMIT-1 guard results only.
"""

from __future__ import annotations

from builtins import BaseExceptionGroup
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterator
from uuid import UUID, uuid4

from sqlalchemy import Engine

from fabric_data_framework.adapters.fabric.spark_protocols import SparkSessionLike
from fabric_data_framework.contracts.append import FRAMEWORK_FIELD_PREFIX
from fabric_data_framework.contracts.audit import MutationCounts
from fabric_data_framework.contracts.temporal import utc_now
from fabric_data_framework.control_plane.dataset_lease import (
    DatasetLeaseConflict,
    DatasetLeaseState,
    acquire_dataset_lease,
    release_dataset_lease,
)


class SparkAppendError(RuntimeError):
    """Fail-closed distributed APPEND error."""


@dataclass(frozen=True)
class SparkDeltaAppendRequest:
    dataset_id: str
    dataset_run_id: UUID
    incoming_relation: str
    target_table: str
    append_identity: tuple[str, ...]
    business_columns: tuple[str, ...]
    expected_incoming_rows: int | None = None


@dataclass(frozen=True)
class SparkAppendEvidence:
    dataset_id: str
    incoming_rows: int
    unique_incoming: int
    inserted: int
    replayed: int
    duplicate_incoming: int

    @property
    def mutations(self) -> MutationCounts:
        return MutationCounts(inserted=self.inserted)


@dataclass(frozen=True)
class _AppendStageCounts:
    incoming_rows: int
    unique_incoming: int
    duplicate_incoming: int


def _q(value: str) -> str:
    if not value:
        raise ValueError("Spark identifier cannot be empty")
    return "`" + value.replace("`", "``") + "`"


def _relation(value: str) -> str:
    parts = value.split(".")
    if not parts or any(not part for part in parts):
        raise ValueError(f"invalid Spark relation: {value!r}")
    return ".".join(_q(part) for part in parts)


def _first_scalar(spark: SparkSessionLike, sql: str, *, label: str) -> object:
    rows = spark.sql(sql).collect()
    if not rows:
        raise SparkAppendError(f"Spark query returned no {label}")
    row = rows[0]
    if hasattr(row, "asDict"):
        values = list(row.asDict().values())
        if not values:
            raise SparkAppendError(f"Spark query returned empty {label}")
        return values[0]
    if isinstance(row, dict):
        if not row:
            raise SparkAppendError(f"Spark query returned empty {label}")
        return next(iter(row.values()))
    try:
        return row[0]
    except Exception as exc:  # pragma: no cover - defensive provider wrapper guard
        raise SparkAppendError(f"Spark query returned unreadable {label}") from exc


def _count(spark: SparkSessionLike, sql: str, *, label: str) -> int:
    value = _first_scalar(spark, sql, label=label)
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise SparkAppendError(f"Spark returned invalid {label}: {value!r}") from exc
    if result < 0:
        raise SparkAppendError(f"Spark returned negative {label}")
    return result


def _has_rows(spark: SparkSessionLike, sql: str) -> bool:
    return bool(spark.sql(sql).collect())


def _select(alias: str, columns: tuple[str, ...]) -> str:
    return ", ".join(f"{alias}.{_q(column)}" for column in columns)


def _join(left: str, right: str, keys: tuple[str, ...]) -> str:
    return " AND ".join(f"{left}.{_q(key)} <=> {right}.{_q(key)}" for key in keys)


def _payload_equal(left: str, right: str, columns: tuple[str, ...]) -> str:
    return " AND ".join(
        f"{left}.{_q(column)} <=> {right}.{_q(column)}" for column in columns
    )


def _validate_request(request: SparkDeltaAppendRequest) -> None:
    if not request.dataset_id or not request.incoming_relation or not request.target_table:
        raise ValueError("dataset_id, incoming_relation and target_table are required")
    if not request.append_identity:
        raise ValueError("APPEND requires at least one append_identity column")
    if len(set(request.append_identity)) != len(request.append_identity):
        raise ValueError("append_identity columns must be unique")
    if not request.business_columns:
        raise ValueError("distributed APPEND requires explicit business_columns")
    if len(set(request.business_columns)) != len(request.business_columns):
        raise ValueError("business_columns must be unique")
    if not set(request.append_identity).issubset(request.business_columns):
        raise ValueError("business_columns must include every append_identity column")
    framework_owned = [
        column for column in request.business_columns if column.startswith(FRAMEWORK_FIELD_PREFIX)
    ]
    if framework_owned:
        raise ValueError(
            "business_columns cannot contain framework-owned fields: "
            + ", ".join(sorted(framework_owned))
        )
    if request.expected_incoming_rows is not None and request.expected_incoming_rows < 0:
        raise ValueError("expected_incoming_rows cannot be negative")


@contextmanager
def _append_lease(
    engine: Engine,
    request: SparkDeltaAppendRequest,
) -> Iterator[DatasetLeaseState]:
    try:
        lease = acquire_dataset_lease(
            engine,
            dataset_id=request.dataset_id,
            lease_owner=f"fabric-spark-append:{uuid4()}",
            dataset_run_id=request.dataset_run_id,
            review_deadline=utc_now() + timedelta(days=1),
        )
    except DatasetLeaseConflict as exc:
        raise SparkAppendError(
            "APPEND mutation is already claimed by another dataset run"
        ) from exc
    try:
        yield lease
    except BaseException as execution_error:
        try:
            release_dataset_lease(engine, lease)
        except BaseException as release_error:
            raise BaseExceptionGroup(
                "APPEND execution and lease release both failed",
                (execution_error, release_error),
            ) from execution_error
        raise
    else:
        try:
            release_dataset_lease(engine, lease)
        except BaseException as release_error:
            raise SparkAppendError(
                "APPEND completed but its durable dataset lease could not be released"
            ) from release_error


@contextmanager
def _deduplicated_stage(
    spark: SparkSessionLike,
    request: SparkDeltaAppendRequest,
) -> Iterator[str]:
    stage = f"_fdf_append_{uuid4().hex}"
    spark.sql(
        "CREATE OR REPLACE TEMP VIEW "
        f"{_q(stage)} AS SELECT DISTINCT {_select('i', request.business_columns)} "
        f"FROM {_relation(request.incoming_relation)} AS i "
        "/* fdf:append_stage */"
    )
    try:
        yield stage
    except BaseException as execution_error:
        try:
            spark.sql(f"DROP VIEW IF EXISTS {_q(stage)} /* fdf:append_stage_drop */")
        except BaseException as cleanup_error:
            raise BaseExceptionGroup(
                "APPEND execution and temporary-stage cleanup both failed",
                (execution_error, cleanup_error),
            ) from execution_error
        raise
    else:
        try:
            spark.sql(f"DROP VIEW IF EXISTS {_q(stage)} /* fdf:append_stage_drop */")
        except BaseException as cleanup_error:
            raise SparkAppendError(
                "APPEND completed but temporary-stage cleanup failed"
            ) from cleanup_error


def _incoming_conflict_sql(stage: str, request: SparkDeltaAppendRequest) -> str:
    grouped = ", ".join(_q(column) for column in request.append_identity)
    return (
        "SELECT 1 FROM ("
        f"SELECT {grouped}, COUNT(*) AS _fdf_variants FROM {_q(stage)} "
        f"GROUP BY {grouped} HAVING COUNT(*) > 1"
        ") AS c LIMIT 1 /* fdf:append_incoming_conflict */"
    )


def _target_duplicate_sql(stage: str, request: SparkDeltaAppendRequest) -> str:
    grouped = ", ".join(f"t.{_q(column)}" for column in request.append_identity)
    return (
        f"SELECT 1 FROM {_relation(request.target_table)} AS t "
        f"JOIN {_q(stage)} AS s ON {_join('t', 's', request.append_identity)} "
        f"GROUP BY {grouped} HAVING COUNT(*) > 1 LIMIT 1 "
        "/* fdf:append_target_duplicate */"
    )


def _target_conflict_sql(stage: str, request: SparkDeltaAppendRequest) -> str:
    return (
        f"SELECT 1 FROM {_relation(request.target_table)} AS t "
        f"JOIN {_q(stage)} AS s ON {_join('t', 's', request.append_identity)} "
        f"WHERE NOT ({_payload_equal('t', 's', request.business_columns)}) LIMIT 1 "
        "/* fdf:append_target_conflict */"
    )


def _replay_count_sql(stage: str, request: SparkDeltaAppendRequest) -> str:
    return (
        "SELECT COUNT(*) FROM "
        f"{_q(stage)} AS s JOIN {_relation(request.target_table)} AS t "
        f"ON {_join('t', 's', request.append_identity)} "
        "/* fdf:append_replay_count */"
    )


def _merge_sql(stage: str, request: SparkDeltaAppendRequest) -> str:
    columns = ", ".join(_q(column) for column in request.business_columns)
    values = ", ".join(f"s.{_q(column)}" for column in request.business_columns)
    return (
        f"MERGE INTO {_relation(request.target_table)} AS t USING {_q(stage)} AS s "
        f"ON {_join('t', 's', request.append_identity)} "
        f"WHEN NOT MATCHED THEN INSERT ({columns}) VALUES ({values}) "
        "/* fdf:append_merge */"
    )


def _missing_after_merge_sql(stage: str, request: SparkDeltaAppendRequest) -> str:
    return (
        f"SELECT 1 FROM {_q(stage)} AS s LEFT ANTI JOIN "
        f"{_relation(request.target_table)} AS t ON {_join('t', 's', request.append_identity)} "
        "LIMIT 1 /* fdf:append_verify_missing */"
    )


def _measure_stage(
    spark: SparkSessionLike,
    stage: str,
    request: SparkDeltaAppendRequest,
) -> _AppendStageCounts:
    incoming_rows = _count(
        spark,
        f"SELECT COUNT(*) FROM {_relation(request.incoming_relation)} "
        "/* fdf:append_incoming_count */",
        label="APPEND incoming row count",
    )
    if request.expected_incoming_rows is not None and incoming_rows != request.expected_incoming_rows:
        raise SparkAppendError(
            "APPEND staged row count does not match framework accounting: "
            f"expected={request.expected_incoming_rows}, actual={incoming_rows}"
        )

    unique_incoming = _count(
        spark,
        f"SELECT COUNT(*) FROM {_q(stage)} /* fdf:append_stage_count */",
        label="APPEND unique incoming row count",
    )
    if unique_incoming > incoming_rows:
        raise SparkAppendError("APPEND distinct stage cannot exceed incoming row count")
    return _AppendStageCounts(
        incoming_rows=incoming_rows,
        unique_incoming=unique_incoming,
        duplicate_incoming=incoming_rows - unique_incoming,
    )


def _assert_premerge_consistency(
    spark: SparkSessionLike,
    stage: str,
    request: SparkDeltaAppendRequest,
) -> None:
    if _has_rows(spark, _incoming_conflict_sql(stage, request)):
        raise SparkAppendError(
            "incoming batch reuses append identity with conflicting business payload"
        )
    if _has_rows(spark, _target_duplicate_sql(stage, request)):
        raise SparkAppendError("target contains duplicate APPEND identity for incoming keys")
    if _has_rows(spark, _target_conflict_sql(stage, request)):
        raise SparkAppendError("append identity already exists with different business payload")


def _measure_replay(
    spark: SparkSessionLike,
    stage: str,
    request: SparkDeltaAppendRequest,
    counts: _AppendStageCounts,
) -> tuple[int, int]:
    replayed = _count(
        spark,
        _replay_count_sql(stage, request),
        label="APPEND replay row count",
    )
    if replayed > counts.unique_incoming:
        raise SparkAppendError("APPEND replay count exceeds unique incoming rows")
    return replayed, counts.unique_incoming - replayed


def _verify_after_merge(
    spark: SparkSessionLike,
    stage: str,
    request: SparkDeltaAppendRequest,
) -> None:
    if _has_rows(spark, _missing_after_merge_sql(stage, request)):
        raise SparkAppendError("APPEND target verification found missing incoming identities")
    if _has_rows(spark, _target_duplicate_sql(stage, request)):
        raise SparkAppendError("APPEND target verification found duplicate identities")
    if _has_rows(spark, _target_conflict_sql(stage, request)):
        raise SparkAppendError("APPEND target verification found conflicting payload")


def _execute_staged_append(
    spark: SparkSessionLike,
    stage: str,
    request: SparkDeltaAppendRequest,
) -> SparkAppendEvidence:
    counts = _measure_stage(spark, stage, request)
    _assert_premerge_consistency(spark, stage, request)
    replayed, inserted = _measure_replay(spark, stage, request, counts)
    spark.sql(_merge_sql(stage, request))
    _verify_after_merge(spark, stage, request)
    return SparkAppendEvidence(
        dataset_id=request.dataset_id,
        incoming_rows=counts.incoming_rows,
        unique_incoming=counts.unique_incoming,
        inserted=inserted,
        replayed=replayed,
        duplicate_incoming=counts.duplicate_incoming,
    )


class FabricSparkDeltaAppendRuntime:
    """Execute one idempotent APPEND batch entirely inside Spark/Delta."""

    def __init__(self, spark: SparkSessionLike) -> None:
        self._spark = spark

    def execute(
        self,
        *,
        control_plane_engine: Engine,
        request: SparkDeltaAppendRequest,
    ) -> SparkAppendEvidence:
        _validate_request(request)
        if not self._spark.catalog.tableExists(request.target_table):
            raise SparkAppendError("APPEND target table does not exist")

        with _append_lease(control_plane_engine, request):
            with _deduplicated_stage(self._spark, request) as stage:
                return _execute_staged_append(self._spark, stage, request)


__all__ = [
    "FabricSparkDeltaAppendRuntime",
    "SparkAppendError",
    "SparkAppendEvidence",
    "SparkDeltaAppendRequest",
]
