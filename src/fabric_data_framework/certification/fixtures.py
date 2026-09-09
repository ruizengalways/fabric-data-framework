"""Framework-owned fixtures and observers used only by real-Fabric certification.

These callables are entry points of the framework wheel itself. They provide bounded
fixture mutation and read-only observation for certification resources. They never
produce release-readiness PASS decisions and never persist credential values.
"""

from __future__ import annotations

import base64
from collections import defaultdict
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import os
import re
from typing import Any
from urllib import request as urllib_request

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from fabric_data_framework.adapters.fabric.capture_transports import (
    FabricCaptureObservation,
    FabricSparkJobDefinitionBinding,
)
from fabric_data_framework.adapters.fabric.contracts import FabricCaptureRequest
from fabric_data_framework.adapters.fabric.rest import FabricJobInstance
from fabric_data_framework.contracts.target_operation import TargetOperationIntent
from fabric_data_framework.evidence.business_paths.driver import (
    BusinessPathDriverReceipt,
    BusinessPathDriverRequest,
)
from fabric_data_framework.evidence.business_paths.evidence import (
    BusinessPathObservationRequest,
    BusinessPathStateObservation,
)
from fabric_data_framework.metadata.config import ExecutionEngine
from fabric_data_framework.recovery.fabric_warehouse import FabricWarehouseMutationEvidence
from fabric_data_framework.recovery.target_probe import TargetCommitProbeEvidence
from fabric_data_framework.recovery.warehouse_fault_injection import (
    FabricWarehouseCommitFaultArmEvidence,
    FabricWarehouseCommitFaultInjector,
    FabricWarehouseCommitFaultRequest,
    FabricWarehouseCommitFaultVerification,
)


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_QUALIFIED = re.compile(
    r"^(?P<schema>[A-Za-z_][A-Za-z0-9_]{0,127})\."
    r"(?P<table>[A-Za-z_][A-Za-z0-9_]{0,127})$"
)


def _quote_identifier(value: str) -> str:
    if _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"unsafe certification SQL identifier: {value!r}")
    return f"[{value}]"


def _quote_table(value: str) -> str:
    match = _QUALIFIED.fullmatch(value)
    if match is None:
        raise ValueError("certification table must use exact schema.table syntax")
    return (
        f"{_quote_identifier(match.group('schema'))}."
        f"{_quote_identifier(match.group('table'))}"
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _canonical_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized = [
        {str(key): _json_value(value) for key, value in sorted(row.items())}
        for row in rows
    ]
    return sorted(
        normalized,
        key=lambda item: json.dumps(
            item,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ),
    )


def _semantic_hash(rows: list[Mapping[str, Any]]) -> str:
    payload = json.dumps(
        _canonical_rows(rows),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _spark_session():
    try:
        from pyspark.sql import SparkSession
    except Exception as exc:  # pragma: no cover - Fabric runtime dependency
        raise RuntimeError("certification observation requires pyspark") from exc
    session = SparkSession.getActiveSession()
    if session is None:
        raise RuntimeError("certification observation requires an active SparkSession")
    return session


def observe_capture(
    request: FabricCaptureRequest,
    job: FabricJobInstance,
) -> FabricCaptureObservation:
    """Observe the real certification landing table after Copy/Spark completion."""

    spark = _spark_session()
    landing = spark.table(request.landing_reference)
    count = int(landing.count())
    lower = request.source_lower_bound
    upper = request.source_upper_bound
    diagnostics: dict[str, object] = {
        "observation_kind": "lakehouse_table_count",
        "job_instance_id": str(job.job_instance_id),
    }
    if request.execution_engine is ExecutionEngine.SPARK:
        marker_rows = (
            spark.table("dbo.cert_spark_run_marker")
            .where("dataset_id = 'cert.spark'")
            .collect()
        )
        if len(marker_rows) != 1:
            raise RuntimeError(
                "Spark certification requires exactly one dbo.cert_spark_run_marker row"
            )
        marker = marker_rows[0].asDict(recursive=True)
        if int(marker["rows_written"]) != count:
            raise RuntimeError("Spark run marker row count does not match landing table")
        lower = marker.get("source_lower_bound")
        upper = marker.get("source_upper_bound")
        diagnostics["bounds_observation_kind"] = "spark_run_marker"
    return FabricCaptureObservation(
        rows_read=count,
        rows_written=count,
        landing_reference=request.landing_reference,
        source_reference=request.source_reference,
        source_lower_bound=lower,
        source_upper_bound=upper,
        schema_version="framework-certification-v1",
        diagnostics=diagnostics,
    )


def spark_execution_data(
    request: FabricCaptureRequest,
    binding: FabricSparkJobDefinitionBinding,
) -> Mapping[str, object]:
    """Encode exact framework-frozen Spark bounds into Fabric ExecutionData."""

    del binding
    payload = {
        "dataset_id": request.dataset_id,
        "source_lower_bound": request.source_lower_bound,
        "source_upper_bound": request.source_upper_bound,
        "parameters": dict(request.parameters),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).decode("ascii")
    return {"commandLineArguments": f"--payload-b64 {encoded}"}


def _replace_rows(
    connection: Connection,
    table_name: str,
    rows: list[Mapping[str, Any]],
) -> None:
    table = _quote_table(table_name)
    connection.execute(text(f"DELETE FROM {table}"))
    if not rows:
        return
    columns = tuple(rows[0].keys())
    if not columns or any(tuple(row.keys()) != columns for row in rows):
        raise ValueError("certification fixture rows require identical ordered columns")
    quoted = ", ".join(_quote_identifier(str(column)) for column in columns)
    parameters = ", ".join(f":p{index}" for index in range(len(columns)))
    statement = text(f"INSERT INTO {table} ({quoted}) VALUES ({parameters})")
    for row in rows:
        connection.execute(
            statement,
            {f"p{index}": row[column] for index, column in enumerate(columns)},
        )


def warehouse_mutation(
    connection: Connection,
    intent: TargetOperationIntent,
    payload: Mapping[str, Any],
) -> FabricWarehouseMutationEvidence:
    """Mutate only the explicitly named bounded certification target table."""

    table_name = payload.get("table")
    rows = payload.get("rows")
    if not isinstance(table_name, str) or not isinstance(rows, list):
        raise ValueError("Warehouse certification mutation requires table and rows")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("Warehouse certification mutation rows must be JSON objects")
    _replace_rows(connection, table_name, rows)
    return FabricWarehouseMutationEvidence(
        query_label=f"certification:{intent.dataset_id}",
        detail="bounded framework certification target mutation executed",
    )


class _ExternalFaultController(FabricWarehouseCommitFaultInjector):
    def __init__(self, *, controller_url: str, token_env_var: str | None) -> None:
        if not controller_url.startswith("https://") or ".invalid" in controller_url:
            raise RuntimeError(
                "real Warehouse fault controller requires a configured HTTPS endpoint"
            )
        self._base = controller_url.rstrip("/")
        self._token_env_var = token_env_var

    def _post(self, action: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._token_env_var is not None:
            token = os.environ.get(self._token_env_var, "").strip()
            if not token:
                raise RuntimeError(
                    f"real Warehouse fault controller token is missing: {self._token_env_var}"
                )
            headers["Authorization"] = f"Bearer {token}"
        req = urllib_request.Request(
            f"{self._base}/{action}",
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=30) as response:  # noqa: S310
            raw = response.read()
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise RuntimeError("Warehouse fault controller returned non-object JSON")
        return value

    @staticmethod
    def _request_payload(request: FabricWarehouseCommitFaultRequest) -> dict[str, Any]:
        return {
            "operation_key": request.operation_key,
            "dataset_id": request.dataset_id,
            "dataset_run_id": str(request.dataset_run_id),
            "attempt": request.attempt,
            "target_reference": request.target_reference,
            "phase": request.phase.value,
        }

    def arm(
        self,
        request: FabricWarehouseCommitFaultRequest,
    ) -> FabricWarehouseCommitFaultArmEvidence:
        value = self._post("arm", self._request_payload(request))
        return FabricWarehouseCommitFaultArmEvidence(
            armed=value.get("armed") is True,
            phase=request.phase,
            evidence_reference=value.get("evidence_reference"),
            provider_fault_id=value.get("provider_fault_id"),
            detail=value.get("detail"),
        )

    def disarm(self, request: FabricWarehouseCommitFaultRequest) -> None:
        value = self._post("disarm", self._request_payload(request))
        if value.get("disarmed") is not True:
            raise RuntimeError("Warehouse fault controller did not confirm disarm")

    def verify(
        self,
        request: FabricWarehouseCommitFaultRequest,
        *,
        observed_exception_type: str | None,
        probe_evidence: TargetCommitProbeEvidence,
    ) -> FabricWarehouseCommitFaultVerification:
        payload = self._request_payload(request)
        payload.update(
            {
                "observed_exception_type": observed_exception_type,
                "probe_resolution": probe_evidence.resolution.value,
            }
        )
        value = self._post("verify", payload)
        return FabricWarehouseCommitFaultVerification(
            triggered=value.get("triggered") is True,
            phase=request.phase,
            evidence_reference=value.get("evidence_reference"),
            provider_fault_id=value.get("provider_fault_id"),
            detail=value.get("detail"),
        )


def warehouse_fault_injector(
    _engine: object,
    _request: FabricWarehouseCommitFaultRequest,
    payload: Mapping[str, Any],
) -> FabricWarehouseCommitFaultInjector:
    controller_url = payload.get("controller_url")
    token_env_var = payload.get("token_env_var")
    if not isinstance(controller_url, str):
        raise RuntimeError("Warehouse fault payload requires controller_url")
    if token_env_var is not None and not isinstance(token_env_var, str):
        raise RuntimeError("Warehouse fault token_env_var must be a string when supplied")
    return _ExternalFaultController(
        controller_url=controller_url,
        token_env_var=token_env_var,
    )


def _replace_fixture_rows(
    database_url: str,
    *,
    table_name: str,
    rows: list[Mapping[str, Any]],
) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            _replace_rows(connection, table_name, rows)
    finally:
        engine.dispose()


def _set_pipeline_control(
    database_url: str,
    *,
    table_name: str,
    dataset_id: str,
    failure_mode: str,
) -> None:
    table = _quote_table(table_name)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(f"DELETE FROM {table} WHERE [dataset_id] = :dataset_id"),
                {"dataset_id": dataset_id},
            )
            connection.execute(
                text(
                    f"INSERT INTO {table} ([dataset_id], [failure_mode]) "
                    "VALUES (:dataset_id, :failure_mode)"
                ),
                {"dataset_id": dataset_id, "failure_mode": failure_mode},
            )
    finally:
        engine.dispose()


def _warehouse_database_url() -> str:
    value = os.environ.get("WAREHOUSE_DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("WAREHOUSE_DATABASE_URL is required for certification fixture")
    return value


def drive_business_path(request: BusinessPathDriverRequest) -> BusinessPathDriverReceipt:
    """Prepare bounded fixture/control rows without deciding PASS."""

    actions = request.parameters.get("actions")
    control_table = request.parameters.get("control_table")
    if not isinstance(actions, dict):
        raise ValueError("business path driver requires actions")
    action = actions.get(request.phase.value)
    if not isinstance(action, dict):
        raise ValueError(f"business path driver has no action for {request.phase.value}")
    replacements = action.get("replacements", [])
    if not isinstance(replacements, list):
        raise ValueError("business path replacements must be a list")
    database_url = _warehouse_database_url()
    for replacement in replacements:
        if not isinstance(replacement, dict):
            raise ValueError("business path replacement must be an object")
        table = replacement.get("table")
        rows = replacement.get("rows")
        if not isinstance(table, str) or not isinstance(rows, list):
            raise ValueError("business path replacement requires table and rows")
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError("business path replacement rows must be JSON objects")
        _replace_fixture_rows(database_url, table_name=table, rows=rows)
    failure_mode = action.get("failure_mode", "SUCCESS")
    if control_table is not None:
        if not isinstance(control_table, str) or not isinstance(failure_mode, str):
            raise ValueError("business path control table/failure mode are invalid")
        _set_pipeline_control(
            database_url,
            table_name=control_table,
            dataset_id=request.dataset_id,
            failure_mode=failure_mode,
        )
    return BusinessPathDriverReceipt(
        gate_id=request.gate_id,
        dataset_id=request.dataset_id,
        scenario_hash=request.scenario_hash,
        phase=request.phase,
        evidence_references=(
            f"certification-driver:{request.dataset_id}:{request.phase.value.lower()}",
        ),
    )


def _select_rows(
    connection: Connection,
    spec: Mapping[str, Any],
) -> list[dict[str, Any]]:
    table_name = spec.get("table")
    columns = spec.get("columns")
    where = spec.get("where", {})
    if not isinstance(table_name, str):
        raise ValueError("business path observation table must be a string")
    if not isinstance(columns, list) or not columns or not all(
        isinstance(column, str) for column in columns
    ):
        raise ValueError("business path observation columns must be a non-empty string list")
    if not isinstance(where, dict):
        raise ValueError("business path observation where must be an object")
    selected = ", ".join(_quote_identifier(column) for column in columns)
    statement = f"SELECT {selected} FROM {_quote_table(table_name)}"
    parameters: dict[str, Any] = {}
    if where:
        predicates: list[str] = []
        for index, (column, value) in enumerate(sorted(where.items())):
            name = f"w{index}"
            predicates.append(f"{_quote_identifier(str(column))} = :{name}")
            parameters[name] = value
        statement += " WHERE " + " AND ".join(predicates)
    result = connection.execute(text(statement), parameters)
    return [dict(row._mapping) for row in result]


def _one_current_per_key(
    rows: list[Mapping[str, Any]],
    *,
    business_keys: list[str],
    current_flag: str,
) -> bool:
    counts: defaultdict[tuple[Any, ...], int] = defaultdict(int)
    all_keys: set[tuple[Any, ...]] = set()
    for row in rows:
        key = tuple(row[column] for column in business_keys)
        all_keys.add(key)
        if bool(row[current_flag]):
            counts[key] += 1
    return bool(all_keys) and all(counts[key] == 1 for key in all_keys)


def observe_business_path(
    request: BusinessPathObservationRequest,
) -> BusinessPathStateObservation:
    """Read real target/progress/history state and return semantic facts only."""

    target_spec = request.parameters.get("target")
    progress_spec = request.parameters.get("progress")
    history_spec = request.parameters.get("history")
    if not isinstance(target_spec, dict) or not isinstance(progress_spec, dict):
        raise ValueError("business path observer requires target and progress specs")
    engine = create_engine(_warehouse_database_url())
    try:
        with engine.connect() as connection:
            target_rows = _select_rows(connection, target_spec)
            progress_rows = _select_rows(connection, progress_spec)
            history_rows: list[dict[str, Any]] | None = None
            current_ok: bool | None = None
            if history_spec is not None:
                if not isinstance(history_spec, dict):
                    raise ValueError("business path history spec must be an object")
                history_rows = _select_rows(connection, history_spec)
                business_keys = history_spec.get("business_key_columns")
                current_flag = history_spec.get("current_flag_column")
                if (
                    not isinstance(business_keys, list)
                    or not all(isinstance(column, str) for column in business_keys)
                    or not isinstance(current_flag, str)
                ):
                    raise ValueError(
                        "business path history spec requires business_key_columns/current_flag_column"
                    )
                current_ok = _one_current_per_key(
                    history_rows,
                    business_keys=business_keys,
                    current_flag=current_flag,
                )
    finally:
        engine.dispose()
    references = [
        f"certification-observer:{request.dataset_id}:{request.phase.value.lower()}:target",
        f"certification-observer:{request.dataset_id}:{request.phase.value.lower()}:progress",
    ]
    if history_rows is not None:
        references.append(
            f"certification-observer:{request.dataset_id}:{request.phase.value.lower()}:history"
        )
    return BusinessPathStateObservation(
        dataset_id=request.dataset_id,
        phase=request.phase,
        target_semantic_sha256=_semantic_hash(target_rows),
        target_row_count=len(target_rows),
        progress_semantic_sha256=_semantic_hash(progress_rows),
        history_semantic_sha256=(
            _semantic_hash(history_rows) if history_rows is not None else None
        ),
        one_current_row_per_business_key=current_ok,
        evidence_references=tuple(references),
    )


def forbidden_noop_apply(*_args: Any, **_kwargs: Any) -> None:
    """Fail if a capture-only certification path ever reaches apply."""

    raise RuntimeError("certification capture-only path must never execute apply")


__all__ = [
    "drive_business_path",
    "forbidden_noop_apply",
    "observe_business_path",
    "observe_capture",
    "spark_execution_data",
    "warehouse_fault_injector",
    "warehouse_mutation",
]
