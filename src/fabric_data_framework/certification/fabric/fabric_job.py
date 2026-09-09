"""Executable entry point embedded in the framework certification Spark job item.

One Spark Job Definition is deliberately reused for two provider paths:

* direct Spark capture receives the framework-owned ``--payload-b64`` request and
  materializes the bounded Lakehouse landing/marker tables observed by certification;
* the Data Pipeline child receives the exact seven framework correlation parameters
  plus one credential-free runtime configuration blob, executes the bounded physical
  certification child, and persists the durable framework outcome through
  :func:`execute_pipeline_child`.

A semantic framework FAILED result is a valid child completion and therefore exits
zero. Provider failure is reserved for malformed identity, authentication, transport or
execution errors. This keeps provider status and framework outcome independently
observable by the parent certification runner.
"""

from __future__ import annotations

import argparse
import base64
from importlib.metadata import version as installed_version
import json
import os
from pathlib import Path
from typing import Any, Mapping

from fabric_data_framework.adapters.fabric.sql_auth import (
    CONTROL_PLANE_DATABASE_URL_ENV_VAR,
    CONTROL_PLANE_SQL_DATABASE_ENV_VAR,
    CONTROL_PLANE_SQL_SERVER_ENV_VAR,
    FABRIC_SQL_AUTH_MODE_ENV_VAR,
    FABRIC_SQL_AUTH_MODE_USER,
    WAREHOUSE_DATABASE_URL_ENV_VAR,
    WAREHOUSE_SQL_DATABASE_ENV_VAR,
    WAREHOUSE_SQL_SERVER_ENV_VAR,
    create_runtime_sql_engine,
)
from fabric_data_framework.control_plane.sqlalchemy_repository import (
    SqlAlchemyControlPlaneRepository,
)
from fabric_data_framework.deployment.candidate_artifact import (
    load_candidate_artifact_manifest,
)
from fabric_data_framework.deployment.delivery import load_dataset_configs
from fabric_data_framework.execution.pipeline_child import (
    execute_pipeline_child,
    pipeline_child_request_from_parameters,
)
from fabric_data_framework.metadata.config import DatasetStatus

from .pipeline_child import CertificationPipelineChildExecutor
from ..simple import DEFAULT_CERTIFICATION_ROOT


_DOMAIN = "framework-certification"
_RUNTIME_CONFIG_KEYS = frozenset(
    {
        "control_plane_sql_server",
        "control_plane_sql_database",
        "warehouse_sql_server",
        "warehouse_sql_database",
        "certification_root",
    }
)
_SPARK_PAYLOAD_KEYS = frozenset(
    {"dataset_id", "source_lower_bound", "source_upper_bound", "parameters"}
)
_CHILD_PARAMETER_KEYS = (
    "framework_pipeline_run_id",
    "framework_dataset_run_id",
    "dataset_id",
    "run_mode",
    "attempt",
    "effective_config_hash",
    "execution_plan_hash",
)


def _decode_json_b64(value: str, *, label: str) -> dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be URL-safe base64 encoded JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON must be an object")
    return payload


def encode_certification_runtime_config(
    *,
    control_plane_sql_server: str,
    control_plane_sql_database: str,
    warehouse_sql_server: str,
    warehouse_sql_database: str,
    certification_root: str | Path = DEFAULT_CERTIFICATION_ROOT,
) -> str:
    """Encode credential-free child runtime identity for a Pipeline activity definition."""

    payload = {
        "control_plane_sql_server": control_plane_sql_server,
        "control_plane_sql_database": control_plane_sql_database,
        "warehouse_sql_server": warehouse_sql_server,
        "warehouse_sql_database": warehouse_sql_database,
        "certification_root": str(certification_root),
    }
    for name, value in payload.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"certification runtime field {name} cannot be empty")
        if any(marker in value.lower() for marker in ("password=", "pwd=", "token=", "bearer ")):
            raise ValueError(f"certification runtime field {name} appears to contain credentials")
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii")


def _runtime_from_blob(value: str, environ: Mapping[str, str] | None) -> tuple[dict[str, str], Path]:
    payload = _decode_json_b64(value, label="runtime-config-b64")
    if set(payload) != _RUNTIME_CONFIG_KEYS:
        raise ValueError(
            "runtime config keys mismatch; "
            f"missing={sorted(_RUNTIME_CONFIG_KEYS - set(payload))}; "
            f"unexpected={sorted(set(payload) - _RUNTIME_CONFIG_KEYS)}"
        )
    values = {name: str(payload[name]).strip() for name in _RUNTIME_CONFIG_KEYS}
    if any(not item for item in values.values()):
        raise ValueError("runtime config values cannot be empty")
    runtime = dict(os.environ if environ is None else environ)
    runtime.update(
        {
            FABRIC_SQL_AUTH_MODE_ENV_VAR: FABRIC_SQL_AUTH_MODE_USER,
            CONTROL_PLANE_SQL_SERVER_ENV_VAR: values["control_plane_sql_server"],
            CONTROL_PLANE_SQL_DATABASE_ENV_VAR: values["control_plane_sql_database"],
            WAREHOUSE_SQL_SERVER_ENV_VAR: values["warehouse_sql_server"],
            WAREHOUSE_SQL_DATABASE_ENV_VAR: values["warehouse_sql_database"],
        }
    )
    return runtime, Path(values["certification_root"])


def _active_spark():
    try:
        from pyspark.sql import SparkSession
    except Exception as exc:  # pragma: no cover - Fabric runtime dependency
        raise RuntimeError("certification Spark job requires pyspark") from exc
    session = SparkSession.getActiveSession()
    if session is None:
        raise RuntimeError("certification Spark job requires an active SparkSession")
    return session


def _run_direct_spark_capture(payload_b64: str, *, spark=None) -> int:
    payload = _decode_json_b64(payload_b64, label="payload-b64")
    if set(payload) != _SPARK_PAYLOAD_KEYS:
        raise ValueError(
            "Spark certification payload keys mismatch; "
            f"missing={sorted(_SPARK_PAYLOAD_KEYS - set(payload))}; "
            f"unexpected={sorted(set(payload) - _SPARK_PAYLOAD_KEYS)}"
        )
    if payload["dataset_id"] != "cert.spark":
        raise ValueError("direct certification Spark job only supports dataset_id='cert.spark'")
    if not isinstance(payload["parameters"], dict):
        raise ValueError("Spark certification parameters must be an object")

    session = spark or _active_spark()
    frame = session.table("dbo.cert_spark_source")
    lower = payload["source_lower_bound"]
    upper = payload["source_upper_bound"]
    try:
        from pyspark.sql import functions as F
    except Exception as exc:  # pragma: no cover - Fabric runtime dependency
        raise RuntimeError("certification Spark capture requires pyspark functions") from exc

    if lower not in (None, ""):
        frame = frame.where(F.col("modified_at") > F.to_timestamp(F.lit(str(lower))))
    if upper not in (None, ""):
        frame = frame.where(F.col("modified_at") <= F.to_timestamp(F.lit(str(upper))))
    rows_written = int(frame.count())
    frame.write.mode("overwrite").saveAsTable("dbo.cert_spark_landing")
    marker = session.createDataFrame(
        [("cert.spark", rows_written, None if lower is None else str(lower), None if upper is None else str(upper))],
        "dataset_id string, rows_written long, source_lower_bound string, source_upper_bound string",
    )
    marker.write.mode("overwrite").saveAsTable("dbo.cert_spark_run_marker")
    print(f"certification Spark capture completed rows_written={rows_written}")
    return 0


def _child_parameters(args: argparse.Namespace) -> dict[str, object]:
    return {
        "framework_pipeline_run_id": args.framework_pipeline_run_id,
        "framework_dataset_run_id": args.framework_dataset_run_id,
        "dataset_id": args.dataset_id,
        "run_mode": args.run_mode,
        "attempt": args.attempt,
        "effective_config_hash": args.effective_config_hash,
        "execution_plan_hash": args.execution_plan_hash,
    }


def _run_pipeline_child(
    args: argparse.Namespace,
    *,
    environ: Mapping[str, str] | None = None,
    control_plane_engine_factory=None,
    warehouse_engine_factory=None,
) -> int:
    runtime, certification_root = _runtime_from_blob(args.runtime_config_b64, environ)
    manifest = load_candidate_artifact_manifest(certification_root / "CANDIDATE.json")
    observed_version = installed_version("fabric-data-framework")
    if manifest.framework_version != observed_version:
        raise ValueError(
            "installed framework version does not match certification candidate manifest"
        )
    configs = load_dataset_configs(
        certification_root / "integration-inputs/project/config/datasets"
    )
    request = pipeline_child_request_from_parameters(_child_parameters(args))

    make_control = control_plane_engine_factory or (
        lambda runtime_map: create_runtime_sql_engine(
            role="control-plane",
            environ=runtime_map,
            database_url_env_var=CONTROL_PLANE_DATABASE_URL_ENV_VAR,
        )
    )
    make_warehouse = warehouse_engine_factory or (
        lambda runtime_map: create_runtime_sql_engine(
            role="warehouse",
            environ=runtime_map,
            database_url_env_var=WAREHOUSE_DATABASE_URL_ENV_VAR,
        )
    )
    control_engine = make_control(runtime)
    warehouse_engine = make_warehouse(runtime)
    try:
        repository = SqlAlchemyControlPlaneRepository(
            control_engine,
            domain=_DOMAIN,
            domain_git_sha=manifest.candidate_git_sha,
            framework_version=manifest.framework_version,
            configs=configs,
        )
        outcome = execute_pipeline_child(
            repository=repository,
            request=request,
            executor=CertificationPipelineChildExecutor(warehouse_engine),
        )
    finally:
        warehouse_engine.dispose()
        control_engine.dispose()

    # A framework FAILED outcome is intentionally not converted into provider failure.
    # The parent proves provider status and durable framework status independently.
    print(
        "certification Pipeline child persisted durable outcome "
        f"dataset_id={outcome.dataset_id} status={outcome.status.value} "
        f"dataset_run_id={outcome.dataset_run_id}"
    )
    if outcome.status not in {DatasetStatus.SUCCEEDED, DatasetStatus.FAILED}:
        raise RuntimeError(
            f"certification Pipeline child produced unsupported terminal status {outcome.status.value}"
        )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-framework-certification-job")
    parser.add_argument("--payload-b64")
    parser.add_argument("--runtime-config-b64")
    parser.add_argument("--framework-pipeline-run-id")
    parser.add_argument("--framework-dataset-run-id")
    parser.add_argument("--dataset-id")
    parser.add_argument("--run-mode")
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--effective-config-hash")
    parser.add_argument("--execution-plan-hash")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    spark=None,
    environ: Mapping[str, str] | None = None,
    control_plane_engine_factory=None,
    warehouse_engine_factory=None,
) -> int:
    args = _parser().parse_args(argv)
    if args.payload_b64 is not None:
        child_values = [
            args.runtime_config_b64,
            args.framework_pipeline_run_id,
            args.framework_dataset_run_id,
            args.dataset_id,
            args.run_mode,
            args.attempt,
            args.effective_config_hash,
            args.execution_plan_hash,
        ]
        if any(value is not None for value in child_values):
            raise ValueError("direct Spark capture payload cannot be combined with Pipeline child arguments")
        return _run_direct_spark_capture(args.payload_b64, spark=spark)

    required = {
        "runtime_config_b64": args.runtime_config_b64,
        "framework_pipeline_run_id": args.framework_pipeline_run_id,
        "framework_dataset_run_id": args.framework_dataset_run_id,
        "dataset_id": args.dataset_id,
        "run_mode": args.run_mode,
        "attempt": args.attempt,
        "effective_config_hash": args.effective_config_hash,
        "execution_plan_hash": args.execution_plan_hash,
    }
    missing = sorted(name for name, value in required.items() if value is None)
    if missing:
        raise ValueError("Pipeline child Spark job arguments are incomplete: " + ",".join(missing))
    return _run_pipeline_child(
        args,
        environ=environ,
        control_plane_engine_factory=control_plane_engine_factory,
        warehouse_engine_factory=warehouse_engine_factory,
    )


if __name__ == "__main__":  # pragma: no cover - provider entry point
    raise SystemExit(main())


__all__ = ["encode_certification_runtime_config", "main"]
