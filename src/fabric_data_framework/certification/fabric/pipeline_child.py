"""Framework-owned physical executor for certification Pipeline child runs.

The generic ``execution.pipeline_child`` contract remains the sole owner of terminal
``DatasetRunAudit`` persistence. This module owns only bounded certification data-plane
mutation. Table identities and failure modes are fixed in source; provider completion
is never interpreted here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection

from fabric_data_framework.apply.replace import ReplaceGuardPolicy, plan_replace
from fabric_data_framework.apply.scd1 import apply_scd1
from fabric_data_framework.apply.scd2 import (
    IS_CURRENT,
    RECORD_HASH,
    SOURCE_DATASET_RUN_ID,
    VALID_FROM,
    VALID_TO,
    apply_scd2,
)
from fabric_data_framework.capture.full import FullSnapshotEvidence
from fabric_data_framework.contracts.audit import RowAccounting
from fabric_data_framework.contracts.reconciliation import (
    ReconciliationMetric,
    ReconciliationResult,
    ReconciliationStatus,
)
from fabric_data_framework.control_plane.repository import ControlPlaneRepository
from fabric_data_framework.data_plane.staging import stage_rows
from fabric_data_framework.execution.pipeline_child import (
    FabricPipelineChildRequest,
    FabricPipelineChildResult,
)
from fabric_data_framework.metadata.config import ApplyStrategy, DatasetConfig, DatasetStatus
from fabric_data_framework.quality.reconciliation.full_replace import reconcile_full_replace
from fabric_data_framework.quality.reconciliation import reconcile_scd2_batch
from fabric_data_framework.quality.reconciliation.engine import evaluate_reconciliation_policy


_SUCCESS = "SUCCESS"
_RETRYABLE_FAILURE = "CERTIFICATION_RETRYABLE_FAILURE"
_RECONCILIATION_FAILURE = "RECONCILIATION_FAILED"
_ALLOWED_FAILURE_MODES = frozenset({_SUCCESS, _RETRYABLE_FAILURE, _RECONCILIATION_FAILURE})
_PUBLISHED = "published"


@dataclass(frozen=True)
class _DatasetTables:
    source: str
    target: str
    history: str | None = None


_TABLES: dict[str, _DatasetTables] = {
    "cert.full_replace": _DatasetTables("dbo.cert_full_source", "dbo.cert_full_target"),
    "cert.watermark_scd1": _DatasetTables("dbo.cert_scd1_source", "dbo.cert_scd1_target"),
    "cert.watermark_scd2": _DatasetTables(
        "dbo.cert_scd2_source", "dbo.cert_scd2_current", "dbo.cert_scd2_history"
    ),
    "cert.retry_idempotency": _DatasetTables("dbo.cert_retry_source", "dbo.cert_retry_target"),
    "cert.reconciliation_fail_closed": _DatasetTables(
        "dbo.cert_recon_source", "dbo.cert_recon_target"
    ),
}


def _quote_table(value: str) -> str:
    parts = value.split(".")
    if len(parts) != 2 or any(not part.replace("_", "").isalnum() for part in parts):
        raise ValueError(f"unsafe certification table identity: {value!r}")
    return ".".join(f"[{part}]" for part in parts)


def _quote_column(value: str) -> str:
    if not value or not value.replace("_", "").isalnum():
        raise ValueError(f"unsafe certification column identity: {value!r}")
    return f"[{value}]"


def _select_rows(
    connection: Connection,
    table: str,
    columns: tuple[str, ...],
) -> list[dict[str, Any]]:
    selected = ", ".join(_quote_column(column) for column in columns)
    result = connection.execute(text(f"SELECT {selected} FROM {_quote_table(table)}"))
    return [dict(row) for row in result.mappings().all()]


def _replace_rows(
    connection: Connection,
    table: str,
    columns: tuple[str, ...],
    rows: list[Mapping[str, Any]],
) -> None:
    quoted_table = _quote_table(table)
    connection.execute(text(f"DELETE FROM {quoted_table}"))
    if not rows:
        return
    selected = ", ".join(_quote_column(column) for column in columns)
    parameters = ", ".join(f":p{index}" for index in range(len(columns)))
    statement = text(f"INSERT INTO {quoted_table} ({selected}) VALUES ({parameters})")
    for row in rows:
        connection.execute(
            statement,
            {f"p{index}": row[column] for index, column in enumerate(columns)},
        )


def _replace_progress(connection: Connection, dataset_id: str, checkpoint: str) -> None:
    connection.execute(
        text("DELETE FROM [dbo].[cert_progress] WHERE [dataset_id] = :dataset_id"),
        {"dataset_id": dataset_id},
    )
    connection.execute(
        text(
            "INSERT INTO [dbo].[cert_progress] ([dataset_id], [checkpoint]) "
            "VALUES (:dataset_id, :checkpoint)"
        ),
        {"dataset_id": dataset_id, "checkpoint": checkpoint},
    )


def _progress_checkpoint(connection: Connection, dataset_id: str) -> str | None:
    row = connection.execute(
        text(
            "SELECT [checkpoint] FROM [dbo].[cert_progress] "
            "WHERE [dataset_id] = :dataset_id"
        ),
        {"dataset_id": dataset_id},
    ).mappings().first()
    return None if row is None or row["checkpoint"] is None else str(row["checkpoint"])


def _failure_mode(connection: Connection, dataset_id: str) -> str:
    rows = connection.execute(
        text(
            "SELECT [failure_mode] FROM [dbo].[cert_pipeline_control] "
            "WHERE [dataset_id] = :dataset_id"
        ),
        {"dataset_id": dataset_id},
    ).mappings().all()
    if len(rows) != 1:
        raise RuntimeError(
            "certification Pipeline child requires exactly one control row for "
            f"{dataset_id}; observed={len(rows)}"
        )
    mode = str(rows[0]["failure_mode"]).strip()
    if mode not in _ALLOWED_FAILURE_MODES:
        raise RuntimeError(f"unsupported certification failure mode {mode!r}")
    return mode


def _parse_timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        rendered = str(value)
        if rendered.endswith("Z"):
            rendered = rendered[:-1] + "+00:00"
        parsed = datetime.fromisoformat(rendered)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timestamp_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _accounting(count: int) -> RowAccounting:
    return RowAccounting(rows_read=count, rows_accepted=count)


def _retryable_failure() -> FabricPipelineChildResult:
    return FabricPipelineChildResult(
        status=DatasetStatus.FAILED,
        error_code=_RETRYABLE_FAILURE,
        error_message="bounded certification retryable failure requested",
        retryable=True,
    )


def _reconciliation_blocked(result: ReconciliationResult) -> bool:
    return result.blocks_state_advance and result.status is ReconciliationStatus.FAIL


def _record_current_state_reconciliation(
    *,
    repository: ControlPlaneRepository,
    request: FabricPipelineChildRequest,
    config: DatasetConfig,
    accounting: RowAccounting,
    target_rows: list[Mapping[str, Any]],
) -> ReconciliationResult:
    keys = [row.get("id") for row in target_rows]
    result = evaluate_reconciliation_policy(
        dataset_run_id=request.framework_dataset_run_id,
        dataset_id=request.dataset_id,
        policy=config.reconciliation,
        accounting=accounting,
        base_metrics=(
            ReconciliationMetric(
                name="unique_current_key",
                expected="true",
                actual="true" if len(keys) == len(set(keys)) else "false",
                passed=len(keys) == len(set(keys)),
            ),
        ),
    )
    repository.record_reconciliation(result)
    return result


def _execute_replace(
    *,
    connection: Connection,
    repository: ControlPlaneRepository,
    request: FabricPipelineChildRequest,
    config: DatasetConfig,
    tables: _DatasetTables,
    force_reconciliation_failure: bool,
) -> FabricPipelineChildResult:
    source = _select_rows(connection, tables.source, ("id", "value"))
    target = _select_rows(connection, tables.target, ("id", "value"))
    accounting = _accounting(len(source))
    staged = stage_rows(source, dataset_run_id=request.framework_dataset_run_id)
    evidence = FullSnapshotEvidence(
        snapshot_id=f"certification:{request.dataset_id}:{request.framework_dataset_run_id}",
        complete=True,
        source_row_count=len(source),
    )
    plan = plan_replace(target, staged, evidence=evidence, policy=ReplaceGuardPolicy())
    reconciliation = reconcile_full_replace(
        dataset_run_id=request.framework_dataset_run_id,
        dataset_id=request.dataset_id,
        policy=config.reconciliation,
        accounting=accounting,
        candidate_row_count=plan.candidate_count,
        evidence=evidence,
        force_fail=force_reconciliation_failure,
    )
    repository.record_reconciliation(reconciliation)
    if _reconciliation_blocked(reconciliation):
        return FabricPipelineChildResult(
            status=DatasetStatus.FAILED,
            row_accounting=accounting,
            error_code=_RECONCILIATION_FAILURE,
            error_message="required certification reconciliation gate failed",
            retryable=False,
        )
    _replace_rows(connection, tables.target, ("id", "value"), list(plan.rows))
    _replace_progress(connection, request.dataset_id, _PUBLISHED)
    return FabricPipelineChildResult(
        status=DatasetStatus.SUCCEEDED,
        row_accounting=accounting,
        mutations=plan.mutations,
    )


def _watermark_source(
    connection: Connection,
    *,
    dataset_id: str,
    source_table: str,
) -> tuple[list[dict[str, Any]], datetime]:
    checkpoint = _progress_checkpoint(connection, dataset_id)
    if checkpoint is None:
        raise RuntimeError(f"certification watermark checkpoint is missing for {dataset_id}")
    lower = _parse_timestamp(checkpoint)
    source = _select_rows(connection, source_table, ("id", "value", "modified_at"))
    normalized = []
    for row in source:
        modified_at = _parse_timestamp(row["modified_at"])
        if modified_at > lower:
            normalized.append(
                {"id": row["id"], "value": row["value"], "modified_at": modified_at}
            )
    normalized.sort(key=lambda row: (row["modified_at"], row["id"]))
    upper = max((row["modified_at"] for row in normalized), default=lower)
    return normalized, upper


def _execute_scd1(
    *,
    connection: Connection,
    repository: ControlPlaneRepository,
    request: FabricPipelineChildRequest,
    config: DatasetConfig,
    tables: _DatasetTables,
) -> FabricPipelineChildResult:
    checkpoint = _progress_checkpoint(connection, request.dataset_id)
    if checkpoint is None:
        raise RuntimeError("certification SCD1 baseline checkpoint is missing")
    lower = _parse_timestamp(checkpoint)
    source, upper = _watermark_source(
        connection,
        dataset_id=request.dataset_id,
        source_table=tables.source,
    )
    accounting = _accounting(len(source))
    current = _select_rows(connection, tables.target, ("id", "value"))
    if not source:
        reconciliation = _record_current_state_reconciliation(
            repository=repository,
            request=request,
            config=config,
            accounting=accounting,
            target_rows=current,
        )
        if _reconciliation_blocked(reconciliation):
            return FabricPipelineChildResult(
                status=DatasetStatus.FAILED,
                row_accounting=accounting,
                error_code=_RECONCILIATION_FAILURE,
                retryable=False,
            )
        return FabricPipelineChildResult(status=DatasetStatus.SUCCEEDED, row_accounting=accounting)

    enriched_current = [
        {"id": row["id"], "value": row["value"], "modified_at": lower}
        for row in current
    ]
    watermark = config.load.watermark
    if watermark is None:
        raise RuntimeError("certification SCD1 requires watermark configuration")
    applied = apply_scd1(
        enriched_current,
        source,
        merge_key=config.load.merge_key,
        ordering_columns=(watermark.column,),
    )
    target_rows = [{"id": row["id"], "value": row["value"]} for row in applied.rows]
    reconciliation = _record_current_state_reconciliation(
        repository=repository,
        request=request,
        config=config,
        accounting=accounting,
        target_rows=target_rows,
    )
    if _reconciliation_blocked(reconciliation):
        return FabricPipelineChildResult(
            status=DatasetStatus.FAILED,
            row_accounting=accounting,
            error_code=_RECONCILIATION_FAILURE,
            retryable=False,
        )
    _replace_rows(connection, tables.target, ("id", "value"), target_rows)
    _replace_progress(connection, request.dataset_id, _timestamp_text(upper))
    return FabricPipelineChildResult(
        status=DatasetStatus.SUCCEEDED,
        row_accounting=accounting,
        mutations=applied.mutations,
    )


def _execute_scd2(
    *,
    connection: Connection,
    repository: ControlPlaneRepository,
    request: FabricPipelineChildRequest,
    config: DatasetConfig,
    tables: _DatasetTables,
) -> FabricPipelineChildResult:
    if tables.history is None:
        raise RuntimeError("certification SCD2 history table is not configured")
    checkpoint = _progress_checkpoint(connection, request.dataset_id)
    if checkpoint is None:
        raise RuntimeError("certification SCD2 baseline checkpoint is missing")
    lower = _parse_timestamp(checkpoint)
    source, upper = _watermark_source(
        connection,
        dataset_id=request.dataset_id,
        source_table=tables.source,
    )
    accounting = _accounting(len(source))
    persisted_history = _select_rows(
        connection, tables.history, ("id", "value", "is_current")
    )
    if not source:
        return FabricPipelineChildResult(status=DatasetStatus.SUCCEEDED, row_accounting=accounting)

    history: list[dict[str, Any]] = []
    for row in persisted_history:
        if row["is_current"] is not True and row["is_current"] != 1:
            raise RuntimeError(
                "certification SCD2 bootstrap history may contain only current baseline rows"
            )
        history.append(
            {
                "id": row["id"],
                "value": row["value"],
                VALID_FROM: lower,
                VALID_TO: None,
                IS_CURRENT: True,
                RECORD_HASH: None,
                SOURCE_DATASET_RUN_ID: "certification-baseline",
            }
        )
    watermark = config.load.watermark
    if watermark is None:
        raise RuntimeError("certification SCD2 requires watermark configuration")
    applied = apply_scd2(
        history,
        source,
        business_key=config.load.business_key,
        tracked_columns=config.load.tracked_columns,
        effective_time_column=watermark.column,
        dataset_run_id=request.framework_dataset_run_id,
    )
    reconciliation = reconcile_scd2_batch(
        dataset_run_id=request.framework_dataset_run_id,
        dataset_id=request.dataset_id,
        policy=config.reconciliation,
        accounting=accounting,
        proposed_rows=applied.rows,
        business_key=config.load.business_key,
    )
    repository.record_reconciliation(reconciliation)
    if _reconciliation_blocked(reconciliation):
        return FabricPipelineChildResult(
            status=DatasetStatus.FAILED,
            row_accounting=accounting,
            error_code=_RECONCILIATION_FAILURE,
            retryable=False,
        )

    current_rows = [
        {"id": row["id"], "value": row["value"]}
        for row in applied.rows
        if row[IS_CURRENT] is True
    ]
    history_rows = [
        {"id": row["id"], "value": row["value"], "is_current": row[IS_CURRENT]}
        for row in applied.rows
    ]
    _replace_rows(connection, tables.target, ("id", "value"), current_rows)
    _replace_rows(connection, tables.history, ("id", "value", "is_current"), history_rows)
    _replace_progress(connection, request.dataset_id, _timestamp_text(upper))
    return FabricPipelineChildResult(
        status=DatasetStatus.SUCCEEDED,
        row_accounting=accounting,
        mutations=applied.mutations,
    )


class CertificationPipelineChildExecutor:
    """Execute only source-controlled framework certification datasets in Warehouse."""

    def __init__(self, warehouse_engine: Engine) -> None:
        self._warehouse_engine = warehouse_engine

    def __call__(
        self,
        request: FabricPipelineChildRequest,
        config: DatasetConfig,
        repository: ControlPlaneRepository,
    ) -> FabricPipelineChildResult:
        tables = _TABLES.get(request.dataset_id)
        if tables is None:
            raise ValueError(
                f"dataset {request.dataset_id!r} is not a framework certification child dataset"
            )
        if config.dataset_id != request.dataset_id:
            raise ValueError("certification Pipeline child config/request dataset mismatch")

        with self._warehouse_engine.begin() as connection:
            mode = _failure_mode(connection, request.dataset_id)
            if mode == _RETRYABLE_FAILURE:
                return _retryable_failure()
            if config.load.apply_strategy is ApplyStrategy.REPLACE:
                return _execute_replace(
                    connection=connection,
                    repository=repository,
                    request=request,
                    config=config,
                    tables=tables,
                    force_reconciliation_failure=mode == _RECONCILIATION_FAILURE,
                )
            if mode != _SUCCESS:
                raise RuntimeError(
                    f"failure mode {mode!r} is not valid for {config.load.apply_strategy.value}"
                )
            if config.load.apply_strategy is ApplyStrategy.SCD1:
                return _execute_scd1(
                    connection=connection,
                    repository=repository,
                    request=request,
                    config=config,
                    tables=tables,
                )
            if config.load.apply_strategy is ApplyStrategy.SCD2:
                return _execute_scd2(
                    connection=connection,
                    repository=repository,
                    request=request,
                    config=config,
                    tables=tables,
                )
            raise ValueError(
                "framework certification Pipeline child supports only REPLACE, SCD1 and SCD2"
            )


__all__ = ["CertificationPipelineChildExecutor"]
