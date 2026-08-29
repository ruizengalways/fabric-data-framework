from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from fabric_data_framework.capture.files import (
    FileManifestError,
    FileManifestPolicy,
    FileObjectEvidence,
    FileReadiness,
    assert_same_file_manifest,
    freeze_file_manifest,
)


def _file(
    uri: str,
    version: str,
    *,
    size: int = 10,
    readiness: FileReadiness = FileReadiness.READY,
) -> FileObjectEvidence:
    return FileObjectEvidence(
        source_uri=uri,
        version_token=version,
        size_bytes=size,
        last_modified=datetime(2026, 8, 29, 1, tzinfo=timezone.utc),
        readiness=readiness,
    )


def test_file_evidence_requires_timezone_aware_last_modified():
    with pytest.raises(ValidationError, match="timezone-aware"):
        FileObjectEvidence(
            source_uri="abfss://landing/a.csv",
            version_token="etag-a",
            size_bytes=10,
            last_modified=datetime(2026, 8, 29, 1),
        )


def test_file_manifest_freezes_deterministic_order_and_fingerprint():
    manifest = freeze_file_manifest(
        source_snapshot_ref="landing-listing-42",
        files=(
            _file("abfss://landing/b.csv", "etag-b", size=20),
            _file("abfss://landing/a.csv", "etag-a", size=10),
        ),
        complete_discovery=True,
    )

    assert [item.source_uri for item in manifest.files] == [
        "abfss://landing/a.csv",
        "abfss://landing/b.csv",
    ]
    assert manifest.total_bytes == 30
    same = freeze_file_manifest(
        source_snapshot_ref="landing-listing-42",
        files=tuple(reversed(manifest.files)),
        complete_discovery=True,
    )
    assert manifest.manifest_fingerprint == same.manifest_fingerprint


def test_file_manifest_requires_explicit_complete_discovery():
    with pytest.raises(FileManifestError, match="not proven complete"):
        freeze_file_manifest(
            source_snapshot_ref="listing",
            files=(_file("abfss://landing/a.csv", "v1"),),
            complete_discovery=False,
        )


def test_file_manifest_rejects_in_progress_objects_by_default():
    with pytest.raises(FileManifestError, match="not READY"):
        freeze_file_manifest(
            source_snapshot_ref="listing",
            files=(
                _file(
                    "abfss://landing/a.csv",
                    "v1",
                    readiness=FileReadiness.IN_PROGRESS,
                ),
            ),
            complete_discovery=True,
        )


def test_file_manifest_rejects_duplicate_uri_even_when_version_matches():
    item = _file("abfss://landing/a.csv", "v1")
    with pytest.raises(FileManifestError, match="appears more than once"):
        freeze_file_manifest(
            source_snapshot_ref="listing",
            files=(item, item),
            complete_discovery=True,
        )


def test_file_manifest_rejects_same_uri_with_different_versions():
    with pytest.raises(FileManifestError, match="multiple version tokens"):
        freeze_file_manifest(
            source_snapshot_ref="listing",
            files=(
                _file("abfss://landing/a.csv", "v1"),
                _file("abfss://landing/a.csv", "v2"),
            ),
            complete_discovery=True,
        )


def test_file_manifest_empty_and_volume_guards_are_explicit():
    with pytest.raises(FileManifestError, match="empty"):
        freeze_file_manifest(
            source_snapshot_ref="listing",
            files=(),
            complete_discovery=True,
        )

    empty = freeze_file_manifest(
        source_snapshot_ref="listing",
        files=(),
        complete_discovery=True,
        policy=FileManifestPolicy(allow_empty_manifest=True),
    )
    assert empty.files == ()

    with pytest.raises(FileManifestError, match="max_files=1"):
        freeze_file_manifest(
            source_snapshot_ref="listing",
            files=(
                _file("abfss://landing/a.csv", "v1"),
                _file("abfss://landing/b.csv", "v1"),
            ),
            complete_discovery=True,
            policy=FileManifestPolicy(max_files=1),
        )


def test_retry_manifest_drift_fails_when_version_or_snapshot_changes():
    original = freeze_file_manifest(
        source_snapshot_ref="listing-1",
        files=(_file("abfss://landing/a.csv", "v1"),),
        complete_discovery=True,
    )
    same = freeze_file_manifest(
        source_snapshot_ref="listing-1",
        files=(_file("abfss://landing/a.csv", "v1"),),
        complete_discovery=True,
    )
    assert_same_file_manifest(original, same)

    changed_version = freeze_file_manifest(
        source_snapshot_ref="listing-1",
        files=(_file("abfss://landing/a.csv", "v2"),),
        complete_discovery=True,
    )
    with pytest.raises(FileManifestError, match="changed between attempts"):
        assert_same_file_manifest(original, changed_version)

    changed_snapshot = freeze_file_manifest(
        source_snapshot_ref="listing-2",
        files=(_file("abfss://landing/a.csv", "v1"),),
        complete_discovery=True,
    )
    with pytest.raises(FileManifestError, match="changed between attempts"):
        assert_same_file_manifest(original, changed_snapshot)


def test_manifest_fingerprint_changes_when_object_metadata_changes():
    original = freeze_file_manifest(
        source_snapshot_ref="listing",
        files=(_file("abfss://landing/a.csv", "v1", size=10),),
        complete_discovery=True,
    )
    modified = FileObjectEvidence(
        source_uri="abfss://landing/a.csv",
        version_token="v1",
        size_bytes=10,
        last_modified=datetime(2026, 8, 29, 1, tzinfo=timezone.utc) + timedelta(seconds=1),
        readiness=FileReadiness.READY,
    )
    changed = freeze_file_manifest(
        source_snapshot_ref="listing",
        files=(modified,),
        complete_discovery=True,
    )
    assert original.manifest_fingerprint != changed.manifest_fingerprint
