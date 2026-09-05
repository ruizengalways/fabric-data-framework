"""Governed data-plane storage for detailed row-quarantine payloads.

The relational Control Plane intentionally stores only immutable quarantine lineage,
summary counts/reasons and a ``source_reference``.  Full business rows (which may
contain PII or large values) remain in an explicitly selected governed data-plane root.

``JsonFileQuarantineStore`` is deliberately filesystem based so the same contract works
for local development and Microsoft Fabric Lakehouse mounts such as
``/lakehouse/default/Files/...``.  Enterprise deployments can provide another writer
that implements ``QuarantinePayloadWriter`` without changing Control Plane semantics.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol, Sequence, runtime_checkable
from urllib.parse import unquote, urlparse
from uuid import UUID

from fabric_data_framework.contracts.replay import (
    QuarantineBatchEvidence,
    QuarantineReplayPayload,
    QuarantineReplayPayloadProvider,
)
from fabric_data_framework.quality.rules import QuarantinedRecord


PAYLOAD_SCHEMA_VERSION = 1


class QuarantinePayloadError(RuntimeError):
    """Raised when detailed quarantine payload evidence is missing or inconsistent."""


@runtime_checkable
class QuarantinePayloadWriter(Protocol):
    """Persist detailed quarantined rows and return a stable non-secret reference."""

    def write_payload(
        self,
        *,
        quarantine_id: UUID,
        dataset_run_id: UUID,
        dataset_id: str,
        rows: Sequence[QuarantinedRecord],
    ) -> str: ...


class JsonFileQuarantineStore(QuarantinePayloadWriter, QuarantineReplayPayloadProvider):
    """Immutable JSON quarantine payloads rooted in one approved data-plane directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise QuarantinePayloadError(f"quarantine root is not a directory: {self.root}")

    def _path(self, quarantine_id: UUID) -> Path:
        # Identity-derived filenames avoid allowing dataset/business values to shape paths.
        return self.root / f"{quarantine_id}.json"

    def write_payload(
        self,
        *,
        quarantine_id: UUID,
        dataset_run_id: UUID,
        dataset_id: str,
        rows: Sequence[QuarantinedRecord],
    ) -> str:
        if not dataset_id.strip():
            raise QuarantinePayloadError("dataset_id cannot be empty")
        if not rows:
            raise QuarantinePayloadError("detailed quarantine payload requires at least one row")
        for item in rows:
            if item.record.dataset_run_id != dataset_run_id:
                raise QuarantinePayloadError(
                    "quarantined row dataset_run_id does not match payload dataset_run_id"
                )
            if len(item.reason_codes) != len(item.reason_messages):
                raise QuarantinePayloadError("quarantine rule codes/messages are not aligned")

        path = self._path(quarantine_id)
        if path.exists():
            raise QuarantinePayloadError(
                f"quarantine payload already exists for {quarantine_id}; payloads are immutable"
            )

        payload = {
            "schema_version": PAYLOAD_SCHEMA_VERSION,
            "quarantine_id": str(quarantine_id),
            "dataset_run_id": str(dataset_run_id),
            "dataset_id": dataset_id,
            "row_count": len(rows),
            "rows": [
                {
                    "data": item.record.data,
                    "bronze_metadata": {
                        "ingested_at": item.record.ingested_at.isoformat(),
                        "run_id": str(item.record.run_id),
                        "dataset_run_id": str(item.record.dataset_run_id),
                        "source_system": item.record.source_system,
                        "source_object": item.record.source_object,
                        "operation": item.record.operation,
                        "source_commit_ts": (
                            item.record.source_commit_ts.isoformat()
                            if item.record.source_commit_ts is not None
                            else None
                        ),
                        "source_sequence": item.record.source_sequence,
                        "schema_version": item.record.schema_version,
                    },
                    "data_quality_failures": [
                        {"rule_code": code, "rule_message": message}
                        for code, message in zip(
                            item.reason_codes,
                            item.reason_messages,
                            strict=True,
                        )
                    ],
                }
                for item in rows
            ],
        }

        temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            with temp.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2, default=str)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            if temp.exists():
                temp.unlink()
        return path.as_uri()

    def _path_from_reference(self, source_reference: str) -> Path:
        parsed = urlparse(source_reference)
        if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
            raise QuarantinePayloadError(
                "JsonFileQuarantineStore only accepts local file:// source references"
            )
        path = Path(unquote(parsed.path)).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise QuarantinePayloadError(
                "quarantine source reference escapes the approved data-plane root"
            ) from exc
        return path

    def load_payload(self, batch: QuarantineBatchEvidence) -> QuarantineReplayPayload:
        if batch.source_reference is None:
            raise QuarantinePayloadError("quarantine batch has no detailed source_reference")
        path = self._path_from_reference(batch.source_reference)
        if not path.is_file():
            raise QuarantinePayloadError(f"quarantine payload does not exist: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise QuarantinePayloadError("quarantine payload is not valid readable JSON") from exc
        if not isinstance(payload, dict):
            raise QuarantinePayloadError("quarantine payload root must be an object")

        expected = {
            "quarantine_id": str(batch.quarantine_id),
            "dataset_id": batch.dataset_id,
            "row_count": batch.row_count,
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                raise QuarantinePayloadError(
                    f"quarantine payload identity mismatch for {key}: "
                    f"expected={value!r}, observed={payload.get(key)!r}"
                )
        if payload.get("schema_version") != PAYLOAD_SCHEMA_VERSION:
            raise QuarantinePayloadError("unsupported quarantine payload schema_version")
        rows = payload.get("rows")
        if not isinstance(rows, list) or len(rows) != batch.row_count:
            raise QuarantinePayloadError("quarantine payload row count does not match Control Plane")

        replay_rows: list[dict[str, object]] = []
        for item in rows:
            if not isinstance(item, dict) or not isinstance(item.get("data"), dict):
                raise QuarantinePayloadError("quarantine payload row is malformed")
            failures = item.get("data_quality_failures")
            if not isinstance(failures, list) or not failures:
                raise QuarantinePayloadError("quarantine payload row lacks DQ failure detail")
            replay_rows.append(dict(item["data"]))

        return QuarantineReplayPayload(
            quarantine_id=batch.quarantine_id,
            dataset_id=batch.dataset_id,
            source_reference=batch.source_reference,
            rows=tuple(replay_rows),
            payload_version=str(PAYLOAD_SCHEMA_VERSION),
        )


__all__ = [
    "JsonFileQuarantineStore",
    "PAYLOAD_SCHEMA_VERSION",
    "QuarantinePayloadError",
    "QuarantinePayloadWriter",
]
