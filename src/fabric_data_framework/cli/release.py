"""Release-candidate readiness CLI commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fabric_data_framework.evidence.integration_evidence import load_integration_evidence_manifest
from fabric_data_framework.evidence.release_readiness import (
    evaluate_release_readiness,
    load_release_readiness_proofs,
    load_release_readiness_spec,
)


_COMMANDS = frozenset({"release-readiness"})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-framework release-readiness")
    parser.add_argument("--spec", required=True, help="Release readiness specification JSON")
    parser.add_argument(
        "--candidate-sha",
        required=True,
        help="Exact 40-character lowercase git SHA being evaluated",
    )
    parser.add_argument(
        "--artifact-sha256",
        help="Exact candidate wheel/artifact SHA256; required with integration evidence",
    )
    parser.add_argument("--proofs", help="Retained non-integration release proof bundle JSON")
    parser.add_argument(
        "--integration-evidence",
        help="Retained IntegrationEvidenceManifest JSON for integration-backed gates",
    )
    parser.add_argument("--output", help="Optional JSON report output path")
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit non-zero unless every required release gate is PASS",
    )
    return parser


def _render(payload: object, output: str | None) -> None:
    data = payload.model_dump(mode="json")  # type: ignore[attr-defined]
    rendered = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(rendered, end="")
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def run_if_matched(argv: list[str]) -> int | None:
    if not argv or argv[0] not in _COMMANDS:
        return None

    try:
        args = _parser().parse_args(argv[1:])
        spec = load_release_readiness_spec(args.spec)
        proofs = load_release_readiness_proofs(args.proofs) if args.proofs else None
        integration = (
            load_integration_evidence_manifest(args.integration_evidence)
            if args.integration_evidence
            else None
        )
        report = evaluate_release_readiness(
            spec,
            candidate_git_sha=args.candidate_sha,
            artifact_sha256=args.artifact_sha256,
            proofs=proofs,
            integration_evidence=integration,
        )
        _render(report, args.output)
        if args.require_ready and not report.release_ready:
            print(
                "error: release candidate is blocked; required gates not PASS: "
                + ", ".join(report.blockers),
                file=sys.stderr,
            )
            return 2
        return 0
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


__all__ = ["run_if_matched"]
