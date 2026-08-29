"""Immutable file-manifest capture guardrails.

Provider adapters discover files and supply stable object-version evidence.  The
framework freezes that evidence before parsing so retries/replays do not silently
read a different set or a newer version of the same object.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field, model_validator

from ..config import FrozenModel, canonical_hash


class FileManifestError(ValueError):
    pass


class FileReadiness(str, Enum):
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    REJECTED = "REJECTED"


class FileObjectEvidence(FrozenModel):
    source_uri: str = Field(min_length=1)
    version_token: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    last_modified: datetime
    readiness: FileReadiness = FileReadiness.READY

    @model_validator(mode="after")
    def validate_last_modified(self) -> "FileObjectEvidence":
        if self.last_modified.tzinfo is None or self.last_modified.utcoffset() is None:
            raise ValueError("file last_modified must be timezone-aware")
        return self


class FileManifestPolicy(FrozenModel):
    require_complete_discovery: bool = True
    require_ready_files: bool = True
    allow_empty_manifest: bool = False
    max_files: int = Field(default=100_000, gt=0)


class FrozenFileManifest(FrozenModel):
    source_snapshot_ref: str = Field(min_length=1)
    files: tuple[FileObjectEvidence, ...]
    complete_discovery: bool

    @property
    def manifest_fingerprint(self) -> str:
        return canonical_hash(
            {
                "source_snapshot_ref": self.source_snapshot_ref,
                "complete_discovery": self.complete_discovery,
                "files": [item.model_dump(mode="json") for item in self.files],
            }
        )

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self.files)


def freeze_file_manifest(
    *,
    source_snapshot_ref: str,
    files: tuple[FileObjectEvidence, ...],
    complete_discovery: bool,
    policy: FileManifestPolicy | None = None,
) -> FrozenFileManifest:
    """Validate and deterministically freeze one provider-discovered file set."""

    effective = policy or FileManifestPolicy()
    if effective.require_complete_discovery and not complete_discovery:
        raise FileManifestError("file discovery is not proven complete")
    if not files and not effective.allow_empty_manifest:
        raise FileManifestError("empty file manifest is not authorized")
    if len(files) > effective.max_files:
        raise FileManifestError(
            f"file manifest contains {len(files)} objects; max_files={effective.max_files}"
        )

    by_uri: dict[str, FileObjectEvidence] = {}
    for item in files:
        if item.source_uri in by_uri:
            prior = by_uri[item.source_uri]
            if prior.version_token != item.version_token:
                raise FileManifestError(
                    f"file {item.source_uri!r} was discovered with multiple version tokens"
                )
            raise FileManifestError(f"file {item.source_uri!r} appears more than once")
        if effective.require_ready_files and item.readiness is not FileReadiness.READY:
            raise FileManifestError(
                f"file {item.source_uri!r} is not READY: {item.readiness.value}"
            )
        by_uri[item.source_uri] = item

    return FrozenFileManifest(
        source_snapshot_ref=source_snapshot_ref,
        files=tuple(by_uri[key] for key in sorted(by_uri)),
        complete_discovery=complete_discovery,
    )


def assert_same_file_manifest(
    expected: FrozenFileManifest,
    observed: FrozenFileManifest,
) -> None:
    """Fail when a retry/replay resolves to different immutable file evidence."""

    if expected.manifest_fingerprint != observed.manifest_fingerprint:
        raise FileManifestError(
            "file manifest changed between attempts; refuse to read a different file set/version"
        )


__all__ = [
    "FileManifestError",
    "FileManifestPolicy",
    "FileObjectEvidence",
    "FileReadiness",
    "FrozenFileManifest",
    "assert_same_file_manifest",
    "freeze_file_manifest",
]
