"""Console-script router for additive CLI commands.

The historical CLI implementation remains in :mod:`fabric_data_framework.cli`.
This thin entrypoint lets new isolated commands be added without duplicating or
rewriting the mature command parser; unknown commands delegate unchanged.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import cli as legacy_cli
from .approved_capture_runner import (
    execute_approved_capture,
    load_approved_capture_run_config,
)
from .approved_control_plane_runner import (
    execute_approved_control_plane_certification,
    write_control_plane_certification_report,
)
from .approved_pipeline_runner import execute_approved_pipeline
from .approved_warehouse_fault_runner import (
    execute_approved_warehouse_fault_drill,
    load_approved_warehouse_fault_drill_config,
)
from .approved_warehouse_runner import (
    execute_approved_warehouse,
    load_approved_warehouse_run_config,
)
from .control_plane_certification import ControlPlaneExternalEvidence
from .delivery import load_dataset_configs, load_release_manifest, write_json_model
from .integration_evidence import (
    IntegrationEvidenceStatus,
    load_integration_evidence_manifest,
    load_integration_evidence_spec,
    validate_integration_evidence_manifest,
    write_integration_evidence_manifest,
)
from .integration_evidence_merge import (
    IntegrationEvidenceMergeConflict,
    merge_integration_evidence_manifests,
)
from .integration_runner import load_approved_integration_runner_config


def _merge_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-framework integration-evidence-merge")
    parser.add_argument("--spec", required=True)
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        dest="inputs",
        help="Partial integration evidence manifest; repeat for each retained stage.",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--require-certified",
        action="store_true",
        help="Fail without writing output unless every required check is PASS after merge.",
    )
    return parser


def _control_plane_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fabric-framework integration-control-plane-certify-run"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--check-id", required=True)
    parser.add_argument(
        "--external-evidence",
        required=True,
        help="JSON references for IAM/network/restore/HA/monitoring/retention evidence.",
    )
    parser.add_argument(
        "--evidence-reference",
        action="append",
        required=True,
        dest="evidence_references",
        help="Durable reference to the retained certification artifact; repeat if needed.",
    )
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--output", required=True, help="Partial integration manifest output.")
    parser.add_argument(
        "--allow-conformance-writes",
        action="store_true",
        help=(
            "Explicitly authorize temporary rollback/CAS certification probes against the "
            "configured approved database."
        ),
    )
    return parser


def _pipeline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fabric-framework integration-pipeline-run"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--prerequisite-manifest", required=True)
    parser.add_argument("--release-manifest", required=True)
    parser.add_argument("--config-dir", required=True)
    parser.add_argument("--check-id", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument(
        "--evidence-reference",
        action="append",
        required=True,
        dest="evidence_references",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-pipeline-execution", action="store_true")
    return parser


def _capture_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fabric-framework integration-capture-run"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--prerequisite-manifest", required=True)
    parser.add_argument("--release-manifest", required=True)
    parser.add_argument("--config-dir", required=True)
    parser.add_argument("--capture-config", required=True)
    parser.add_argument(
        "--evidence-reference",
        action="append",
        required=True,
        dest="evidence_references",
    )
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-capture-execution", action="store_true")
    return parser


def _warehouse_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fabric-framework integration-warehouse-run"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument(
        "--prerequisite-manifest",
        required=True,
        help=(
            "Exact-spec merged manifest containing PASS item-read and control-plane "
            "certification prerequisites while the Warehouse check remains NOT_RUN."
        ),
    )
    parser.add_argument("--release-manifest", required=True)
    parser.add_argument("--config-dir", required=True)
    parser.add_argument(
        "--warehouse-config",
        required=True,
        help=(
            "Credential-free representative mutation recipe with a logical bounded "
            "Warehouse mutation extension and exact extension artifact name."
        ),
    )
    parser.add_argument(
        "--evidence-reference",
        action="append",
        required=True,
        dest="evidence_references",
        help="Durable retained Warehouse evidence reference; repeat if needed.",
    )
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--output", required=True, help="Partial integration manifest output.")
    parser.add_argument(
        "--allow-warehouse-execution",
        action="store_true",
        help="Explicitly authorize the representative Warehouse target mutation.",
    )
    return parser


def _warehouse_fault_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fabric-framework integration-warehouse-fault-drill-run"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument(
        "--prerequisite-manifest",
        required=True,
        help=(
            "Exact-spec merged manifest containing PASS item-read, control-plane and "
            "normal Warehouse commit prerequisites while the fault drill remains NOT_RUN."
        ),
    )
    parser.add_argument("--release-manifest", required=True)
    parser.add_argument("--config-dir", required=True)
    parser.add_argument(
        "--fault-config",
        required=True,
        help="Credential-free mutation plus provider-specific commit-fault drill recipe.",
    )
    parser.add_argument(
        "--evidence-reference",
        action="append",
        required=True,
        dest="evidence_references",
        help="Durable retained fault-drill evidence reference; repeat if needed.",
    )
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--output", required=True, help="Partial integration manifest output.")
    parser.add_argument(
        "--allow-warehouse-fault-injection",
        action="store_true",
        help=(
            "Explicitly authorize the provider/session fault injection and representative "
            "Warehouse mutation."
        ),
    )
    parser.add_argument(
        "--allow-warehouse-session-termination",
        action="store_true",
        help=(
            "Separately authorize Admin-level exact-session termination recovery when the "
            "fault config explicitly enables it. This never follows implicitly from fault "
            "injection authorization."
        ),
    )
    return parser


def _run_merge(argv: list[str]) -> int:
    args = _merge_parser().parse_args(argv)
    try:
        spec = load_integration_evidence_spec(args.spec)
        manifests = tuple(load_integration_evidence_manifest(path) for path in args.inputs)
        merged = merge_integration_evidence_manifests(spec, manifests)
        validate_integration_evidence_manifest(
            spec,
            merged,
            require_certified=args.require_certified,
        )
        write_integration_evidence_manifest(merged, args.output)
        print(
            f"integration_evidence_id={merged.evidence_id} "
            f"manifest_hash={merged.manifest_hash} "
            f"certified={str(merged.certified).lower()}"
        )
        return 0
    except (IntegrationEvidenceMergeConflict, KeyError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _run_control_plane_certification(argv: list[str]) -> int:
    args = _control_plane_parser().parse_args(argv)
    try:
        config = load_approved_integration_runner_config(args.config)
        spec = load_integration_evidence_spec(args.spec)
        external_evidence = ControlPlaneExternalEvidence.from_json_file(
            args.external_evidence
        )
        execution = execute_approved_control_plane_certification(
            config=config,
            spec=spec,
            check_id=args.check_id,
            environ=os.environ,
            external_evidence=external_evidence,
            evidence_references=tuple(args.evidence_references),
            allow_conformance_writes=args.allow_conformance_writes,
        )
        if execution.report is not None:
            write_control_plane_certification_report(
                execution.report,
                args.report_output,
            )
        write_integration_evidence_manifest(execution.manifest, args.output)
        result = next(
            item for item in execution.manifest.results if item.check_id == args.check_id
        )
        print(
            f"integration_evidence_id={execution.manifest.evidence_id} "
            f"check_id={result.check_id} status={result.status.value} "
            f"manifest_hash={execution.manifest.manifest_hash}"
        )
        if result.status is not IntegrationEvidenceStatus.PASS:
            raise ValueError("approved control-plane certification check did not PASS")
        return 0
    except (KeyError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _run_pipeline(argv: list[str]) -> int:
    args = _pipeline_parser().parse_args(argv)
    try:
        config = load_approved_integration_runner_config(args.config)
        spec = load_integration_evidence_spec(args.spec)
        prerequisite_manifest = load_integration_evidence_manifest(args.prerequisite_manifest)
        release_manifest = load_release_manifest(args.release_manifest)
        configs = load_dataset_configs(args.config_dir)
        execution = execute_approved_pipeline(
            config=config,
            spec=spec,
            prerequisite_manifest=prerequisite_manifest,
            release_manifest=release_manifest,
            configs=configs,
            check_id=args.check_id,
            dataset_id=args.dataset_id,
            environ=os.environ,
            evidence_references=tuple(args.evidence_references),
            allow_pipeline_execution=args.allow_pipeline_execution,
        )
        write_integration_evidence_manifest(execution.manifest, args.output)
        result = next(
            item for item in execution.manifest.results if item.check_id == args.check_id
        )
        print(
            f"integration_evidence_id={execution.manifest.evidence_id} "
            f"check_id={result.check_id} status={result.status.value} "
            f"manifest_hash={execution.manifest.manifest_hash}"
        )
        if result.status is not IntegrationEvidenceStatus.PASS:
            raise ValueError("approved Pipeline execution check did not PASS")
        return 0
    except (KeyError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _run_capture(argv: list[str]) -> int:
    args = _capture_parser().parse_args(argv)
    try:
        config = load_approved_integration_runner_config(args.config)
        spec = load_integration_evidence_spec(args.spec)
        prerequisite_manifest = load_integration_evidence_manifest(args.prerequisite_manifest)
        release_manifest = load_release_manifest(args.release_manifest)
        configs = load_dataset_configs(args.config_dir)
        capture_config = load_approved_capture_run_config(args.capture_config)
        execution = execute_approved_capture(
            config=config,
            spec=spec,
            prerequisite_manifest=prerequisite_manifest,
            release_manifest=release_manifest,
            configs=configs,
            capture_config=capture_config,
            environ=os.environ,
            evidence_references=tuple(args.evidence_references),
            allow_capture_execution=args.allow_capture_execution,
        )
        if execution.report is not None:
            write_json_model(execution.report, args.report_output)
        write_integration_evidence_manifest(execution.manifest, args.output)
        result = next(
            item
            for item in execution.manifest.results
            if item.check_id == capture_config.check_id
        )
        print(
            f"integration_evidence_id={execution.manifest.evidence_id} "
            f"check_id={result.check_id} status={result.status.value} "
            f"manifest_hash={execution.manifest.manifest_hash}"
        )
        if result.status is not IntegrationEvidenceStatus.PASS:
            raise ValueError("approved capture execution check did not PASS")
        if execution.report is None:
            raise ValueError("approved capture PASS did not produce a retained safe report")
        return 0
    except (KeyError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _run_warehouse(argv: list[str]) -> int:
    args = _warehouse_parser().parse_args(argv)
    try:
        config = load_approved_integration_runner_config(args.config)
        spec = load_integration_evidence_spec(args.spec)
        prerequisite_manifest = load_integration_evidence_manifest(args.prerequisite_manifest)
        release_manifest = load_release_manifest(args.release_manifest)
        configs = load_dataset_configs(args.config_dir)
        warehouse_config = load_approved_warehouse_run_config(args.warehouse_config)
        execution = execute_approved_warehouse(
            config=config,
            spec=spec,
            prerequisite_manifest=prerequisite_manifest,
            release_manifest=release_manifest,
            configs=configs,
            run_config=warehouse_config,
            environ=os.environ,
            evidence_references=tuple(args.evidence_references),
            allow_warehouse_execution=args.allow_warehouse_execution,
        )
        if execution.report is not None:
            write_json_model(execution.report, args.report_output)
        write_integration_evidence_manifest(execution.manifest, args.output)
        result = next(
            item
            for item in execution.manifest.results
            if item.check_id == warehouse_config.check_id
        )
        print(
            f"integration_evidence_id={execution.manifest.evidence_id} "
            f"check_id={result.check_id} status={result.status.value} "
            f"manifest_hash={execution.manifest.manifest_hash}"
        )
        if result.status is not IntegrationEvidenceStatus.PASS:
            raise ValueError("approved Warehouse execution check did not PASS")
        if execution.report is None:
            raise ValueError("approved Warehouse PASS did not produce a retained safe report")
        return 0
    except (KeyError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _run_warehouse_fault(argv: list[str]) -> int:
    args = _warehouse_fault_parser().parse_args(argv)
    try:
        config = load_approved_integration_runner_config(args.config)
        spec = load_integration_evidence_spec(args.spec)
        prerequisite_manifest = load_integration_evidence_manifest(args.prerequisite_manifest)
        release_manifest = load_release_manifest(args.release_manifest)
        configs = load_dataset_configs(args.config_dir)
        fault_config = load_approved_warehouse_fault_drill_config(args.fault_config)
        execution = execute_approved_warehouse_fault_drill(
            config=config,
            spec=spec,
            prerequisite_manifest=prerequisite_manifest,
            release_manifest=release_manifest,
            configs=configs,
            run_config=fault_config,
            environ=os.environ,
            evidence_references=tuple(args.evidence_references),
            allow_warehouse_fault_injection=args.allow_warehouse_fault_injection,
            allow_warehouse_session_termination=args.allow_warehouse_session_termination,
        )
        if execution.report is not None:
            write_json_model(execution.report, args.report_output)
        write_integration_evidence_manifest(execution.manifest, args.output)
        result = next(
            item
            for item in execution.manifest.results
            if item.check_id == fault_config.check_id
        )
        print(
            f"integration_evidence_id={execution.manifest.evidence_id} "
            f"check_id={result.check_id} status={result.status.value} "
            f"manifest_hash={execution.manifest.manifest_hash}"
        )
        if result.status is not IntegrationEvidenceStatus.PASS:
            raise ValueError("approved Warehouse ambiguous-COMMIT fault drill did not PASS")
        if execution.report is None:
            raise ValueError("approved Warehouse fault-drill PASS did not produce a safe report")
        return 0
    except (KeyError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if effective_argv and effective_argv[0] == "integration-evidence-merge":
        return _run_merge(effective_argv[1:])
    if effective_argv and effective_argv[0] == "integration-control-plane-certify-run":
        return _run_control_plane_certification(effective_argv[1:])
    if effective_argv and effective_argv[0] == "integration-pipeline-run":
        return _run_pipeline(effective_argv[1:])
    if effective_argv and effective_argv[0] == "integration-capture-run":
        return _run_capture(effective_argv[1:])
    if effective_argv and effective_argv[0] == "integration-warehouse-run":
        return _run_warehouse(effective_argv[1:])
    if effective_argv and effective_argv[0] == "integration-warehouse-fault-drill-run":
        return _run_warehouse_fault(effective_argv[1:])
    return legacy_cli.main(effective_argv)


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
