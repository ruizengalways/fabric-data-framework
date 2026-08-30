"""Developer-time customer project CLI commands."""

from __future__ import annotations

import argparse
import json
import sys

from ..deployment.project import initialize_customer_project


_COMMANDS = frozenset({"project-init"})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-framework project-init")
    parser.add_argument("path", help="Target customer/domain repository path")
    parser.add_argument("--domain", required=True, help="Stable lowercase domain id, e.g. health")
    parser.add_argument(
        "--allow-existing",
        action="store_true",
        help="Fill missing scaffold files in an existing repository without overwriting files",
    )
    return parser


def run_if_matched(argv: list[str]) -> int | None:
    """Run a project command when the first argument belongs to this command family."""

    if not argv or argv[0] not in _COMMANDS:
        return None

    command = argv[0]
    try:
        if command == "project-init":
            args = _parser().parse_args(argv[1:])
            result = initialize_customer_project(
                args.path,
                domain=args.domain,
                allow_existing=args.allow_existing,
            )
            print(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))
            return 0
        raise AssertionError(f"unhandled project command {command}")
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


__all__ = ["run_if_matched"]
