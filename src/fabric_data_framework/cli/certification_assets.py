"""CLI boundary for framework-owned Fabric certification asset bootstrap."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from uuid import UUID

from fabric_data_framework.adapters.fabric.auth import EnvironmentAccessTokenProvider
from fabric_data_framework.certification.fabric_assets import FabricCertificationAssetClient
from fabric_data_framework.certification.simple import DEFAULT_CERTIFICATION_ROOT
from fabric_data_framework.deployment.candidate_artifact import (
    load_candidate_artifact_manifest,
)


_COMMAND = "bootstrap-certification-assets"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"fabric-framework {_COMMAND}")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--lakehouse-id", required=True)
    parser.add_argument("--candidate-manifest", required=True)
    parser.add_argument("--candidate-wheel", required=True)
    parser.add_argument("--control-plane-sql-server", required=True)
    parser.add_argument("--control-plane-sql-database", required=True)
    parser.add_argument("--warehouse-sql-server", required=True)
    parser.add_argument("--warehouse-sql-database", required=True)
    parser.add_argument(
        "--certification-root",
        default=str(DEFAULT_CERTIFICATION_ROOT),
    )
    parser.add_argument(
        "--dependency-wheel",
        action="append",
        default=[],
        help=(
            "Optional exact dependency wheel to upload into the Fabric Environment. "
            "Repeat for an explicitly reviewed offline/protected-workspace bundle."
        ),
    )
    parser.add_argument("--access-token-env-var", default="FABRIC_ACCESS_TOKEN")
    parser.add_argument(
        "--allow-item-mutation",
        action="store_true",
        help=(
            "Authorize create/updateDefinition and Environment publish. Without this "
            "flag the command only verifies already-existing exact named items."
        ),
    )
    parser.add_argument("--lro-timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--output")
    return parser


def _run(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = load_candidate_artifact_manifest(args.candidate_manifest)
        client = FabricCertificationAssetClient(
            token_provider=EnvironmentAccessTokenProvider(
                env_var=args.access_token_env_var,
            ),
            lro_timeout_seconds=args.lro_timeout_seconds,
        )
        report = client.bootstrap(
            workspace_id=UUID(args.workspace_id),
            lakehouse_id=UUID(args.lakehouse_id),
            candidate_manifest=manifest,
            candidate_wheel_path=args.candidate_wheel,
            control_plane_sql_server=args.control_plane_sql_server,
            control_plane_sql_database=args.control_plane_sql_database,
            warehouse_sql_server=args.warehouse_sql_server,
            warehouse_sql_database=args.warehouse_sql_database,
            certification_root=args.certification_root,
            allow_item_mutation=args.allow_item_mutation,
            dependency_wheels=tuple(args.dependency_wheel),
        )
        rendered = json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n"
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return 0
    except PermissionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, TypeError) as exc:
        print(
            f"error: Fabric certification asset bootstrap failed ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 2


def run_if_matched(argv: list[str]) -> int | None:
    if argv and argv[0] == _COMMAND:
        return _run(argv[1:])
    return None


__all__ = ["run_if_matched"]
