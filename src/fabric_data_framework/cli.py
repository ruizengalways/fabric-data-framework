"""Small provider-neutral CLI used by CI/CD runners and operator validation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from sqlalchemy import create_engine

from . import __version__
from .capture import load_capture_selections, validate_capture_selection
from .control_plane import apply_baseline_schema, current_schema_version
from .delivery import (
    build_release_manifest,
    load_dataset_configs,
    load_environment_bindings,
    load_release_manifest,
    materialize_semantic_metadata,
    plan_deployment,
    record_deployment_history,
    validate_release_tag,
    write_json_model,
)
from .deployment import CIProvider, DeploymentMechanism, DeploymentProvenance
from .operator import get_dataset_operational_snapshot, list_dataset_operational_snapshots


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-framework")
    subparsers = parser.add_subparsers(dest="command", required=True)

    tag = subparsers.add_parser("validate-tag", help="Verify vX.Y.Z tag matches package version")
    tag.add_argument("--tag", required=True)
    tag.add_argument("--version", default=__version__)

    migrate = subparsers.add_parser("control-plane-migrate")
    migrate.add_argument("--database-url", required=True)

    status = subparsers.add_parser(
        "control-plane-status",
        help="Read typed dataset operational status without mutating control-plane state",
    )
    status.add_argument("--database-url", required=True)
    status.add_argument("--dataset-id")
    status.add_argument("--output")

    onboarding = subparsers.add_parser(
        "capture-onboarding-validate",
        help="Validate source-controlled capture-pattern/history/delete claims",
    )
    onboarding.add_argument("--config-dir", required=True)
    onboarding.add_argument("--selections", required=True)
    onboarding.add_argument(
        "--require-all",
        action="store_true",
        help="Require every DatasetConfig in config-dir to have a capture selection",
    )
    onboarding.add_argument("--output")

    materialize = subparsers.add_parser("metadata-materialize")
    materialize.add_argument("--database-url", required=True)
    materialize.add_argument("--config-dir", required=True)
    materialize.add_argument("--domain", required=True)
    materialize.add_argument("--domain-git-sha", required=True)
    materialize.add_argument("--framework-version", default=__version__)

    release = subparsers.add_parser("release-manifest")
    release.add_argument("--domain", required=True)
    release.add_argument("--domain-release-version", required=True)
    release.add_argument("--domain-git-sha", required=True)
    release.add_argument("--framework-version", default=__version__)
    release.add_argument("--config-dir", required=True)
    release.add_argument("--config-schema-version", type=int, default=1)
    release.add_argument("--fabric-item-manifest-version", default="none-v1")
    release.add_argument("--build-id", required=True)
    release.add_argument("--artifact", action="append", default=[], metavar="NAME=PATH")
    release.add_argument("--output", required=True)

    plan = subparsers.add_parser("deployment-plan")
    plan.add_argument("--manifest", required=True)
    plan.add_argument("--bindings", required=True)
    plan.add_argument("--output", required=True)

    record = subparsers.add_parser("deployment-record")
    record.add_argument("--database-url", required=True)
    record.add_argument("--manifest", required=True)
    record.add_argument("--bindings", required=True)
    record.add_argument(
        "--mechanism",
        choices=[value.value for value in DeploymentMechanism],
        required=True,
    )
    record.add_argument("--ci-provider", choices=[value.value for value in CIProvider], required=True)
    record.add_argument("--initiated-by", required=True)
    record.add_argument("--approved-by")
    record.add_argument("--status", default="SUCCEEDED")

    return parser


def _artifacts(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--artifact must use NAME=PATH")
        name, raw_path = value.split("=", 1)
        if not name or not raw_path:
            raise ValueError("--artifact must use non-empty NAME=PATH")
        result[name] = Path(raw_path)
    return result


def _write_or_print_json(payload: object, output: str | None) -> None:
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(mode="json")  # type: ignore[attr-defined]
    else:
        data = [item.model_dump(mode="json") for item in payload]  # type: ignore[union-attr]
    rendered = json.dumps(data, indent=2, sort_keys=True, default=str) + "\n"
    if output is None:
        print(rendered, end="")
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-tag":
            validate_release_tag(args.tag, args.version)
            print(f"validated {args.tag} for package version {args.version}")
            return 0

        if args.command == "control-plane-migrate":
            engine = create_engine(args.database_url)
            apply_baseline_schema(engine)
            print(f"control-plane schema version={current_schema_version(engine)}")
            return 0

        if args.command == "control-plane-status":
            engine = create_engine(args.database_url)
            if args.dataset_id:
                payload = get_dataset_operational_snapshot(engine, args.dataset_id)
            else:
                payload = list_dataset_operational_snapshots(engine)
            _write_or_print_json(payload, args.output)
            return 0

        if args.command == "capture-onboarding-validate":
            configs = load_dataset_configs(args.config_dir)
            configs_by_id = {item.dataset_id: item for item in configs}
            selections = load_capture_selections(args.selections)
            reports = []
            for selection in selections:
                config = configs_by_id.get(selection.dataset_id)
                if config is None:
                    raise ValueError(
                        f"capture selection references unknown dataset {selection.dataset_id!r}"
                    )
                reports.append(validate_capture_selection(config, selection))
            if args.require_all:
                selected_ids = {item.dataset_id for item in selections}
                missing = sorted(set(configs_by_id) - selected_ids)
                if missing:
                    raise ValueError(
                        "DatasetConfig values missing capture selection: " + ", ".join(missing)
                    )
            _write_or_print_json(tuple(reports), args.output)
            return 0

        if args.command == "metadata-materialize":
            engine = create_engine(args.database_url)
            configs = load_dataset_configs(args.config_dir)
            bundle_hash = materialize_semantic_metadata(
                engine,
                configs=configs,
                domain=args.domain,
                domain_git_sha=args.domain_git_sha,
                framework_version=args.framework_version,
            )
            print(f"materialized datasets={len(configs)} config_bundle_hash={bundle_hash}")
            return 0

        if args.command == "release-manifest":
            configs = load_dataset_configs(args.config_dir)
            manifest = build_release_manifest(
                domain=args.domain,
                domain_release_version=args.domain_release_version,
                domain_git_sha=args.domain_git_sha,
                framework_version=args.framework_version,
                configs=configs,
                config_schema_version=args.config_schema_version,
                fabric_item_manifest_version=args.fabric_item_manifest_version,
                build_id=args.build_id,
                artifacts=_artifacts(args.artifact),
            )
            write_json_model(manifest, args.output)
            print(f"release_hash={manifest.bundle.release_hash}")
            return 0

        if args.command == "deployment-plan":
            manifest = load_release_manifest(args.manifest)
            bindings = load_environment_bindings(args.bindings)
            plan = plan_deployment(manifest, bindings)
            write_json_model(plan, args.output)
            print(
                f"planned environment={bindings.environment.value} "
                f"release_hash={plan.release_hash} steps={len(plan.steps)}"
            )
            return 0

        if args.command == "deployment-record":
            manifest = load_release_manifest(args.manifest)
            bindings = load_environment_bindings(args.bindings)
            provenance = DeploymentProvenance(
                environment=bindings.environment,
                domain=manifest.domain,
                bundle=manifest.bundle,
                deployment_mechanism=DeploymentMechanism(args.mechanism),
                ci_provider=CIProvider(args.ci_provider),
                initiated_by=args.initiated_by,
                approved_by=args.approved_by,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                status=args.status,
            )
            record_deployment_history(create_engine(args.database_url), provenance)
            print(f"deployment_id={provenance.deployment_id}")
            return 0

        raise AssertionError(f"unhandled command {args.command}")
    except (KeyError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
