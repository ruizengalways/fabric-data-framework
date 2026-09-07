from __future__ import annotations

from collections import deque
import json
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest

from fabric_data_framework.adapters.fabric.items import FabricItemCatalogClient
from fabric_data_framework.adapters.fabric.rest import FabricRestError


class _Response:
    def __init__(self, payload) -> None:
        self.status = 200
        self.headers = {}
        self._raw = json.dumps(payload).encode("utf-8")

    def getcode(self):
        return self.status

    def read(self):
        return self._raw


class _QueueOpener:
    def __init__(self, payloads) -> None:
        self.responses = deque(_Response(payload) for payload in payloads)
        self.requests = []

    def __call__(self, request, *, timeout):
        self.requests.append((request, timeout))
        return self.responses.popleft()


def _item(*, workspace_id, item_id, name, item_type):
    return {
        "id": str(item_id),
        "workspaceId": str(workspace_id),
        "displayName": name,
        "type": item_type,
    }


def test_list_items_uses_type_filter_and_continuation_token_pagination():
    workspace_id = uuid4()
    first_id, second_id = uuid4(), uuid4()
    opener = _QueueOpener(
        [
            {
                "value": [
                    _item(
                        workspace_id=workspace_id,
                        item_id=first_id,
                        name="cert-pipeline-a",
                        item_type="DataPipeline",
                    )
                ],
                "continuationToken": "opaque next/token",
                "continuationUri": "https://malicious.invalid/must-not-be-followed",
            },
            {
                "value": [
                    _item(
                        workspace_id=workspace_id,
                        item_id=second_id,
                        name="cert-pipeline-b",
                        item_type="DataPipeline",
                    )
                ]
            },
        ]
    )
    client = FabricItemCatalogClient(token_provider=lambda: "secret-token", opener=opener)

    items = client.list_items(workspace_id=workspace_id, item_type="DataPipeline")

    assert [item.id for item in items] == [first_id, second_id]
    assert len(opener.requests) == 2
    first = urlparse(opener.requests[0][0].full_url)
    second = urlparse(opener.requests[1][0].full_url)
    assert first.netloc == "api.fabric.microsoft.com"
    assert second.netloc == "api.fabric.microsoft.com"
    assert parse_qs(first.query) == {"type": ["DataPipeline"]}
    assert parse_qs(second.query) == {
        "type": ["DataPipeline"],
        "continuationToken": ["opaque next/token"],
    }
    assert opener.requests[0][0].get_header("Authorization") == "Bearer secret-token"


def test_list_items_rejects_workspace_identity_mismatch():
    workspace_id = uuid4()
    opener = _QueueOpener(
        [
            {
                "value": [
                    _item(
                        workspace_id=uuid4(),
                        item_id=uuid4(),
                        name="wrong-workspace",
                        item_type="Lakehouse",
                    )
                ]
            }
        ]
    )
    client = FabricItemCatalogClient(token_provider=lambda: "token", opener=opener)

    with pytest.raises(FabricRestError, match="unexpected workspace"):
        client.list_items(workspace_id=workspace_id, item_type="Lakehouse")


def test_list_items_rejects_unexpected_type_inside_filtered_response():
    workspace_id = uuid4()
    opener = _QueueOpener(
        [
            {
                "value": [
                    _item(
                        workspace_id=workspace_id,
                        item_id=uuid4(),
                        name="wrong-type",
                        item_type="Notebook",
                    )
                ]
            }
        ]
    )
    client = FabricItemCatalogClient(token_provider=lambda: "token", opener=opener)

    with pytest.raises(FabricRestError, match="unexpected type"):
        client.list_items(workspace_id=workspace_id, item_type="Lakehouse")


def test_list_items_rejects_repeated_continuation_token():
    workspace_id = uuid4()
    opener = _QueueOpener(
        [
            {"value": [], "continuationToken": "same-token"},
            {"value": [], "continuationToken": "same-token"},
        ]
    )
    client = FabricItemCatalogClient(token_provider=lambda: "token", opener=opener)

    with pytest.raises(FabricRestError, match="repeated a continuationToken"):
        client.list_items(workspace_id=workspace_id)


def test_list_items_rejects_malformed_response_shape():
    client = FabricItemCatalogClient(
        token_provider=lambda: "token",
        opener=_QueueOpener([{"items": []}]),
    )

    with pytest.raises(FabricRestError, match="value array"):
        client.list_items(workspace_id=uuid4())
