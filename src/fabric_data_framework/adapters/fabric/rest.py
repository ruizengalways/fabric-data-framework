"""Concrete Microsoft Fabric REST job-scheduler transport.

The client intentionally owns only HTTP/job mechanics. Authentication is injected as
an access-token provider so Entra/MSAL/managed-identity selection remains an
environment concern. Semantic success is decided by higher framework layers.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from time import monotonic, sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID


FABRIC_API_V1 = "https://api.fabric.microsoft.com/v1"


class FabricRestError(RuntimeError):
    """HTTP/provider error retaining Fabric retry evidence where available."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        retriable: bool | None = None,
        retry_after_seconds: int | None = None,
        payload: object | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.retriable = retriable
        self.retry_after_seconds = retry_after_seconds
        self.payload = payload


class FabricJobStatus(str, Enum):
    NOT_STARTED = "NotStarted"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    DEDUPED = "Deduped"

    @property
    def terminal(self) -> bool:
        return self in {
            FabricJobStatus.COMPLETED,
            FabricJobStatus.FAILED,
            FabricJobStatus.CANCELLED,
            FabricJobStatus.DEDUPED,
        }


@dataclass(frozen=True)
class FabricJobStart:
    job_instance_id: UUID
    location: str
    retry_after_seconds: int | None = None


@dataclass(frozen=True)
class FabricJobInstance:
    job_instance_id: UUID
    item_id: UUID
    job_type: str
    status: FabricJobStatus
    root_activity_id: UUID | None
    start_time_utc: datetime | None
    end_time_utc: datetime | None
    failure_reason: object | None
    retry_after_seconds: int | None = None


def _header(headers: Mapping[str, str] | Any, name: str) -> str | None:
    value = headers.get(name) if hasattr(headers, "get") else None
    if value is None:
        return None
    return str(value)


def _retry_after(headers: Mapping[str, str] | Any) -> int | None:
    value = _header(headers, "Retry-After")
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _parse_datetime(value: object | None) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FabricRestError(f"Fabric returned timezone-naive timestamp {value!r}")
    return parsed


def _job_id_from_location(location: str) -> UUID:
    parsed = urlparse(location)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise FabricRestError("Fabric job Location header did not contain a path")
    try:
        return UUID(parts[-1])
    except ValueError as exc:
        raise FabricRestError(
            f"Fabric job Location header did not end in a UUID: {location!r}"
        ) from exc


def _typed_parameter(name: str, value: object) -> dict[str, object]:
    if not name or len(name) > 256:
        raise ValueError("Fabric job parameter names must contain 1..256 characters")
    if isinstance(value, bool):
        parameter_type = "Boolean"
        encoded: object = value
    elif isinstance(value, int):
        parameter_type = "Integer"
        encoded = value
    elif isinstance(value, float):
        parameter_type = "Number"
        encoded = value
    elif isinstance(value, UUID):
        parameter_type = "Guid"
        encoded = str(value)
    elif isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"Fabric DateTime parameter {name!r} must be timezone-aware")
        parameter_type = "DateTime"
        encoded = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    elif isinstance(value, str):
        parameter_type = "Text"
        encoded = value
    else:
        raise ValueError(
            f"unsupported Fabric job parameter type for {name!r}: {type(value).__name__}"
        )
    return {"name": name, "value": encoded, "type": parameter_type}


class FabricRestClient:
    """Minimal v1 REST client for on-demand Fabric item jobs and polling."""

    def __init__(
        self,
        *,
        token_provider: Callable[[], str],
        base_url: str = FABRIC_API_V1,
        request_timeout_seconds: float = 60.0,
        opener: Callable[..., Any] = urlopen,
        sleeper: Callable[[float], None] = sleep,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")
        self._token_provider = token_provider
        self._base_url = base_url.rstrip("/")
        self._request_timeout_seconds = request_timeout_seconds
        self._opener = opener
        self._sleeper = sleeper
        self._clock = clock

    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith("https://") or path_or_url.startswith("http://"):
            return path_or_url
        return f"{self._base_url}/{path_or_url.lstrip('/')}"

    def _request(
        self,
        method: str,
        path_or_url: str,
        *,
        payload: dict[str, Any] | None = None,
        expected_statuses: frozenset[int],
    ) -> tuple[object | None, Any]:
        token = self._token_provider().strip()
        if not token:
            raise FabricRestError("Fabric access-token provider returned an empty token")
        data = None
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self._url(path_or_url), data=data, headers=headers, method=method)
        try:
            response = self._opener(request, timeout=self._request_timeout_seconds)
            status_value = getattr(response, "status", None)
            status = int(status_value if status_value is not None else response.getcode())
            response_headers = response.headers
            raw = response.read()
        except HTTPError as exc:
            raw = exc.read()
            response_headers = exc.headers
            payload_obj: object | None = None
            if raw:
                try:
                    payload_obj = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    payload_obj = raw.decode("utf-8", errors="replace")
            error_code = None
            retriable = None
            message = f"Fabric REST request failed with HTTP {exc.code}"
            if isinstance(payload_obj, dict):
                error_code = payload_obj.get("errorCode")
                retriable = payload_obj.get("isRetriable")
                if payload_obj.get("message"):
                    message = str(payload_obj["message"])
            raise FabricRestError(
                message,
                status_code=exc.code,
                error_code=str(error_code) if error_code is not None else None,
                retriable=bool(retriable) if retriable is not None else None,
                retry_after_seconds=_retry_after(response_headers),
                payload=payload_obj,
            ) from exc
        except URLError as exc:
            raise FabricRestError(f"Fabric REST transport error: {exc.reason}") from exc

        if status not in expected_statuses:
            raise FabricRestError(
                f"Fabric REST returned unexpected HTTP {status}",
                status_code=status,
                retry_after_seconds=_retry_after(response_headers),
            )
        if not raw:
            return None, response_headers
        try:
            return json.loads(raw.decode("utf-8")), response_headers
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FabricRestError("Fabric REST returned invalid JSON") from exc

    def run_item_job(
        self,
        *,
        workspace_id: UUID,
        item_id: UUID,
        job_type: str,
        parameters: Mapping[str, object] | None = None,
        execution_data: Mapping[str, object] | None = None,
    ) -> FabricJobStart:
        """Start one v1 on-demand item job.

        ``parameters`` uses the generic Job Scheduler per-run parameter shape. Fabric
        documents that parameter support is item/job-type dependent; a provider
        ``FeatureNotAvailable`` response is intentionally surfaced rather than hidden.
        """

        if not job_type.strip():
            raise ValueError("job_type cannot be empty")
        payload: dict[str, Any] = {}
        if execution_data is not None:
            payload["executionData"] = dict(execution_data)
        if parameters:
            payload["parameters"] = [
                _typed_parameter(name, value)
                for name, value in sorted(parameters.items())
            ]
        body, headers = self._request(
            "POST",
            f"workspaces/{workspace_id}/items/{item_id}/jobs/{job_type}/instances",
            payload=payload or None,
            expected_statuses=frozenset({202}),
        )
        del body
        location = _header(headers, "Location")
        if not location:
            raise FabricRestError("Fabric on-demand job response did not include Location")
        return FabricJobStart(
            job_instance_id=_job_id_from_location(location),
            location=location,
            retry_after_seconds=_retry_after(headers),
        )

    def get_item_job_instance(
        self,
        *,
        workspace_id: UUID,
        item_id: UUID,
        job_instance_id: UUID,
    ) -> FabricJobInstance:
        payload, headers = self._request(
            "GET",
            f"workspaces/{workspace_id}/items/{item_id}/jobs/instances/{job_instance_id}",
            expected_statuses=frozenset({200}),
        )
        if not isinstance(payload, dict):
            raise FabricRestError("Fabric job-instance response must be a JSON object")
        try:
            status = FabricJobStatus(str(payload["status"]))
            observed_id = UUID(str(payload["id"]))
            observed_item = UUID(str(payload["itemId"]))
            job_type = str(payload["jobType"])
        except (KeyError, ValueError) as exc:
            raise FabricRestError(
                f"Fabric job-instance response has an unsupported/malformed identity or status: {payload!r}"
            ) from exc
        if observed_id != job_instance_id:
            raise FabricRestError(
                f"Fabric returned job id {observed_id}, expected {job_instance_id}"
            )
        if observed_item != item_id:
            raise FabricRestError(f"Fabric returned item id {observed_item}, expected {item_id}")
        root = payload.get("rootActivityId")
        return FabricJobInstance(
            job_instance_id=observed_id,
            item_id=observed_item,
            job_type=job_type,
            status=status,
            root_activity_id=UUID(str(root)) if root else None,
            start_time_utc=_parse_datetime(payload.get("startTimeUtc")),
            end_time_utc=_parse_datetime(payload.get("endTimeUtc")),
            failure_reason=payload.get("failureReason"),
            retry_after_seconds=_retry_after(headers),
        )

    def run_and_wait_item_job(
        self,
        *,
        workspace_id: UUID,
        item_id: UUID,
        job_type: str,
        parameters: Mapping[str, object] | None = None,
        execution_data: Mapping[str, object] | None = None,
        timeout_seconds: float = 3600.0,
        default_poll_seconds: float = 5.0,
    ) -> FabricJobInstance:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if default_poll_seconds < 0:
            raise ValueError("default_poll_seconds must be >= 0")
        started = self.run_item_job(
            workspace_id=workspace_id,
            item_id=item_id,
            job_type=job_type,
            parameters=parameters,
            execution_data=execution_data,
        )
        deadline = self._clock() + timeout_seconds
        delay = (
            float(started.retry_after_seconds)
            if started.retry_after_seconds is not None
            else default_poll_seconds
        )
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise FabricRestError(
                    f"Fabric job {started.job_instance_id} did not reach a terminal state before timeout"
                )
            if delay > 0:
                self._sleeper(min(delay, remaining))
            instance = self.get_item_job_instance(
                workspace_id=workspace_id,
                item_id=item_id,
                job_instance_id=started.job_instance_id,
            )
            if instance.status.terminal:
                return instance
            delay = (
                float(instance.retry_after_seconds)
                if instance.retry_after_seconds is not None
                else default_poll_seconds
            )


__all__ = [
    "FABRIC_API_V1",
    "FabricJobInstance",
    "FabricJobStart",
    "FabricJobStatus",
    "FabricRestClient",
    "FabricRestError",
]
