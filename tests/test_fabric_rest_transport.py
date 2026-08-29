from __future__ import annotations

from collections import deque
from io import BytesIO
import json
from urllib.error import HTTPError
from uuid import UUID, uuid4

import pytest

from fabric_data_framework.adapters.fabric.rest import (
    FabricJobStatus,
    FabricRestClient,
    FabricRestError,
)


class _Response:
    def __init__(self, status: int, *, headers=None, payload=None) -> None:
        self.status = status
        self.headers = headers or {}
        self._raw = b"" if payload is None else json.dumps(payload).encode("utf-8")

    def getcode(self):
        return self.status

    def read(self):
        return self._raw


class _QueueOpener:
    def __init__(self, responses) -> None:
        self.responses = deque(responses)
        self.requests = []

    def __call__(self, request, *, timeout):
        self.requests.append((request, timeout))
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response


def _job_payload(*, job_id, item_id, root_id, status):
    return {
        "id": str(job_id),
        "itemId": str(item_id),
        "jobType": "Pipeline",
        "invokeType": "Manual",
        "status": status,
        "rootActivityId": str(root_id),
        "startTimeUtc": "2026-08-29T09:00:00Z",
        "endTimeUtc": "2026-08-29T09:00:03Z" if status != "InProgress" else None,
        "failureReason": None,
    }


def test_run_and_wait_item_job_uses_typed_parameters_and_polling():
    workspace_id = uuid4()
    item_id = uuid4()
    job_id = uuid4()
    root_id = uuid4()
    location = (
        f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items/"
        f"{item_id}/jobs/instances/{job_id}"
    )
    opener = _QueueOpener(
        [
            _Response(202, headers={"Location": location, "Retry-After": "0"}),
            _Response(
                200,
                headers={"Retry-After": "0"},
                payload=_job_payload(
                    job_id=job_id,
                    item_id=item_id,
                    root_id=root_id,
                    status="InProgress",
                ),
            ),
            _Response(
                200,
                payload=_job_payload(
                    job_id=job_id,
                    item_id=item_id,
                    root_id=root_id,
                    status="Completed",
                ),
            ),
        ]
    )
    client = FabricRestClient(
        token_provider=lambda: "token-123",
        opener=opener,
        sleeper=lambda _: None,
        clock=lambda: 0.0,
    )
    framework_run_id = uuid4()

    result = client.run_and_wait_item_job(
        workspace_id=workspace_id,
        item_id=item_id,
        job_type="Pipeline",
        parameters={
            "framework_pipeline_run_id": framework_run_id,
            "dataset_id": "crm.customer",
            "attempt": 2,
            "enabled": True,
        },
        timeout_seconds=30,
        default_poll_seconds=0,
    )

    assert result.job_instance_id == job_id
    assert result.root_activity_id == root_id
    assert result.status is FabricJobStatus.COMPLETED
    assert len(opener.requests) == 3

    request = opener.requests[0][0]
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer token-123"
    assert request.full_url.endswith(
        f"/workspaces/{workspace_id}/items/{item_id}/jobs/Pipeline/instances"
    )
    body = json.loads(request.data.decode("utf-8"))
    parameters = {item["name"]: item for item in body["parameters"]}
    assert parameters["framework_pipeline_run_id"] == {
        "name": "framework_pipeline_run_id",
        "value": str(framework_run_id),
        "type": "Guid",
    }
    assert parameters["dataset_id"]["type"] == "Text"
    assert parameters["attempt"]["type"] == "Integer"
    assert parameters["enabled"]["type"] == "Boolean"


def test_http_error_preserves_fabric_retry_evidence():
    payload = json.dumps(
        {
            "errorCode": "TooManyRequestsForJobs",
            "message": "slow down",
            "isRetriable": True,
        }
    ).encode("utf-8")
    error = HTTPError(
        "https://api.fabric.microsoft.com/v1/test",
        429,
        "too many requests",
        {"Retry-After": "7"},
        BytesIO(payload),
    )
    opener = _QueueOpener([error])
    client = FabricRestClient(token_provider=lambda: "token", opener=opener)

    with pytest.raises(FabricRestError) as caught:
        client.run_item_job(
            workspace_id=uuid4(),
            item_id=uuid4(),
            job_type="Pipeline",
        )

    assert caught.value.status_code == 429
    assert caught.value.error_code == "TooManyRequestsForJobs"
    assert caught.value.retriable is True
    assert caught.value.retry_after_seconds == 7


def test_unknown_fabric_job_status_fails_closed():
    workspace_id = uuid4()
    item_id = uuid4()
    job_id = uuid4()
    opener = _QueueOpener(
        [
            _Response(
                200,
                payload={
                    "id": str(job_id),
                    "itemId": str(item_id),
                    "jobType": "Pipeline",
                    "status": "FutureStatusNotYetUnderstood",
                },
            )
        ]
    )
    client = FabricRestClient(token_provider=lambda: "token", opener=opener)

    with pytest.raises(FabricRestError, match="unsupported/malformed"):
        client.get_item_job_instance(
            workspace_id=workspace_id,
            item_id=item_id,
            job_instance_id=job_id,
        )


def test_location_must_end_in_job_uuid():
    opener = _QueueOpener(
        [
            _Response(
                202,
                headers={"Location": "https://api.fabric.microsoft.com/v1/jobs/not-a-uuid"},
            )
        ]
    )
    client = FabricRestClient(token_provider=lambda: "token", opener=opener)

    with pytest.raises(FabricRestError, match="did not end in a UUID"):
        client.run_item_job(
            workspace_id=UUID("00000000-0000-0000-0000-000000000001"),
            item_id=UUID("00000000-0000-0000-0000-000000000002"),
            job_type="Pipeline",
        )
