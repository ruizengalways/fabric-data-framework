"""CLI presentation layer for the unified real-Fabric certification runner."""

from __future__ import annotations

import argparse
import sys

from ..certification import CertificationCheckStatus, certify, print_certification_summary


CERTIFICATION_COMMANDS = frozenset({"certify"})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-framework certify")
    parser.add_argument("--candidate-manifest", required=True)
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--environment", default="DEV", choices=("DEV", "UAT", "PROD"))
    parser.add_argument("--lakehouse-base-path", default="Files/framework_cert")
    parser.add_argument("--customer-inputs")
    parser.add_argument("--no-auto-notebook-token", action="store_true")
    parser.add_argument("--no-install-extensions", action="store_true")
    parser.add_argument("--allow-control-plane-migration", action="store_true")
    parser.add_argument("--allow-control-plane-writes", action="store_true")
    parser.add_argument("--allow-pipeline-execution", action="store_true")
    parser.add_argument("--allow-capture-execution", action="store_true")
    parser.add_argument("--allow-warehouse-execution", action="store_true")
    parser.add_argument("--allow-warehouse-fault-injection", action="store_true")
    parser.add_argument("--allow-warehouse-session-termination", action="store_true")
    parser.add_argument("--allow-business-path-execution", action="store_true")
    parser.add_argument("--allow-scenario-mutation", action="store_true")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Exit non-zero unless every unified certification check is PASS.",
    )
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
            "no active SparkSession is available; use fabric_data_framework.certification.certify(...) inside the Fabric notebook"
        )
    return spark


def _run(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    try:
        report = certify(
            spark=_active_spark(),
            candidate_manifest_path=args.candidate_manifest,
            wheel_path=args.wheel,
            output_dir=args.output_dir,
            environment=args.environment,
            lakehouse_base_path=args.lakehouse_base_path,
            customer_inputs_root=args.customer_inputs,
            auto_notebook_token=not args.no_auto_notebook_token,
            install_extensions=not args.no_install_extensions,
            allow_control_plane_migration=args.allow_control_plane_migration,
            allow_control_plane_writes=args.allow_control_plane_writes,
            allow_pipeline_execution=args.allow_pipeline_execution,
            allow_capture_execution=args.allow_capture_execution,
            allow_warehouse_execution=args.allow_warehouse_execution,
            allow_warehouse_fault_injection=args.allow_warehouse_fault_injection,
            allow_warehouse_session_termination=args.allow_warehouse_session_termination,
            allow_business_path_execution=args.allow_business_path_execution,
            allow_scenario_mutation=args.allow_scenario_mutation,
        )
        print_certification_summary(report)
        if any(item.status is CertificationCheckStatus.FAIL for item in report.checks):
            return 2
        if args.require_complete and not report.passed:
            return 2
        return 0
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(f"error: unified Fabric certification failed ({type(exc).__name__})", file=sys.stderr)
        return 2


def run_if_matched(argv: list[str]) -> int | None:
    if argv and argv[0] == "certify":
        return _run(argv[1:])
    return None


__all__ = ["CERTIFICATION_COMMANDS", "run_if_matched"]
