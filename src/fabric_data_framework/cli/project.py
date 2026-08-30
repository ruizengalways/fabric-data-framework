"""Developer-time customer project CLI commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ..deployment.project import initialize_customer_project, validate_customer_project


_COMMANDS = frozenset({"project-init", "project-validate"})


def _init_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-framework project-init")
    parser.add_argument("path", help="Target customer/domain repository path")
    parser.add_argument("--domain", required=True, help="Stable lowercase domain id, e.g. health")
    parser.add_argument(
        "--allow-existing",
        action="store_true",
        help="Fill missing scaffold files in an existing repository without overwriting files",
    )
    return parser


def _validate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-framework project-validate")
    parser.add_argument("path", help="Customer/domain repository root")
    parser.add_argument(
        "--semantic-selections",
        help=(
            "Semantic selection JSON path. Defaults to "
            "<project>/config/capture/semantic-selections.json."
        ),
    )
    parser.add_argument("--output", help="Optional JSON report output path")
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
    """Run a project command when the first argument belongs to this command family."""

    if not argv or argv[0] not in _COMMANDS:
        return None

    command = argv[0]
    try:
        if command == "project-init":
            args = _init_parser().parse_args(argv[1:])
            result = initialize_customer_project(
                args.path,
                domain=args.domain,
                allow_existing=args.allow_existing,
            )
            _render(result, None)
            return 0
        if command == "project-validate":
            args = _validate_parser().parse_args(argv[1:])
            report = validate_customer_project(
                args.path,
                semantic_selections=args.semantic_selections,
            )
            _render(report, args.output)
            return 0
        raise AssertionError(f"unhandled project command {command}")
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


__all__ = ["run_if_matched"]
