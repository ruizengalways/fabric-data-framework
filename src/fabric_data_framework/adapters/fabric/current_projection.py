"""Production Spark/Delta physicalization for authoritative-history current projections.

The implementation is intentionally Spark-SQL/DataFrame-reader based without importing
``pyspark`` at module import time, so the wheel remains importable outside Fabric.  The
runtime never interprets history CDF rows as current-state events: CDF identifies affected
business keys, then authoritative history is read exactly at the frozen upper version.
"""

from __future__ import annotations

from builtins import BaseExceptionGroup
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol
from uuid import UUID, uuid4

from sqlalchemy import Engine

from fabric_data_framework.capture.cdc import build_cdc_checkpoint
from fabric_data_framework.contracts.audit import MutationCounts
from fabric_data_framework.contracts.current_projection import (
    current_projection_checkpoint_partition,
)
from fabric_data_framework.contracts.runtime import StateCommitGate
from fabric_data_framework.control_plane.dataset_lease import (
    DatasetLeaseConflict,
    acquire_dataset_lease,
    release_dataset_lease,
)
from fabric_data_framework.control_plane.io import (
    CDCCheckpointState,
    commit_cdc_checkpoint,
    read_cdc_checkpoint,
)
from fabric_data_framework.deployment.current_projection import quote_spark_relation
from fabric_data_framework.execution.current_projection import (
    CurrentProjectionExecutionError,
    CurrentProjectionExecutionResult,
)


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
class SparkCurrentProjectionEvidence:
    dataset_id: str
    lower_version: int | None
    upper_version: int
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
    table_reference: str,
    business_key: tuple[str, ...],
    projected_columns: tuple[str, ...],
    current_flag_column: str,
) -> int | None:
    if state is None:
        return None
    partition = current_projection_checkpoint_partition(
        table_reference=table_reference,
        business_key=business_key,
        projected_columns=projected_columns,
        current_flag_column=current_flag_column,
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


def _commit_projection_checkpoint(
    *,
    engine: Engine,
    dataset_id: str,
    dataset_run_id: UUID,
    table_reference: str,
    business_key: tuple[str, ...],
    projected_columns: tuple[str, ...],
    current_flag_column: str,
    upper_version: int,
    checkpoint_state: CDCCheckpointState | None,
    reconciliation_required: bool,
    reconciliation_passed: bool,
) -> CDCCheckpointState:
    gate = StateCommitGate(
        target_committed=True,
        reconciliation_required=reconciliation_required,
        reconciliation_passed=reconciliation_passed,
    )
    if not gate.can_advance_state:
        raise CurrentProjectionExecutionError(
            "current projection reconciliation failed; checkpoint was not advanced"
        )
    return commit_cdc_checkpoint(
        engine,
        dataset_id=dataset_id,
        checkpoint=build_cdc_checkpoint(
            {
                current_projection_checkpoint_partition(
                    table_reference=table_reference,
                    business_key=business_key,
                    projected_columns=projected_columns,
                    current_flag_column=current_flag_column,
                ): (upper_version,)
            }
        ),
        dataset_run_id=dataset_run_id,
        expected_version=checkpoint_state.version if checkpoint_state is not None else 0,
        gate=gate,
    )


class FabricSparkDeltaCurrentProjectionRuntime:
    """Distributed Mode-3 executor using Fabric Spark and Delta CDF/time travel."""

    def __init__(self, spark: SparkSessionLike) -> None:
        self.spark = spark

    def latest_history_version(self, table_reference: str) -> int:
        relation = quote_spark_relation(table_reference)
        value = _first_scalar(
            self.spark.sql(
                f"SELECT version FROM (DESCRIBE HISTORY {relation}) ORDER BY version DESC LIMIT 1"
            ),
            label="Delta history version",
        )
        try:
            version = int(value)
        except (TypeError, ValueError) as exc:
            raise CurrentProjectionExecutionError(
                f"invalid Delta history version: {value!r}"
            ) from exc
        if version < 0:
            raise CurrentProjectionExecutionError("Delta history version cannot be negative")
        return version

    def _acquire(self, engine: Engine, dataset_id: str, dataset_run_id: UUID):
        try:
            return acquire_dataset_lease(
                engine,
                dataset_id=dataset_id,
                lease_owner=f"fabric-spark-current-projection:{uuid4()}",
                dataset_run_id=dataset_run_id,
                review_deadline=datetime.now(timezone.utc) + timedelta(days=1),
            )
        except DatasetLeaseConflict as exc:
            raise CurrentProjectionExecutionError(
                "current projection mutation is already claimed by another dataset run"
            ) from exc

    def _release(self, engine: Engine, lease, execution_error: BaseException | None = None) -> None:
        try:
            release_dataset_lease(engine, lease)
        except BaseException as release_error:
            if execution_error is not None:
                raise BaseExceptionGroup(
                    "current projection execution and lease release both failed",
                    (execution_error, release_error),
                ) from execution_error
            raise CurrentProjectionExecutionError(
                "current projection completed but its durable dataset lease could not be released"
            ) from release_error

    def execute_incremental(
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
        if not business_key or not projected_columns:
            raise ValueError("business_key and projected_columns are required")
        if not set(business_key).issubset(projected_columns):
            raise ValueError("projected_columns must include every business key column")
        if reconciliation_required and reconcile is None:
            raise CurrentProjectionExecutionError(
                "required Spark current-projection reconciliation callback is missing"
            )
        if not self.spark.catalog.tableExists(target_table):
            raise CurrentProjectionExecutionError(
                "incremental current projection target does not exist; run full rebuild first"
            )

        lease = self._acquire(control_plane_engine, dataset_id, dataset_run_id)
        execution_error: BaseException | None = None
        try:
            checkpoint_state = read_cdc_checkpoint(control_plane_engine, dataset_id)
            if checkpoint_state is None:
                raise CurrentProjectionExecutionError(
                    "current projection is uninitialized; run full rebuild before incremental execution"
                )
            lower = _processed_version(
                checkpoint_state,
                table_reference=history_table,
                business_key=business_key,
                projected_columns=projected_columns,
                current_flag_column=current_flag_column,
            )
            assert lower is not None
            latest = self.latest_history_version(history_table)
            upper = latest if requested_upper_version is None else requested_upper_version
            if upper > latest:
                raise CurrentProjectionExecutionError(
                    "requested projection upper version is ahead of authoritative history"
                )
            if upper < lower:
                raise CurrentProjectionExecutionError(
                    "current projection cannot rewind committed history progress"
                )
            if upper == lower:
                return CurrentProjectionExecutionResult(
                    dataset_id=dataset_id,
                    lower_processed_version=lower,
                    upper_processed_version=upper,
                    affected_keys=0,
                    mutations=MutationCounts(),
                    checkpoint_version=checkpoint_state.version,
                    no_work=True,
                )

            start = lower + 1
            token = uuid4().hex
            cdf_view = f"_fdf_cdf_{token}"
            key_view = f"_fdf_keys_{token}"
            stage_view = f"_fdf_stage_{token}"
            before_view = f"_fdf_before_{token}"
            history_sql = quote_spark_relation(history_table)
            target_sql = quote_spark_relation(target_table)
            key_sql = ", ".join(_q(key) for key in business_key)
            try:
                cdf = (
                    self.spark.read.format("delta")
                    .option("readChangeFeed", "true")
                    .option("startingVersion", start)
                    .option("endingVersion", upper)
                    .table(history_table)
                )
                cdf.createOrReplaceTempView(cdf_view)
            except Exception as exc:
                raise CurrentProjectionExecutionError(
                    "authoritative history CDF range is unavailable; explicit rebuild is required"
                ) from exc

            null_predicate = " OR ".join(f"{_q(key)} IS NULL" for key in business_key)
            if _has_rows(
                self.spark,
                f"SELECT 1 FROM {_q(cdf_view)} WHERE {null_predicate} LIMIT 1",
            ):
                raise CurrentProjectionExecutionError(
                    "history CDF contains a row with an incomplete business key"
                )
            self.spark.sql(
                f"CREATE OR REPLACE TEMP VIEW {_q(key_view)} AS "
                f"SELECT DISTINCT {key_sql} FROM {_q(cdf_view)}"
            )
            affected = _count(
                self.spark,
                f"SELECT COUNT(*) FROM {_q(key_view)} /* fdf:affected_count */",
                label="affected-key count",
            )

            if affected == 0:
                evidence = SparkCurrentProjectionEvidence(
                    dataset_id=dataset_id,
                    lower_version=lower,
                    upper_version=upper,
                    affected_keys=0,
                    mutations=MutationCounts(),
                )
                passed = True if reconcile is None else bool(reconcile(evidence))
                next_state = _commit_projection_checkpoint(
                    engine=control_plane_engine,
                    dataset_id=dataset_id,
                    dataset_run_id=dataset_run_id,
                    table_reference=history_table,
                    business_key=business_key,
                    projected_columns=projected_columns,
                    current_flag_column=current_flag_column,
                    upper_version=upper,
                    checkpoint_state=checkpoint_state,
                    reconciliation_required=reconciliation_required,
                    reconciliation_passed=passed,
                )
                return CurrentProjectionExecutionResult(
                    dataset_id=dataset_id,
                    lower_processed_version=lower,
                    upper_processed_version=upper,
                    affected_keys=0,
                    mutations=MutationCounts(),
                    checkpoint_version=next_state.version,
                )

            key_join = _join("h", "k", business_key)
            if _has_rows(
                self.spark,
                f"SELECT 1 FROM {history_sql} VERSION AS OF {upper} h "
                f"JOIN {_q(key_view)} k ON {key_join} "
                f"WHERE h.{_q(current_flag_column)} = true "
                f"GROUP BY {', '.join(f'k.{_q(key)}' for key in business_key)} "
                "HAVING COUNT(*) > 1 LIMIT 1 /* fdf:history_duplicate_current */",
            ):
                raise CurrentProjectionExecutionError(
                    "authoritative SCD2 history has more than one current row for an affected key"
                )

            select_items = []
            for column in projected_columns:
                source_alias = "k" if column in business_key else "h"
                select_items.append(f"{source_alias}.{_q(column)} AS {_q(column)}")
            present_expr = f"h.{_q(business_key[0])} IS NOT NULL AS {_q('__fdf_present')}"
            self.spark.sql(
                f"CREATE OR REPLACE TEMP VIEW {_q(stage_view)} AS SELECT "
                + ", ".join(select_items + [present_expr])
                + f" FROM {_q(key_view)} k LEFT JOIN {history_sql} VERSION AS OF {upper} h "
                + f"ON {key_join} AND h.{_q(current_flag_column)} = true"
            )
            self.spark.sql(
                f"CREATE OR REPLACE TEMP VIEW {_q(before_view)} AS SELECT t.* FROM {target_sql} t "
                f"JOIN {_q(key_view)} k ON {_join('t', 'k', business_key)}"
            )
            if _has_rows(
                self.spark,
                f"SELECT 1 FROM {_q(before_view)} t GROUP BY "
                + ", ".join(f"t.{_q(key)}" for key in business_key)
                + " HAVING COUNT(*) > 1 LIMIT 1 /* fdf:target_duplicate_key */",
            ):
                raise CurrentProjectionExecutionError(
                    "current projection target contains duplicate business keys"
                )

            matched = _join("s", "t", business_key)
            first_key = _q(business_key[0])
            inserts = _count(
                self.spark,
                f"SELECT COUNT(*) FROM {_q(stage_view)} s LEFT JOIN {_q(before_view)} t ON {matched} "
                f"WHERE s.{_q('__fdf_present')} = true AND t.{first_key} IS NULL "
                "/* fdf:insert_count */",
                label="projection insert count",
            )
            deletes = _count(
                self.spark,
                f"SELECT COUNT(*) FROM {_q(before_view)} t JOIN {_q(stage_view)} s ON {matched} "
                f"WHERE s.{_q('__fdf_present')} = false /* fdf:delete_count */",
                label="projection delete count",
            )
            comparable = tuple(column for column in projected_columns if column not in business_key)
            difference = (
                " OR ".join(
                    f"NOT (t.{_q(column)} <=> s.{_q(column)})" for column in comparable
                )
                or "false"
            )
            updates = _count(
                self.spark,
                f"SELECT COUNT(*) FROM {_q(before_view)} t JOIN {_q(stage_view)} s ON {matched} "
                f"WHERE s.{_q('__fdf_present')} = true AND ({difference}) "
                "/* fdf:update_count */",
                label="projection update count",
            )
            mutations = MutationCounts(inserted=inserts, updated=updates, deleted=deletes)

            update_columns = tuple(column for column in projected_columns if column not in business_key)
            update_clause = ", ".join(
                f"t.{_q(column)} = s.{_q(column)}" for column in update_columns
            )
            insert_columns = ", ".join(_q(column) for column in projected_columns)
            insert_values = ", ".join(f"s.{_q(column)}" for column in projected_columns)
            merge_sql = (
                f"MERGE INTO {target_sql} t USING {_q(stage_view)} s ON {_join('t', 's', business_key)} "
                f"WHEN MATCHED AND s.{_q('__fdf_present')} = false THEN DELETE "
            )
            if update_clause:
                merge_sql += (
                    f"WHEN MATCHED AND s.{_q('__fdf_present')} = true THEN UPDATE SET {update_clause} "
                )
            merge_sql += (
                f"WHEN NOT MATCHED AND s.{_q('__fdf_present')} = true THEN "
                f"INSERT ({insert_columns}) VALUES ({insert_values})"
            )
            self.spark.sql(merge_sql + " /* fdf:merge */")

            projected = ", ".join(_q(column) for column in projected_columns)
            expected_sql = (
                f"SELECT {projected} FROM {_q(stage_view)} WHERE {_q('__fdf_present')} = true"
            )
            actual_sql = (
                f"SELECT {_projected_select('t', projected_columns)} FROM {target_sql} t "
                f"JOIN {_q(key_view)} k ON {_join('t', 'k', business_key)}"
            )
            if _has_rows(
                self.spark,
                "SELECT 1 FROM (("
                + actual_sql
                + ") EXCEPT ALL ("
                + expected_sql
                + ")) UNION ALL (("
                + expected_sql
                + ") EXCEPT ALL ("
                + actual_sql
                + ")) LIMIT 1 /* fdf:verify */",
            ):
                raise CurrentProjectionExecutionError(
                    "current projection target does not equal authoritative current history for affected keys"
                )

            evidence = SparkCurrentProjectionEvidence(
                dataset_id=dataset_id,
                lower_version=lower,
                upper_version=upper,
                affected_keys=affected,
                mutations=mutations,
            )
            passed = True if reconcile is None else bool(reconcile(evidence))
            next_state = _commit_projection_checkpoint(
                engine=control_plane_engine,
                dataset_id=dataset_id,
                dataset_run_id=dataset_run_id,
                table_reference=history_table,
                business_key=business_key,
                projected_columns=projected_columns,
                current_flag_column=current_flag_column,
                upper_version=upper,
                checkpoint_state=checkpoint_state,
                reconciliation_required=reconciliation_required,
                reconciliation_passed=passed,
            )
            return CurrentProjectionExecutionResult(
                dataset_id=dataset_id,
                lower_processed_version=lower,
                upper_processed_version=upper,
                affected_keys=affected,
                mutations=mutations,
                checkpoint_version=next_state.version,
            )
        except BaseException as exc:
            execution_error = exc
            raise
        finally:
            self._release(control_plane_engine, lease, execution_error)

    def rebuild(
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
        if not set(business_key).issubset(projected_columns):
            raise ValueError("projected_columns must include every business key column")
        if reconciliation_required and reconcile is None:
            raise CurrentProjectionExecutionError(
                "required Spark current-projection reconciliation callback is missing"
            )
        lease = self._acquire(control_plane_engine, dataset_id, dataset_run_id)
        execution_error: BaseException | None = None
        try:
            checkpoint_state = read_cdc_checkpoint(control_plane_engine, dataset_id)
            lower = _processed_version(
                checkpoint_state,
                table_reference=history_table,
                business_key=business_key,
                projected_columns=projected_columns,
                current_flag_column=current_flag_column,
            )
            latest = self.latest_history_version(history_table)
            upper = latest if requested_upper_version is None else requested_upper_version
            if upper > latest:
                raise CurrentProjectionExecutionError(
                    "requested rebuild version is ahead of authoritative history"
                )
            if lower is not None and upper < lower:
                raise CurrentProjectionExecutionError(
                    "full current projection rebuild cannot rewind committed history progress"
                )
            history_sql = quote_spark_relation(history_table)
            target_sql = quote_spark_relation(target_table)
            if _has_rows(
                self.spark,
                f"SELECT 1 FROM {history_sql} VERSION AS OF {upper} h "
                f"WHERE h.{_q(current_flag_column)} = true GROUP BY "
                + ", ".join(f"h.{_q(key)}" for key in business_key)
                + " HAVING COUNT(*) > 1 LIMIT 1 /* fdf:rebuild_duplicate_current */",
            ):
                raise CurrentProjectionExecutionError(
                    "authoritative SCD2 history has more than one current row per business key"
                )
            projected = ", ".join(_q(column) for column in projected_columns)
            self.spark.sql(
                f"CREATE OR REPLACE TABLE {target_sql} USING DELTA AS "
                f"SELECT {projected} FROM {history_sql} VERSION AS OF {upper} "
                f"WHERE {_q(current_flag_column)} = true /* fdf:rebuild */"
            )
            row_count = _count(
                self.spark,
                f"SELECT COUNT(*) FROM {target_sql} /* fdf:rebuild_count */",
                label="rebuilt current row count",
            )
            mutations = MutationCounts(inserted=row_count)
            evidence = SparkCurrentProjectionEvidence(
                dataset_id=dataset_id,
                lower_version=lower,
                upper_version=upper,
                affected_keys=row_count,
                mutations=mutations,
                rebuilt=True,
            )
            passed = True if reconcile is None else bool(reconcile(evidence))
            next_state = _commit_projection_checkpoint(
                engine=control_plane_engine,
                dataset_id=dataset_id,
                dataset_run_id=dataset_run_id,
                table_reference=history_table,
                business_key=business_key,
                projected_columns=projected_columns,
                current_flag_column=current_flag_column,
                upper_version=upper,
                checkpoint_state=checkpoint_state,
                reconciliation_required=reconciliation_required,
                reconciliation_passed=passed,
            )
            return CurrentProjectionExecutionResult(
                dataset_id=dataset_id,
                lower_processed_version=lower,
                upper_processed_version=upper,
                affected_keys=row_count,
                mutations=mutations,
                checkpoint_version=next_state.version,
            )
        except BaseException as exc:
            execution_error = exc
            raise
        finally:
            self._release(control_plane_engine, lease, execution_error)


__all__ = [
    "FabricSparkDeltaCurrentProjectionRuntime",
    "SparkCurrentProjectionEvidence",
    "SparkProjectionReconciliation",
    "SparkSessionLike",
]
