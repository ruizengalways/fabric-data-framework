from __future__ import annotations

from io import BytesIO
import json
from urllib.error import HTTPError
from uuid import uuid4

import pytest

from fabric_data_framework.adapters.fabric.rest import FabricRestClient, FabricRestError


class _ClosableResponse:
    def __init__(self, status: int, *, headers=None, payload=None) -> None:
        self.status = status
        self.headers = headers or {}
        self._raw = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.closed = False

    def getcode(self):
        return self.status

    def read(self):
        return self._raw

    def close(self):
        self.closed = True


def test_success_response_is_explicitly_closed_after_body_read():
    workspace_id = uuid4()
    item_id = uuid4()
    job_id = uuid4()
    response = _ClosableResponse(
        200,
        payload={
            "id": str(job_id),
            "itemId": str(item_id),
            "jobType": "Pipeline",
            "status": "Completed",
        },
    )
    client = FabricRestClient(
        token_provider=lambda: "token",
        opener=lambda _request, timeout: response,
    )

    client.get_item_job_instance(
        workspace_id=workspace_id,
        item_id=item_id,
        job_instance_id=job_id,
    )

    assert response.closed is True


def test_http_error_body_is_closed_after_read():
    body = BytesIO(
        json.dumps(
            {
                "errorCode": "RemoteFailure",
                "message": "failed",
                "isRetriable": False,
            }
        ).encode("utf-8")
    )
    error = HTTPError(
        "https://api.fabric.microsoft.com/v1/test",
        500,
        "remote failure",
        {},
        body,
    )

    def opener(_request, *, timeout):
        raise error

    client = FabricRestClient(token_provider=lambda: "token", opener=opener)

    with pytest.raises(FabricRestError):
        client.run_item_job(
            workspace_id=uuid4(),
            item_id=uuid4(),
            job_type="Pipeline",
        )

    assert body.closed is True
