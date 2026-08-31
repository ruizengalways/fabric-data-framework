"""CLI leaf for approved representative live business-path evidence.

The command only loads exact-release inputs and delegates to reusable evidence code.
It never authors PASS JSON itself and never owns provider/runtime semantics.
"""

from __future__ import annotations

import argparse
import os
import sys

from ..deployment.delivery import load_dataset_configs, load_release_manifest
from ..evidence.approved_business_path_runner import (
    execute_approved_business_path,
    write_approved_business_path_execution_report,
    write_business_path_partial_proof_bundle,
)
from ..evidence.business_path_driver import load_approved_business_path_driver_config
from ..evidence.business_path_evidence import load_approved_business_path_scenario
from ..evidence.integration_evidence import (
    load_integration_evidence_manifest,
    load_integration_evidence_spec,
)
from ..evidence.integration_runner import load_approved_integration_runner_config


BUSINESS_PATH_COMMANDS = frozenset({"candidate-business-path-run"})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fabric-framework candidate-business-path-run")
    parser.add_argument("--runner-config", required=True)
    parser.add_argument("--integration-spec", required=True)
    parser.add_argument("--prerequisite-manifest", required=True)
    parser.add_argument("--release-manifest", required=True)
    parser.add_argument("--config-dir", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--driver-config", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--pipeline-check-id", required=True)
    parser.add_argument(
        "--evidence-reference",
        action="append",
        required=True,
        dest="evidence_references",
        help="Durable retained reference for the approved live path; repeat if needed.",
    )
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--proof-output", required=True)
    parser.add_argument(
        "--allow-pipeline-execution",
        action="store_true",
        help="Explicitly authorize the representative Fabric Pipeline attempt(s).",
    )
    parser.add_argument(
        "--allow-scenario-mutation",
        action="store_true",
        help="Explicitly authorize exact-release driver fixture/fault preparation and cleanup.",
    )
    return parser


def _run(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    try:
        runner_config = load_approved_integration_runner_config(args.runner_config)
        integration_spec = load_integration_evidence_spec(args.integration_spec)
        prerequisite_manifest = load_integration_evidence_manifest(
            args.prerequisite_manifest
        )
        release_manifest = load_release_manifest(args.release_manifest)
        configs = load_dataset_configs(args.config_dir)
        scenario = load_approved_business_path_scenario(
            args.scenario,
            release_manifest=release_manifest,
        )
        driver_config = load_approved_business_path_driver_config(
            args.driver_config,
            release_manifest=release_manifest,
            expected_scenario_hash=scenario.scenario_hash,
        )
        execution = execute_approved_business_path(
            runner_config=runner_config,
            integration_spec=integration_spec,
            prerequisite_manifest=prerequisite_manifest,
            release_manifest=release_manifest,
            configs=configs,
            scenario=scenario,
            driver_config=driver_config,
            candidate_git_sha=args.candidate_sha,
            artifact_sha256=args.artifact_sha256,
            pipeline_check_id=args.pipeline_check_id,
            environ=os.environ,
            evidence_references=tuple(args.evidence_references),
            allow_pipeline_execution=args.allow_pipeline_execution,
            allow_scenario_mutation=args.allow_scenario_mutation,
        )
        write_approved_business_path_execution_report(execution, args.report_output)
        write_business_path_partial_proof_bundle(execution, args.proof_output)
        print(
            f"gate_id={execution.gate_id.value} dataset_id={execution.dataset_id} "
            f"scenario_hash={execution.scenario_hash} status={execution.proof.status.value}"
        )
        return 0
    except (KeyError, OSError, TypeError, ValueError, RuntimeError) as exc:
        # Extension/provider exceptions may carry sensitive environment details. Retain
        # only the exception type at this outer approved-run boundary.
        print(
            f"error: candidate business path execution failed ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 2


def run_if_matched(argv: list[str]) -> int | None:
    if argv and argv[0] == "candidate-business-path-run":
        return _run(argv[1:])
    return None


__all__ = ["BUSINESS_PATH_COMMANDS", "run_if_matched"]
