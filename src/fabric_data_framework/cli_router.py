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
from .approved_control_plane_runner import (
    execute_approved_control_plane_certification,
    write_control_plane_certification_report,
)
from .control_plane_certification import ControlPlaneExternalEvidence
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
        # Write only after every merge/certification validation succeeds. Existing
        # retained output is therefore not clobbered by a conflict or failed gate.
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


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if effective_argv and effective_argv[0] == "integration-evidence-merge":
        return _run_merge(effective_argv[1:])
    if effective_argv and effective_argv[0] == "integration-control-plane-certify-run":
        return _run_control_plane_certification(effective_argv[1:])
    return legacy_cli.main(effective_argv)


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
