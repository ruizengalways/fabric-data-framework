"""CLI presentation layer for installed-wheel real-Fabric certification."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from ..adapters.fabric.auth import EnvironmentAccessTokenProvider
from ..certification import (
    CertificationCheckStatus,
    DEFAULT_CERTIFICATION_ROOT,
    certify_installed,
    discover_certification_bindings_from_names,
    print_certification_summary,
)


CERTIFICATION_COMMANDS = frozenset({"certify", "discover-certification-bindings"})


def _certify_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-framework certify")
    parser.add_argument(
        "--certification-root",
        default=str(DEFAULT_CERTIFICATION_ROOT),
        help="Directory containing CANDIDATE.json, exactly one candidate framework wheel and optional framework integration inputs.",
    )
    parser.add_argument("--environment", default="DEV", choices=("DEV", "UAT", "PROD"))
    parser.add_argument("--integration-inputs")
    parser.add_argument("--output-dir")
    parser.add_argument("--lakehouse-base-path", default="Files/framework_cert")
    parser.add_argument(
        "--allow-live-mutations",
        action="store_true",
        help="Authorize approved control-plane/Pipeline/Copy/Spark/Warehouse/business-path certification mutations.",
    )
    parser.add_argument("--allow-control-plane-migration", action="store_true")
    parser.add_argument(
        "--allow-warehouse-session-termination",
        action="store_true",
        help="Separately authorize Admin-level exact Warehouse session termination when the reviewed fault recipe requires it.",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Exit non-zero unless every unified certification check is PASS.",
    )
    return parser


def _binding_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fabric-framework discover-certification-bindings"
    )
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--item-read-name", required=True)
    parser.add_argument("--item-read-type", required=True)
    parser.add_argument("--pipeline-name", required=True)
    parser.add_argument("--copy-job-name", required=True)
    parser.add_argument("--spark-job-name", required=True)
    parser.add_argument("--access-token-env-var", default="FABRIC_ACCESS_TOKEN")
    parser.add_argument("--output")
    return parser


def _active_spark():
    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise ValueError(
            "fabric-framework certify requires a PySpark/Fabric runtime; use the Python API inside a Fabric notebook"
        ) from exc
    spark = SparkSession.getActiveSession()
    if spark is None:
        raise ValueError(
            "no active SparkSession is available; use fabric_data_framework.certification.certify_installed(...) inside the Fabric notebook"
        )
    return spark


def _run_certify(argv: list[str]) -> int:
    args = _certify_parser().parse_args(argv)
    try:
        report = certify_installed(
            spark=_active_spark(),
            certification_root=args.certification_root,
            environment=args.environment,
            integration_inputs_root=args.integration_inputs,
            output_dir=args.output_dir,
            lakehouse_base_path=args.lakehouse_base_path,
            allow_live_mutations=args.allow_live_mutations,
            allow_control_plane_migration=args.allow_control_plane_migration,
            allow_warehouse_session_termination=args.allow_warehouse_session_termination,
        )
        print_certification_summary(report)
        if any(item.status is CertificationCheckStatus.FAIL for item in report.checks):
            return 2
        if args.require_complete and not report.passed:
            return 2
        return 0
    except (OSError, RuntimeError, TypeError, ValueError):
        print("error: installed-wheel Fabric certification failed", file=sys.stderr)
        return 2


def _run_binding_discovery(argv: list[str]) -> int:
    args = _binding_parser().parse_args(argv)
    try:
        result = discover_certification_bindings_from_names(
            token_provider=EnvironmentAccessTokenProvider(
                env_var=args.access_token_env_var,
            ),
            workspace_id=args.workspace_id,
            item_read_name=args.item_read_name,
            item_read_type=args.item_read_type,
            pipeline_name=args.pipeline_name,
            copy_job_name=args.copy_job_name,
            spark_job_name=args.spark_job_name,
        )
        rendered = result.model_dump_json(indent=2) + "\n"
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, TypeError) as exc:
        print(
            f"error: certification binding discovery failed ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 2


def run_if_matched(argv: list[str]) -> int | None:
    if argv and argv[0] == "certify":
        return _run_certify(argv[1:])
    if argv and argv[0] == "discover-certification-bindings":
        return _run_binding_discovery(argv[1:])
    return None


__all__ = ["CERTIFICATION_COMMANDS", "run_if_matched"]
