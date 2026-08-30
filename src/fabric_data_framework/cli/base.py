"""Provider-neutral base CLI commands.

This module is a presentation layer over the reusable framework. Core package
modules must never import from ``fabric_data_framework.cli``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine

from .. import __version__
from ..adapters.fabric.rest import FabricRestClient
from ..capture import (
    load_capture_selections,
    load_semantic_capture_selections,
    validate_capture_selection,
    validate_semantic_capture_selection,
)
from ..control_plane import apply_baseline_schema, current_schema_version
from ..control_plane_certification import (
    CONTROL_PLANE_BACKEND_PROFILES,
    ControlPlaneExternalEvidence,
    certify_control_plane_backend,
    get_control_plane_backend_profile,
)
from ..delivery import (
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
from ..deployment import CIProvider, DeploymentMechanism, DeploymentProvenance
from ..fabric_auth import EnvironmentAccessTokenProvider
from ..integration_checks import run_fabric_item_read_check
from ..integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceStatus,
    load_integration_evidence_manifest,
    load_integration_evidence_spec,
    run_integration_evidence,
    validate_integration_evidence_manifest,
    write_integration_evidence_manifest,
)
from ..integration_runner import (
    build_approved_integration_run_plan,
    load_approved_integration_runner_config,
)
from ..operator import get_dataset_operational_snapshot, list_dataset_operational_snapshots


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

    certify = subparsers.add_parser(
        "control-plane-certify",
        help="Evaluate schema, CAS conformance and external production evidence",
    )
    certify.add_argument("--database-url", required=True)
    certify.add_argument(
        "--profile",
        choices=sorted(CONTROL_PLANE_BACKEND_PROFILES),
        required=True,
    )
    certify.add_argument(
        "--run-conformance",
        action="store_true",
        help=(
            "Run temporary write/rollback/CAS probes. Use only in an approved certification "
            "database or environment."
        ),
    )
    certify.add_argument(
        "--external-evidence",
        help="JSON file containing references to IAM/network/restore/HA/monitoring/retention evidence",
    )
    certify.add_argument(
        "--require-reference-certified",
        action="store_true",
        help="Exit non-zero unless deterministic conformance is fully certified",
    )
    certify.add_argument(
        "--require-production-certified",
        action="store_true",
        help="Exit non-zero unless production profile, conformance and external evidence all pass",
    )
    certify.add_argument("--output")

    integration = subparsers.add_parser(
        "integration-evidence-validate",
        help="Validate a retained approved-environment evidence manifest against its exact spec",
    )
    integration.add_argument("--spec", required=True)
    integration.add_argument("--manifest", required=True)
    integration.add_argument(
        "--require-certified",
        action="store_true",
        help="Exit non-zero unless every required integration check is PASS",
    )

    preflight = subparsers.add_parser(
        "integration-run-preflight",
        help=(
            "Validate exact-release physical bindings and runtime prerequisite presence "
            "without persisting secret values"
        ),
    )
    preflight.add_argument("--config", required=True)
    preflight.add_argument("--spec", required=True)
    preflight.add_argument(
        "--check-id",
        action="append",
        default=None,
        help=(
            "Plan only this evidence check; repeat for a staged subset. "
            "Default plans all required checks."
        ),
    )
    preflight.add_argument(
        "--allow-mutating-checks",
        action="store_true",
        help=(
            "Explicitly authorize a preflight plan containing remote execution/write checks. "
            "This flag does not itself execute those checks."
        ),
    )
    preflight.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit non-zero unless all runtime prerequisites exist and mutation is authorized",
    )
    preflight.add_argument("--output")

    item_smoke = subparsers.add_parser(
        "integration-item-smoke-run",
        help="Execute one read-only Fabric item identity/authorization smoke and retain a partial manifest",
    )
    item_smoke.add_argument("--config", required=True)
    item_smoke.add_argument("--spec", required=True)
    item_smoke.add_argument("--check-id", required=True)
    item_smoke.add_argument("--evidence-reference", required=True)
    item_smoke.add_argument("--output", required=True)

    onboarding = subparsers.add_parser(
        "capture-onboarding-validate",
        help="Validate source-controlled legacy capture-pattern/history/delete claims",
    )
    onboarding.add_argument("--config-dir", required=True)
    onboarding.add_argument("--selections", required=True)
    onboarding.add_argument(
        "--require-all",
        action="store_true",
        help="Require every DatasetConfig in config-dir to have a capture selection",
    )
    onboarding.add_argument("--output")

    semantic_onboarding = subparsers.add_parser(
        "capture-semantic-onboarding-validate",
        help="Validate cheatsheet-aligned source/Bronze/history semantic selections",
    )
    semantic_onboarding.add_argument("--config-dir", required=True)
    semantic_onboarding.add_argument("--selections", required=True)
    semantic_onboarding.add_argument(
        "--require-all",
        action="store_true",
        help="Require every DatasetConfig in config-dir to have a semantic capture selection",
    )
    semantic_onboarding.add_argument("--output")

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

        if args.command == "control-plane-certify":
            if args.require_production_certified and not args.run_conformance:
                raise ValueError("--require-production-certified requires --run-conformance")
            evidence = (
                ControlPlaneExternalEvidence.from_json_file(args.external_evidence)
                if args.external_evidence
                else None
            )
            report = certify_control_plane_backend(
                create_engine(args.database_url),
                profile=get_control_plane_backend_profile(args.profile),
                run_conformance=args.run_conformance,
                external_evidence=evidence,
            )
            _write_or_print_json(report, args.output)
            if args.require_production_certified and not report.production_certified:
                raise ValueError("control plane is not production-certified")
            if args.require_reference_certified and not report.reference_certified:
                raise ValueError("control plane is not reference-certified")
            return 0

        if args.command == "integration-evidence-validate":
            spec = load_integration_evidence_spec(args.spec)
            manifest = load_integration_evidence_manifest(args.manifest)
            validate_integration_evidence_manifest(
                spec,
                manifest,
                require_certified=args.require_certified,
            )
            print(
                f"integration_evidence_id={manifest.evidence_id} "
                f"manifest_hash={manifest.manifest_hash} "
                f"certified={str(manifest.certified).lower()}"
            )
            return 0

        if args.command == "integration-run-preflight":
            config = load_approved_integration_runner_config(args.config)
            spec = load_integration_evidence_spec(args.spec)
            plan = build_approved_integration_run_plan(
                config,
                spec,
                environ=os.environ,
                selected_check_ids=args.check_id,
                allow_mutating_checks=args.allow_mutating_checks,
            )
            _write_or_print_json(plan, args.output)
            if args.require_ready and not plan.ready:
                reasons = []
                if plan.missing_runtime_env_vars:
                    reasons.append(
                        "missing runtime env vars=" + ",".join(plan.missing_runtime_env_vars)
                    )
                if plan.mutating_check_ids and not plan.mutating_checks_authorized:
                    reasons.append("mutating checks not explicitly authorized")
                raise ValueError("integration run preflight is not ready: " + "; ".join(reasons))
            return 0

        if args.command == "integration-item-smoke-run":
            config = load_approved_integration_runner_config(args.config)
            spec = load_integration_evidence_spec(args.spec)
            plan = build_approved_integration_run_plan(
                config,
                spec,
                environ=os.environ,
                selected_check_ids=(args.check_id,),
                allow_mutating_checks=False,
            )
            if not plan.ready:
                raise ValueError(
                    "read-only item smoke preflight is not ready; missing runtime env vars="
                    + ",".join(plan.missing_runtime_env_vars)
                )
            check_by_id = {item.check_id: item for item in spec.checks}
            check = check_by_id[args.check_id]
            if check.kind is not IntegrationEvidenceCheckKind.FABRIC_ITEM_READ:
                raise ValueError("integration-item-smoke-run requires FABRIC_ITEM_READ check kind")
            if len(plan.bindings) != 1:
                raise ValueError("read-only item smoke requires exactly one physical binding")
            binding = plan.bindings[0]
            if binding.workspace_id is None or binding.item_id is None:
                raise ValueError("read-only item smoke binding is incomplete")
            client = FabricRestClient(
                token_provider=EnvironmentAccessTokenProvider(
                    env_var=config.fabric_access_token_env_var
                )
            )
            manifest = run_integration_evidence(
                spec,
                runners={
                    args.check_id: lambda: run_fabric_item_read_check(
                        client=client,
                        check_id=args.check_id,
                        workspace_id=binding.workspace_id,
                        item_id=binding.item_id,
                        evidence_references=(args.evidence_reference,),
                    )
                },
            )
            write_integration_evidence_manifest(manifest, args.output)
            result = next(item for item in manifest.results if item.check_id == args.check_id)
            print(
                f"integration_evidence_id={manifest.evidence_id} "
                f"check_id={result.check_id} status={result.status.value} "
                f"manifest_hash={manifest.manifest_hash}"
            )
            if result.status is not IntegrationEvidenceStatus.PASS:
                raise ValueError("read-only Fabric item smoke did not PASS")
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

        if args.command == "capture-semantic-onboarding-validate":
            configs = load_dataset_configs(args.config_dir)
            configs_by_id = {item.dataset_id: item for item in configs}
            selections = load_semantic_capture_selections(args.selections)
            reports = []
            for selection in selections:
                config = configs_by_id.get(selection.dataset_id)
                if config is None:
                    raise ValueError(
                        f"semantic capture selection references unknown dataset {selection.dataset_id!r}"
                    )
                reports.append(validate_semantic_capture_selection(config, selection))
            if args.require_all:
                selected_ids = {item.dataset_id for item in selections}
                missing = sorted(set(configs_by_id) - selected_ids)
                if missing:
                    raise ValueError(
                        "DatasetConfig values missing semantic capture selection: "
                        + ", ".join(missing)
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


__all__ = ["main"]
