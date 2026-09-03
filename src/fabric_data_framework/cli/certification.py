"""CLI presentation layer for the unified real-Fabric certification runner."""

from __future__ import annotations

import argparse
import sys

from ..certification import (
    CertificationCheckStatus,
    DEFAULT_CERTIFICATION_ROOT,
    certify,
    print_certification_summary,
)


CERTIFICATION_COMMANDS = frozenset({"certify"})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-framework certify")
    parser.add_argument(
        "--certification-root",
        default=str(DEFAULT_CERTIFICATION_ROOT),
        help="Directory containing CANDIDATE.json, one framework wheel and optional customer-inputs/.",
    )
    parser.add_argument("--environment", default="DEV", choices=("DEV", "UAT", "PROD"))
    parser.add_argument("--customer-inputs")
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
            certification_root=args.certification_root,
            environment=args.environment,
            customer_inputs_root=args.customer_inputs,
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
        print("error: unified Fabric certification failed", file=sys.stderr)
        return 2


def run_if_matched(argv: list[str]) -> int | None:
    if argv and argv[0] == "certify":
        return _run(argv[1:])
    return None


__all__ = ["CERTIFICATION_COMMANDS", "run_if_matched"]
