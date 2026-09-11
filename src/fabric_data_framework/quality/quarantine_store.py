"""Governed data-plane storage for detailed row-quarantine payloads.

The relational Control Plane intentionally stores only immutable quarantine lineage,
summary counts/reasons and a ``source_reference``. Full business rows remain in an
explicitly selected governed data-plane root.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Protocol, Sequence, runtime_checkable
from urllib.parse import unquote, urlparse
from uuid import UUID, uuid4

from fabric_data_framework.contracts.replay import (
    QuarantineBatchEvidence,
    QuarantineReplayPayload,
    QuarantineReplayPayloadProvider,
)
from fabric_data_framework.contracts.typed_values import (
    TypedValueError,
    decode_typed_value,
    encode_typed_value,
)
from fabric_data_framework.quality.rules import QuarantinedRecord


PAYLOAD_SCHEMA_VERSION = 2


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


def _payload_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _payload_sha256(payload: dict[str, object]) -> str:
    return hashlib.sha256(_payload_bytes(payload)).hexdigest()


class JsonFileQuarantineStore(QuarantinePayloadWriter, QuarantineReplayPayloadProvider):
    """Immutable typed JSON quarantine payloads rooted in one approved directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise QuarantinePayloadError(f"quarantine root is not a directory: {self.root}")

    def _path(self, quarantine_id: UUID) -> Path:
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

        try:
            payload_body: dict[str, object] = {
                "schema_version": PAYLOAD_SCHEMA_VERSION,
                "quarantine_id": str(quarantine_id),
                "dataset_run_id": str(dataset_run_id),
                "dataset_id": dataset_id,
                "row_count": len(rows),
                "rows": [
                    {
                        "data": encode_typed_value(item.record.data),
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
        except TypedValueError as exc:
            raise QuarantinePayloadError(
                "quarantine payload contains an unsupported business value type"
            ) from exc

        payload = dict(payload_body)
        payload["payload_sha256"] = _payload_sha256(payload_body)
        temp = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
        try:
            with temp.open("x", encoding="utf-8") as handle:
                json.dump(
                    payload,
                    handle,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                    allow_nan=False,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp, path)
            except FileExistsError as exc:
                raise QuarantinePayloadError(
                    f"quarantine payload already exists for {quarantine_id}; payloads are immutable"
                ) from exc
            except OSError as exc:
                raise QuarantinePayloadError(
                    "filesystem does not support atomic create-if-absent quarantine publication"
                ) from exc
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
        if payload.get("schema_version") != PAYLOAD_SCHEMA_VERSION:
            raise QuarantinePayloadError("unsupported quarantine payload schema_version")

        observed_hash = payload.get("payload_sha256")
        if not isinstance(observed_hash, str) or len(observed_hash) != 64:
            raise QuarantinePayloadError("quarantine payload lacks a valid content hash")
        payload_body = dict(payload)
        del payload_body["payload_sha256"]
        if _payload_sha256(payload_body) != observed_hash:
            raise QuarantinePayloadError("quarantine payload content hash mismatch")

        expected = {
            "quarantine_id": str(batch.quarantine_id),
            "dataset_run_id": str(batch.dataset_run_id),
            "dataset_id": batch.dataset_id,
            "row_count": batch.row_count,
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                raise QuarantinePayloadError(
                    f"quarantine payload identity mismatch for {key}: "
                    f"expected={value!r}, observed={payload.get(key)!r}"
                )
        rows = payload.get("rows")
        if not isinstance(rows, list) or len(rows) != batch.row_count:
            raise QuarantinePayloadError("quarantine payload row count does not match Control Plane")

        replay_rows: list[dict[str, object]] = []
        for item in rows:
            if not isinstance(item, dict):
                raise QuarantinePayloadError("quarantine payload row is malformed")
            failures = item.get("data_quality_failures")
            if not isinstance(failures, list) or not failures:
                raise QuarantinePayloadError("quarantine payload row lacks DQ failure detail")
            try:
                decoded = decode_typed_value(item.get("data"))
            except TypedValueError as exc:
                raise QuarantinePayloadError("quarantine payload typed data is malformed") from exc
            if not isinstance(decoded, dict):
                raise QuarantinePayloadError("quarantine payload row data must decode to an object")
            replay_rows.append(decoded)

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
