"""Console-script router for additive CLI commands.

The historical CLI implementation remains in :mod:`fabric_data_framework.cli`.
This thin entrypoint lets new isolated commands be added without duplicating or
rewriting the mature command parser; unknown commands delegate unchanged.
"""

from __future__ import annotations

import argparse
import sys

from . import cli as legacy_cli
from .integration_evidence import (
    load_integration_evidence_manifest,
    load_integration_evidence_spec,
    validate_integration_evidence_manifest,
    write_integration_evidence_manifest,
)
from .integration_evidence_merge import (
    IntegrationEvidenceMergeConflict,
    merge_integration_evidence_manifests,
)


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


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if effective_argv and effective_argv[0] == "integration-evidence-merge":
        return _run_merge(effective_argv[1:])
    return legacy_cli.main(effective_argv)


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
