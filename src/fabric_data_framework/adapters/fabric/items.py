"""Read-only Microsoft Fabric workspace item discovery.

This module extends the existing Fabric REST transport with Core List Items semantics.
It performs no Fabric mutation and never retains access-token values.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode, urlparse
from uuid import UUID

from .rest import FabricRestClient, FabricRestError


@dataclass(frozen=True)
class FabricItem:
    """Minimal non-secret identity returned by the Fabric Core Items API."""

    id: UUID
    workspace_id: UUID
    display_name: str
    item_type: str


def _parse_item(value: object, *, expected_workspace_id: UUID) -> FabricItem:
    if not isinstance(value, dict):
        raise FabricRestError("Fabric List Items entry must be a JSON object")
    try:
        item_id = UUID(str(value["id"]))
        workspace_id = UUID(str(value["workspaceId"]))
        display_name = str(value["displayName"]).strip()
        item_type = str(value["type"]).strip()
    except (KeyError, ValueError) as exc:
        raise FabricRestError("Fabric List Items entry has malformed identity fields") from exc
    if workspace_id != expected_workspace_id:
        raise FabricRestError(
            "Fabric List Items returned an item from an unexpected workspace: "
            f"observed={workspace_id}, expected={expected_workspace_id}"
        )
    if not display_name:
        raise FabricRestError("Fabric List Items entry has an empty displayName")
    if not item_type:
        raise FabricRestError("Fabric List Items entry has an empty type")
    return FabricItem(
        id=item_id,
        workspace_id=workspace_id,
        display_name=display_name,
        item_type=item_type,
    )


class FabricItemCatalogClient(FabricRestClient):
    """Read-only Core Items API client with fail-closed pagination."""

    def _validated_continuation_uri(self, value: object, *, workspace_id: UUID) -> str:
        uri = str(value).strip()
        if not uri:
            raise FabricRestError("Fabric List Items continuationUri cannot be blank")
        base = urlparse(self._base_url)
        parsed = urlparse(uri)
        expected_path = f"{base.path.rstrip('/')}/workspaces/{workspace_id}/items"
        if (
            parsed.scheme != base.scheme
            or parsed.netloc != base.netloc
            or parsed.path != expected_path
            or parsed.fragment
        ):
            raise FabricRestError(
                "Fabric List Items continuationUri escaped the configured API origin/path"
            )
        return uri

    def list_items(
        self,
        *,
        workspace_id: UUID,
        item_type: str | None = None,
    ) -> tuple[FabricItem, ...]:
        """List all visible items in one workspace, optionally filtered by exact type.

        Fabric's Core List Items endpoint is paginated. A provider continuation URI is
        followed only after strict same-origin/current-workspace validation. If Fabric
        returns only a continuation token, the client rebuilds the same request and
        preserves percent escapes already present in the opaque token.
        """

        selected_type = item_type.strip() if item_type is not None else None
        if item_type is not None and not selected_type:
            raise ValueError("item_type cannot be empty")

        next_request: str | None = None
        continuation_token: str | None = None
        observed_tokens: set[str] = set()
        observed_uris: set[str] = set()
        result: list[FabricItem] = []

        while True:
            if next_request is None:
                query: dict[str, str] = {}
                if selected_type is not None:
                    query["type"] = selected_type
                if continuation_token is not None:
                    query["continuationToken"] = continuation_token
                suffix = f"?{urlencode(query, safe='%')}" if query else ""
                request_target = f"workspaces/{workspace_id}/items{suffix}"
            else:
                request_target = next_request

            payload, _ = self._request(
                "GET",
                request_target,
                expected_statuses=frozenset({200}),
            )
            if not isinstance(payload, dict):
                raise FabricRestError("Fabric List Items response must be a JSON object")
            values = payload.get("value")
            if not isinstance(values, list):
                raise FabricRestError("Fabric List Items response must contain a value array")
            for value in values:
                item = _parse_item(value, expected_workspace_id=workspace_id)
                if selected_type is not None and item.item_type != selected_type:
                    raise FabricRestError(
                        "Fabric List Items type-filter response contained an unexpected type: "
                        f"observed={item.item_type!r}, expected={selected_type!r}"
                    )
                result.append(item)

            raw_token = payload.get("continuationToken")
            raw_uri = payload.get("continuationUri")
            if raw_token in (None, "") and raw_uri in (None, ""):
                break

            continuation_token = None
            next_request = None
            if raw_token not in (None, ""):
                continuation_token = str(raw_token).strip()
                if not continuation_token:
                    raise FabricRestError("Fabric List Items continuationToken cannot be blank")
                if continuation_token in observed_tokens:
                    raise FabricRestError("Fabric List Items repeated a continuationToken")
                observed_tokens.add(continuation_token)
            if raw_uri not in (None, ""):
                next_request = self._validated_continuation_uri(
                    raw_uri,
                    workspace_id=workspace_id,
                )
                if next_request in observed_uris:
                    raise FabricRestError("Fabric List Items repeated a continuationUri")
                observed_uris.add(next_request)
            elif continuation_token is None:
                raise FabricRestError(
                    "Fabric List Items pagination response has no usable continuation"
                )

        return tuple(result)


__all__ = ["FabricItem", "FabricItemCatalogClient"]
