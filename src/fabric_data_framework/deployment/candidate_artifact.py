"""Dependency-light exact candidate wheel identity contract.

This module is intentionally standard-library only so CI/release workflows can verify
candidate bytes before installing or trusting the wheel itself.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from email.parser import Parser
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile


CANDIDATE_ARTIFACT_SCHEMA_VERSION = 1
_PACKAGE_NAME = "fabric-data-framework"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class CandidateArtifactManifest:
    schema_version: int
    package_name: str
    framework_version: str
    candidate_git_sha: str
    workflow_run_id: int
    workflow_run_attempt: int
    wheel_filename: str
    wheel_sha256: str

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "CandidateArtifactManifest":
        expected = {
            "schema_version",
            "package_name",
            "framework_version",
            "candidate_git_sha",
            "workflow_run_id",
            "workflow_run_attempt",
            "wheel_filename",
            "wheel_sha256",
        }
        if set(payload) != expected:
            missing = sorted(expected - set(payload))
            extra = sorted(set(payload) - expected)
            raise ValueError(
                f"candidate manifest keys mismatch: missing={missing}, extra={extra}"
            )
        manifest = cls(
            schema_version=_require_int(payload["schema_version"], "schema_version"),
            package_name=_require_str(payload["package_name"], "package_name"),
            framework_version=_require_str(
                payload["framework_version"], "framework_version"
            ),
            candidate_git_sha=_require_str(
                payload["candidate_git_sha"], "candidate_git_sha"
            ),
            workflow_run_id=_require_int(payload["workflow_run_id"], "workflow_run_id"),
            workflow_run_attempt=_require_int(
                payload["workflow_run_attempt"], "workflow_run_attempt"
            ),
            wheel_filename=_require_str(payload["wheel_filename"], "wheel_filename"),
            wheel_sha256=_require_str(payload["wheel_sha256"], "wheel_sha256"),
        )
        _validate_manifest_fields(manifest)
        return manifest


def _require_str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _validate_manifest_fields(manifest: CandidateArtifactManifest) -> None:
    if manifest.schema_version != CANDIDATE_ARTIFACT_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported candidate manifest schema_version {manifest.schema_version}"
        )
    if manifest.package_name != _PACKAGE_NAME:
        raise ValueError(f"candidate package_name must be {_PACKAGE_NAME!r}")
    if not manifest.framework_version or len(manifest.framework_version) > 64:
        raise ValueError("framework_version is invalid")
    if _SHA_RE.fullmatch(manifest.candidate_git_sha) is None:
        raise ValueError("candidate_git_sha must be a 40-character lowercase git SHA")
    if _SHA256_RE.fullmatch(manifest.wheel_sha256) is None:
        raise ValueError("wheel_sha256 must be a 64-character lowercase SHA256")
    wheel_path = Path(manifest.wheel_filename)
    if wheel_path.name != manifest.wheel_filename or wheel_path.suffix != ".whl":
        raise ValueError("wheel_filename must be a plain .whl filename")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wheel_identity(path: Path) -> tuple[str, str]:
    if not path.is_file() or path.suffix != ".whl":
        raise ValueError(f"candidate wheel does not exist: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_paths = [
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_paths) != 1:
                raise ValueError(
                    f"candidate wheel must contain exactly one METADATA file; found {len(metadata_paths)}"
                )
            raw = archive.read(metadata_paths[0]).decode("utf-8")
    except zipfile.BadZipFile as exc:
        raise ValueError("candidate wheel is not a valid wheel ZIP archive") from exc
    metadata = Parser().parsestr(raw)
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise ValueError("candidate wheel METADATA must contain Name and Version")
    return name, version


def _single_wheel(dist_dir: Path) -> Path:
    wheels = sorted(path for path in dist_dir.glob("*.whl") if path.is_file())
    if len(wheels) != 1:
        raise ValueError(
            f"candidate dist directory must contain exactly one wheel; found {len(wheels)}"
        )
    return wheels[0]


def create_candidate_artifact_manifest(
    dist_dir: str | Path,
    *,
    candidate_git_sha: str,
    workflow_run_id: int,
    workflow_run_attempt: int,
) -> CandidateArtifactManifest:
    root = Path(dist_dir)
    wheel = _single_wheel(root)
    package_name, framework_version = _wheel_identity(wheel)
    manifest = CandidateArtifactManifest(
        schema_version=CANDIDATE_ARTIFACT_SCHEMA_VERSION,
        package_name=package_name,
        framework_version=framework_version,
        candidate_git_sha=candidate_git_sha,
        workflow_run_id=workflow_run_id,
        workflow_run_attempt=workflow_run_attempt,
        wheel_filename=wheel.name,
        wheel_sha256=sha256_file(wheel),
    )
    _validate_manifest_fields(manifest)
    return manifest


def load_candidate_artifact_manifest(path: str | Path) -> CandidateArtifactManifest:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("candidate manifest is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("candidate manifest JSON must be an object")
    return CandidateArtifactManifest.from_dict(payload)


def write_candidate_artifact_manifest(
    manifest: CandidateArtifactManifest, path: str | Path
) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_candidate_artifact(
    dist_dir: str | Path,
    manifest: CandidateArtifactManifest,
    *,
    expected_candidate_git_sha: str,
    expected_workflow_run_id: int,
    expected_workflow_run_attempt: int | None = None,
    expected_framework_version: str | None = None,
    expected_wheel_sha256: str | None = None,
) -> CandidateArtifactManifest:
    _validate_manifest_fields(manifest)
    if manifest.candidate_git_sha != expected_candidate_git_sha:
        raise ValueError("candidate manifest git SHA does not match expected candidate")
    if manifest.workflow_run_id != expected_workflow_run_id:
        raise ValueError("candidate manifest workflow run ID does not match expected run")
    if (
        expected_workflow_run_attempt is not None
        and manifest.workflow_run_attempt != expected_workflow_run_attempt
    ):
        raise ValueError("candidate manifest workflow run attempt does not match expected run")
    if (
        expected_framework_version is not None
        and manifest.framework_version != expected_framework_version
    ):
        raise ValueError("candidate manifest framework version does not match expected version")
    if expected_wheel_sha256 is not None:
        if _SHA256_RE.fullmatch(expected_wheel_sha256) is None:
            raise ValueError("expected wheel SHA256 is invalid")
        if manifest.wheel_sha256 != expected_wheel_sha256:
            raise ValueError("candidate manifest wheel SHA256 does not match expected SHA256")

    wheel = Path(dist_dir) / manifest.wheel_filename
    actual_sha256 = sha256_file(wheel)
    if actual_sha256 != manifest.wheel_sha256:
        raise ValueError("candidate wheel bytes do not match manifest SHA256")
    package_name, framework_version = _wheel_identity(wheel)
    if package_name != manifest.package_name:
        raise ValueError("candidate wheel package name does not match manifest")
    if framework_version != manifest.framework_version:
        raise ValueError("candidate wheel version does not match manifest")
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="candidate-artifact")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--dist-dir", required=True)
    create.add_argument("--candidate-sha", required=True)
    create.add_argument("--workflow-run-id", required=True, type=int)
    create.add_argument("--workflow-run-attempt", required=True, type=int)
    create.add_argument("--output", required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--dist-dir", required=True)
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--candidate-sha", required=True)
    verify.add_argument("--workflow-run-id", required=True, type=int)
    verify.add_argument("--workflow-run-attempt", type=int)
    verify.add_argument("--expected-version")
    verify.add_argument("--expected-wheel-sha256")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            manifest = create_candidate_artifact_manifest(
                args.dist_dir,
                candidate_git_sha=args.candidate_sha,
                workflow_run_id=args.workflow_run_id,
                workflow_run_attempt=args.workflow_run_attempt,
            )
            write_candidate_artifact_manifest(manifest, args.output)
            print(json.dumps(asdict(manifest), sort_keys=True))
            return 0
        manifest = load_candidate_artifact_manifest(args.manifest)
        verified = verify_candidate_artifact(
            args.dist_dir,
            manifest,
            expected_candidate_git_sha=args.candidate_sha,
            expected_workflow_run_id=args.workflow_run_id,
            expected_workflow_run_attempt=args.workflow_run_attempt,
            expected_framework_version=args.expected_version,
            expected_wheel_sha256=args.expected_wheel_sha256,
        )
        print(json.dumps(asdict(verified), sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CANDIDATE_ARTIFACT_SCHEMA_VERSION",
    "CandidateArtifactManifest",
    "create_candidate_artifact_manifest",
    "load_candidate_artifact_manifest",
    "main",
    "sha256_file",
    "verify_candidate_artifact",
    "write_candidate_artifact_manifest",
]
