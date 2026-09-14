"""Production Spark/Delta physicalization for authoritative-history current projections.

The implementation is intentionally Spark-SQL/DataFrame-reader based without importing
``pyspark`` at module import time, so the wheel remains importable outside Fabric. The
runtime never interprets history CDF rows as current-state events: CDF identifies affected
business keys, then authoritative history is read exactly at the frozen upper version.
"""

from __future__ import annotations

from builtins import BaseExceptionGroup
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterator, Protocol
from uuid import UUID, uuid4

from sqlalchemy import Engine

from fabric_data_framework.capture.cdc import build_cdc_checkpoint
from fabric_data_framework.contracts.audit import MutationCounts
from fabric_data_framework.contracts.current_projection import (
    current_projection_checkpoint_partition,
)
from fabric_data_framework.contracts.current_projection_execution import (
    CurrentProjectionExecutionError,
    CurrentProjectionExecutionResult,
)
from fabric_data_framework.contracts.runtime import StateCommitGate
from fabric_data_framework.control_plane.dataset_lease import (
    DatasetLeaseConflict,
    DatasetLeaseState,
    acquire_dataset_lease,
    release_dataset_lease,
)
from fabric_data_framework.control_plane.io import (
    CDCCheckpointState,
    commit_cdc_checkpoint,
    read_cdc_checkpoint,
)
from fabric_data_framework.deployment.current_projection import quote_spark_relation


class SparkFrameLike(Protocol):
    def collect(self): ...
    def createOrReplaceTempView(self, name: str) -> None: ...


class SparkReaderLike(Protocol):
    def format(self, value: str) -> "SparkReaderLike": ...
    def option(self, key: str, value: object) -> "SparkReaderLike": ...
    def table(self, name: str) -> SparkFrameLike: ...


class SparkCatalogLike(Protocol):
    def tableExists(self, name: str) -> bool: ...


class SparkSessionLike(Protocol):
    @property
    def read(self) -> SparkReaderLike: ...

    @property
    def catalog(self) -> SparkCatalogLike: ...

    def sql(self, query: str) -> SparkFrameLike: ...


@dataclass(frozen=True)
class SparkDeltaProjectionRequest:
    dataset_id: str
    dataset_run_id: UUID
    history_table: str
    target_table: str
    business_key: tuple[str, ...]
    projected_columns: tuple[str, ...]
    current_flag_column: str = "_framework_is_current"
    requested_upper_version: int | None = None
    reconciliation_required: bool = True


@dataclass(frozen=True)
class SparkCurrentProjectionEvidence:
    dataset_id: str
    lower_version: int | None
    upper_version: int
    affected_keys: int
    mutations: MutationCounts
    rebuilt: bool = False


@dataclass(frozen=True)
class _ProjectionVersionWindow:
    checkpoint_state: CDCCheckpointState | None
    lower_version: int | None
    upper_version: int


@dataclass(frozen=True)
class _ProjectionViews:
    cdf: str
    keys: str
    stage: str
    before: str


@dataclass(frozen=True)
class _ProjectionMutationOutcome:
    affected_keys: int
    mutations: MutationCounts
    rebuilt: bool = False


SparkProjectionReconciliation = Callable[[SparkCurrentProjectionEvidence], bool]


def _q(value: str) -> str:
    if not value:
        raise ValueError("Spark identifier cannot be empty")
    return "`" + value.replace("`", "``") + "`"


def _first_scalar(frame: SparkFrameLike, *, label: str) -> object:
    rows = frame.collect()
    if not rows:
        raise CurrentProjectionExecutionError(f"Spark query returned no {label}")
    row = rows[0]
    if hasattr(row, "asDict"):
        values = list(row.asDict().values())
        if not values:
            raise CurrentProjectionExecutionError(f"Spark query returned empty {label}")
        return values[0]
    if isinstance(row, dict):
        if not row:
            raise CurrentProjectionExecutionError(f"Spark query returned empty {label}")
        return next(iter(row.values()))
    try:
        return row[0]
    except Exception as exc:  # pragma: no cover - defensive against provider row wrappers
        raise CurrentProjectionExecutionError(
            f"Spark query returned unreadable {label}"
        ) from exc


def _count(spark: SparkSessionLike, sql: str, *, label: str) -> int:
    value = _first_scalar(spark.sql(sql), label=label)
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise CurrentProjectionExecutionError(f"Spark returned invalid {label}: {value!r}") from exc
    if result < 0:
        raise CurrentProjectionExecutionError(f"Spark returned negative {label}")
    return result


def _has_rows(spark: SparkSessionLike, sql: str) -> bool:
    return bool(spark.sql(sql).collect())


def _join(left: str, right: str, keys: tuple[str, ...]) -> str:
    return " AND ".join(f"{left}.{_q(key)} <=> {right}.{_q(key)}" for key in keys)


def _projected_select(alias: str, columns: tuple[str, ...]) -> str:
    return ", ".join(f"{alias}.{_q(column)}" for column in columns)


def _processed_version(
    state: CDCCheckpointState | None,
    *,
    request: SparkDeltaProjectionRequest,
) -> int | None:
    if state is None:
        return None
    partition = current_projection_checkpoint_partition(
        table_reference=request.history_table,
        business_key=request.business_key,
        projected_columns=request.projected_columns,
        current_flag_column=request.current_flag_column,
    )
    if len(state.checkpoint.positions) != 1:
        raise CurrentProjectionExecutionError(
            "current projection checkpoint must contain exactly one semantic partition"
        )
    position = state.checkpoint.position_for(partition)
    if position is None or len(position) != 1:
        raise CurrentProjectionExecutionError(
            "current projection checkpoint does not match current projection semantics"
        )
    return int(position[0])


def _validate_request(
    request: SparkDeltaProjectionRequest,
    reconcile: SparkProjectionReconciliation | None,
) -> None:
    if not request.business_key or not request.projected_columns:
        raise ValueError("business_key and projected_columns are required")
    if not set(request.business_key).issubset(request.projected_columns):
        raise ValueError("projected_columns must include every business key column")
    if request.reconciliation_required and reconcile is None:
        raise CurrentProjectionExecutionError(
            "required Spark current-projection reconciliation callback is missing"
        )


def _latest_history_version(spark: SparkSessionLike, table_reference: str) -> int:
    relation = quote_spark_relation(table_reference)
    rows = spark.sql(f"DESCRIBE HISTORY {relation} LIMIT 1").collect()
    if not rows:
        raise CurrentProjectionExecutionError("Delta history returned no commits")
    row = rows[0]
    if hasattr(row, "asDict"):
        value = row.asDict().get("version")
    elif isinstance(row, dict):
        value = row.get("version")
    else:
        try:
            value = row[0]
        except Exception as exc:  # pragma: no cover - provider row wrapper guard
            raise CurrentProjectionExecutionError(
                "Delta history version could not be read"
            ) from exc
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise CurrentProjectionExecutionError(f"invalid Delta history version: {value!r}") from exc
    if version < 0:
        raise CurrentProjectionExecutionError("Delta history version cannot be negative")
    return version


def _resolve_version_window(
    spark: SparkSessionLike,
    engine: Engine,
    request: SparkDeltaProjectionRequest,
    *,
    rebuild: bool,
) -> _ProjectionVersionWindow:
    checkpoint_state = read_cdc_checkpoint(engine, request.dataset_id)
    if checkpoint_state is None and not rebuild:
        raise CurrentProjectionExecutionError(
            "current projection is uninitialized; run full rebuild before incremental execution"
        )
    lower = _processed_version(checkpoint_state, request=request)
    latest = _latest_history_version(spark, request.history_table)
    upper = latest if request.requested_upper_version is None else request.requested_upper_version
    if upper > latest:
        message = (
            "requested rebuild version is ahead of authoritative history"
            if rebuild
            else "requested projection upper version is ahead of authoritative history"
        )
        raise CurrentProjectionExecutionError(message)
    if lower is not None and upper < lower:
        message = (
            "full current projection rebuild cannot rewind committed history progress"
            if rebuild
            else "current projection cannot rewind committed history progress"
        )
        raise CurrentProjectionExecutionError(message)
    return _ProjectionVersionWindow(
        checkpoint_state=checkpoint_state,
        lower_version=lower,
        upper_version=upper,
    )


def _commit_projection_checkpoint(
    engine: Engine,
    request: SparkDeltaProjectionRequest,
    window: _ProjectionVersionWindow,
    *,
    reconciliation_passed: bool,
) -> CDCCheckpointState:
    gate = StateCommitGate(
        target_committed=True,
        reconciliation_required=request.reconciliation_required,
        reconciliation_passed=reconciliation_passed,
    )
    if not gate.can_advance_state:
        raise CurrentProjectionExecutionError(
            "current projection reconciliation failed; checkpoint was not advanced"
        )
    return commit_cdc_checkpoint(
        engine,
        dataset_id=request.dataset_id,
        checkpoint=build_cdc_checkpoint(
            {
                current_projection_checkpoint_partition(
                    table_reference=request.history_table,
                    business_key=request.business_key,
                    projected_columns=request.projected_columns,
                    current_flag_column=request.current_flag_column,
                ): (window.upper_version,)
            }
        ),
        dataset_run_id=request.dataset_run_id,
        expected_version=(
            window.checkpoint_state.version if window.checkpoint_state is not None else 0
        ),
        gate=gate,
    )


@contextmanager
def _projection_lease(
    engine: Engine,
    request: SparkDeltaProjectionRequest,
) -> Iterator[DatasetLeaseState]:
    try:
        lease = acquire_dataset_lease(
            engine,
            dataset_id=request.dataset_id,
            lease_owner=f"fabric-spark-current-projection:{uuid4()}",
            dataset_run_id=request.dataset_run_id,
            review_deadline=datetime.now(timezone.utc) + timedelta(days=1),
        )
    except DatasetLeaseConflict as exc:
        raise CurrentProjectionExecutionError(
            "current projection mutation is already claimed by another dataset run"
        ) from exc
    try:
        yield lease
    except BaseException as execution_error:
        try:
            release_dataset_lease(engine, lease)
        except BaseException as release_error:
            raise BaseExceptionGroup(
                "current projection execution and lease release both failed",
                (execution_error, release_error),
            ) from execution_error
        raise
    else:
        try:
            release_dataset_lease(engine, lease)
        except BaseException as release_error:
            raise CurrentProjectionExecutionError(
                "current projection completed but its durable dataset lease could not be released"
            ) from release_error


def _new_views() -> _ProjectionViews:
    token = uuid4().hex
    return _ProjectionViews(
        cdf=f"_fdf_cdf_{token}",
        keys=f"_fdf_keys_{token}",
        stage=f"_fdf_stage_{token}",
        before=f"_fdf_before_{token}",
    )


def _load_affected_keys(
    spark: SparkSessionLike,
    request: SparkDeltaProjectionRequest,
    window: _ProjectionVersionWindow,
    views: _ProjectionViews,
) -> int:
    assert window.lower_version is not None
    start = window.lower_version + 1
    try:
        cdf = (
            spark.read.format("delta")
            .option("readChangeFeed", "true")
            .option("startingVersion", start)
            .option("endingVersion", window.upper_version)
            .table(request.history_table)
        )
        cdf.createOrReplaceTempView(views.cdf)
    except Exception as exc:
        raise CurrentProjectionExecutionError(
            "authoritative history CDF range is unavailable; explicit rebuild is required"
        ) from exc
    null_predicate = " OR ".join(f"{_q(key)} IS NULL" for key in request.business_key)
    if _has_rows(
        spark,
        f"SELECT 1 FROM {_q(views.cdf)} WHERE {null_predicate} LIMIT 1",
    ):
        raise CurrentProjectionExecutionError(
            "history CDF contains a row with an incomplete business key"
        )
    key_sql = ", ".join(_q(key) for key in request.business_key)
    spark.sql(
        f"CREATE OR REPLACE TEMP VIEW {_q(views.keys)} AS "
        f"SELECT DISTINCT {key_sql} FROM {_q(views.cdf)}"
    )
    return _count(
        spark,
        f"SELECT COUNT(*) FROM {_q(views.keys)} /* fdf:affected_count */",
        label="affected-key count",
    )


def _history_duplicate_sql(
    request: SparkDeltaProjectionRequest,
    views: _ProjectionViews,
    window: _ProjectionVersionWindow,
) -> str:
    history_sql = quote_spark_relation(request.history_table)
    key_join = _join("h", "k", request.business_key)
    grouped_keys = ", ".join(f"k.{_q(key)}" for key in request.business_key)
    return (
        f"SELECT 1 FROM {history_sql} VERSION AS OF {window.upper_version} h "
        f"JOIN {_q(views.keys)} k ON {key_join} "
        f"WHERE h.{_q(request.current_flag_column)} = true "
        f"GROUP BY {grouped_keys} "
        "HAVING COUNT(*) > 1 LIMIT 1 /* fdf:history_duplicate_current */"
    )


def _stage_sql(
    request: SparkDeltaProjectionRequest,
    views: _ProjectionViews,
    window: _ProjectionVersionWindow,
) -> str:
    history_sql = quote_spark_relation(request.history_table)
    key_join = _join("h", "k", request.business_key)
    select_items = []
    for column in request.projected_columns:
        source_alias = "k" if column in request.business_key else "h"
        select_items.append(f"{source_alias}.{_q(column)} AS {_q(column)}")
    present_expr = (
        f"h.{_q(request.business_key[0])} IS NOT NULL AS {_q('__fdf_present')}"
    )
    return (
        f"CREATE OR REPLACE TEMP VIEW {_q(views.stage)} AS SELECT "
        + ", ".join(select_items + [present_expr])
        + f" FROM {_q(views.keys)} k LEFT JOIN {history_sql} VERSION AS OF "
        + f"{window.upper_version} h ON {key_join} "
        + f"AND h.{_q(request.current_flag_column)} = true"
    )


def _before_sql(request: SparkDeltaProjectionRequest, views: _ProjectionViews) -> str:
    target_sql = quote_spark_relation(request.target_table)
    return (
        f"CREATE OR REPLACE TEMP VIEW {_q(views.before)} AS SELECT t.* FROM {target_sql} t "
        f"JOIN {_q(views.keys)} k ON {_join('t', 'k', request.business_key)}"
    )


def _target_duplicate_sql(
    request: SparkDeltaProjectionRequest,
    views: _ProjectionViews,
) -> str:
    grouped = ", ".join(f"t.{_q(key)}" for key in request.business_key)
    return (
        f"SELECT 1 FROM {_q(views.before)} t GROUP BY {grouped} "
        "HAVING COUNT(*) > 1 LIMIT 1 /* fdf:target_duplicate_key */"
    )


def _mutation_counts(
    spark: SparkSessionLike,
    request: SparkDeltaProjectionRequest,
    views: _ProjectionViews,
) -> MutationCounts:
    matched = _join("s", "t", request.business_key)
    first_key = _q(request.business_key[0])
    inserts = _count(
        spark,
        f"SELECT COUNT(*) FROM {_q(views.stage)} s LEFT JOIN {_q(views.before)} t ON {matched} "
        f"WHERE s.{_q('__fdf_present')} = true AND t.{first_key} IS NULL "
        "/* fdf:insert_count */",
        label="projection insert count",
    )
    deletes = _count(
        spark,
        f"SELECT COUNT(*) FROM {_q(views.before)} t JOIN {_q(views.stage)} s ON {matched} "
        f"WHERE s.{_q('__fdf_present')} = false /* fdf:delete_count */",
        label="projection delete count",
    )
    comparable = tuple(
        column for column in request.projected_columns if column not in request.business_key
    )
    difference = (
        " OR ".join(
            f"NOT (t.{_q(column)} <=> s.{_q(column)})" for column in comparable
        )
        or "false"
    )
    updates = _count(
        spark,
        f"SELECT COUNT(*) FROM {_q(views.before)} t JOIN {_q(views.stage)} s ON {matched} "
        f"WHERE s.{_q('__fdf_present')} = true AND ({difference}) "
        "/* fdf:update_count */",
        label="projection update count",
    )
    return MutationCounts(inserted=inserts, updated=updates, deleted=deletes)


def _merge_sql(request: SparkDeltaProjectionRequest, views: _ProjectionViews) -> str:
    target_sql = quote_spark_relation(request.target_table)
    update_columns = tuple(
        column for column in request.projected_columns if column not in request.business_key
    )
    update_clause = ", ".join(
        f"t.{_q(column)} = s.{_q(column)}" for column in update_columns
    )
    insert_columns = ", ".join(_q(column) for column in request.projected_columns)
    insert_values = ", ".join(f"s.{_q(column)}" for column in request.projected_columns)
    sql = (
        f"MERGE INTO {target_sql} t USING {_q(views.stage)} s "
        f"ON {_join('t', 's', request.business_key)} "
        f"WHEN MATCHED AND s.{_q('__fdf_present')} = false THEN DELETE "
    )
    if update_clause:
        sql += (
            f"WHEN MATCHED AND s.{_q('__fdf_present')} = true "
            f"THEN UPDATE SET {update_clause} "
        )
    sql += (
        f"WHEN NOT MATCHED AND s.{_q('__fdf_present')} = true THEN "
        f"INSERT ({insert_columns}) VALUES ({insert_values})"
    )
    return sql + " /* fdf:merge */"


def _verification_sql(
    request: SparkDeltaProjectionRequest,
    views: _ProjectionViews,
) -> tuple[str, str]:
    target_sql = quote_spark_relation(request.target_table)
    projected = ", ".join(_q(column) for column in request.projected_columns)
    expected = (
        f"SELECT {projected} FROM {_q(views.stage)} WHERE {_q('__fdf_present')} = true"
    )
    actual = (
        f"SELECT {_projected_select('t', request.projected_columns)} FROM {target_sql} t "
        f"JOIN {_q(views.keys)} k ON {_join('t', 'k', request.business_key)}"
    )
    extra = (
        "SELECT 1 FROM (" + actual + " EXCEPT ALL " + expected
        + ") fdf_extra LIMIT 1 /* fdf:verify_extra */"
    )
    missing = (
        "SELECT 1 FROM (" + expected + " EXCEPT ALL " + actual
        + ") fdf_missing LIMIT 1 /* fdf:verify_missing */"
    )
    return extra, missing


def _mutate_incremental_target(
    spark: SparkSessionLike,
    request: SparkDeltaProjectionRequest,
    window: _ProjectionVersionWindow,
    views: _ProjectionViews,
    *,
    affected_keys: int,
) -> _ProjectionMutationOutcome:
    if _has_rows(spark, _history_duplicate_sql(request, views, window)):
        raise CurrentProjectionExecutionError(
            "authoritative SCD2 history has more than one current row for an affected key"
        )
    spark.sql(_stage_sql(request, views, window))
    spark.sql(_before_sql(request, views))
    if _has_rows(spark, _target_duplicate_sql(request, views)):
        raise CurrentProjectionExecutionError(
            "current projection target contains duplicate business keys"
        )
    mutations = _mutation_counts(spark, request, views)
    spark.sql(_merge_sql(request, views))
    extra_sql, missing_sql = _verification_sql(request, views)
    if _has_rows(spark, extra_sql) or _has_rows(spark, missing_sql):
        raise CurrentProjectionExecutionError(
            "current projection target does not equal authoritative current history for affected keys"
        )
    return _ProjectionMutationOutcome(affected_keys=affected_keys, mutations=mutations)


def _reconcile_and_commit(
    engine: Engine,
    request: SparkDeltaProjectionRequest,
    window: _ProjectionVersionWindow,
    outcome: _ProjectionMutationOutcome,
    reconcile: SparkProjectionReconciliation | None,
) -> CurrentProjectionExecutionResult:
    evidence = SparkCurrentProjectionEvidence(
        dataset_id=request.dataset_id,
        lower_version=window.lower_version,
        upper_version=window.upper_version,
        affected_keys=outcome.affected_keys,
        mutations=outcome.mutations,
        rebuilt=outcome.rebuilt,
    )
    passed = True if reconcile is None else bool(reconcile(evidence))
    next_state = _commit_projection_checkpoint(
        engine,
        request,
        window,
        reconciliation_passed=passed,
    )
    return CurrentProjectionExecutionResult(
        dataset_id=request.dataset_id,
        lower_processed_version=window.lower_version,
        upper_processed_version=window.upper_version,
        affected_keys=outcome.affected_keys,
        mutations=outcome.mutations,
        checkpoint_version=next_state.version,
    )


def _rebuild_duplicate_sql(
    request: SparkDeltaProjectionRequest,
    window: _ProjectionVersionWindow,
) -> str:
    history_sql = quote_spark_relation(request.history_table)
    grouped = ", ".join(f"h.{_q(key)}" for key in request.business_key)
    return (
        f"SELECT 1 FROM {history_sql} VERSION AS OF {window.upper_version} h "
        f"WHERE h.{_q(request.current_flag_column)} = true GROUP BY {grouped} "
        "HAVING COUNT(*) > 1 LIMIT 1 /* fdf:rebuild_duplicate_current */"
    )


def _rebuild_sql(
    request: SparkDeltaProjectionRequest,
    window: _ProjectionVersionWindow,
) -> str:
    history_sql = quote_spark_relation(request.history_table)
    target_sql = quote_spark_relation(request.target_table)
    projected = ", ".join(_q(column) for column in request.projected_columns)
    return (
        f"CREATE OR REPLACE TABLE {target_sql} USING DELTA AS "
        f"SELECT {projected} FROM {history_sql} VERSION AS OF {window.upper_version} "
        f"WHERE {_q(request.current_flag_column)} = true /* fdf:rebuild */"
    )


class FabricSparkDeltaCurrentProjectionRuntime:
    """Thin provider coordinator for distributed Delta current projections."""

    def __init__(self, spark: SparkSessionLike) -> None:
        self.spark = spark

    def latest_history_version(self, table_reference: str) -> int:
        return _latest_history_version(self.spark, table_reference)

    def execute_incremental(  # noqa: PLR0913 - stable provider runtime façade
        self,
        *,
        control_plane_engine: Engine,
        dataset_id: str,
        dataset_run_id: UUID,
        history_table: str,
        target_table: str,
        business_key: tuple[str, ...],
        projected_columns: tuple[str, ...],
        current_flag_column: str = "_framework_is_current",
        requested_upper_version: int | None = None,
        reconciliation_required: bool = True,
        reconcile: SparkProjectionReconciliation | None = None,
    ) -> CurrentProjectionExecutionResult:
        request = SparkDeltaProjectionRequest(
            dataset_id=dataset_id,
            dataset_run_id=dataset_run_id,
            history_table=history_table,
            target_table=target_table,
            business_key=business_key,
            projected_columns=projected_columns,
            current_flag_column=current_flag_column,
            requested_upper_version=requested_upper_version,
            reconciliation_required=reconciliation_required,
        )
        return self._execute_incremental(control_plane_engine, request, reconcile)

    def _execute_incremental(
        self,
        engine: Engine,
        request: SparkDeltaProjectionRequest,
        reconcile: SparkProjectionReconciliation | None,
    ) -> CurrentProjectionExecutionResult:
        _validate_request(request, reconcile)
        if not self.spark.catalog.tableExists(request.target_table):
            raise CurrentProjectionExecutionError(
                "incremental current projection target does not exist; run full rebuild first"
            )
        with _projection_lease(engine, request):
            window = _resolve_version_window(self.spark, engine, request, rebuild=False)
            assert window.lower_version is not None
            if window.upper_version == window.lower_version:
                assert window.checkpoint_state is not None
                return CurrentProjectionExecutionResult(
                    dataset_id=request.dataset_id,
                    lower_processed_version=window.lower_version,
                    upper_processed_version=window.upper_version,
                    affected_keys=0,
                    mutations=MutationCounts(),
                    checkpoint_version=window.checkpoint_state.version,
                    no_work=True,
                )
            views = _new_views()
            affected = _load_affected_keys(self.spark, request, window, views)
            if affected == 0:
                outcome = _ProjectionMutationOutcome(0, MutationCounts())
            else:
                outcome = _mutate_incremental_target(
                    self.spark,
                    request,
                    window,
                    views,
                    affected_keys=affected,
                )
            return _reconcile_and_commit(engine, request, window, outcome, reconcile)

    def rebuild(  # noqa: PLR0913 - stable provider runtime façade
        self,
        *,
        control_plane_engine: Engine,
        dataset_id: str,
        dataset_run_id: UUID,
        history_table: str,
        target_table: str,
        business_key: tuple[str, ...],
        projected_columns: tuple[str, ...],
        current_flag_column: str = "_framework_is_current",
        requested_upper_version: int | None = None,
        reconciliation_required: bool = True,
        reconcile: SparkProjectionReconciliation | None = None,
    ) -> CurrentProjectionExecutionResult:
        request = SparkDeltaProjectionRequest(
            dataset_id=dataset_id,
            dataset_run_id=dataset_run_id,
            history_table=history_table,
            target_table=target_table,
            business_key=business_key,
            projected_columns=projected_columns,
            current_flag_column=current_flag_column,
            requested_upper_version=requested_upper_version,
            reconciliation_required=reconciliation_required,
        )
        return self._rebuild(control_plane_engine, request, reconcile)

    def _rebuild(
        self,
        engine: Engine,
        request: SparkDeltaProjectionRequest,
        reconcile: SparkProjectionReconciliation | None,
    ) -> CurrentProjectionExecutionResult:
        _validate_request(request, reconcile)
        with _projection_lease(engine, request):
            window = _resolve_version_window(self.spark, engine, request, rebuild=True)
            if _has_rows(self.spark, _rebuild_duplicate_sql(request, window)):
                raise CurrentProjectionExecutionError(
                    "authoritative SCD2 history has more than one current row per business key"
                )
            self.spark.sql(_rebuild_sql(request, window))
            target_sql = quote_spark_relation(request.target_table)
            row_count = _count(
                self.spark,
                f"SELECT COUNT(*) FROM {target_sql} /* fdf:rebuild_count */",
                label="rebuilt current row count",
            )
            outcome = _ProjectionMutationOutcome(
                affected_keys=row_count,
                mutations=MutationCounts(inserted=row_count),
                rebuilt=True,
            )
            return _reconcile_and_commit(
                engine,
                request,
                window,
                outcome,
                reconcile,
            )


__all__ = [
    "FabricSparkDeltaCurrentProjectionRuntime",
    "SparkCurrentProjectionEvidence",
    "SparkDeltaProjectionRequest",
    "SparkProjectionReconciliation",
    "SparkSessionLike",
]
