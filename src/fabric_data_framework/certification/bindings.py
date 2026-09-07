"""Fail-closed discovery of non-secret Fabric certification item bindings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from pydantic import Field

from fabric_data_framework.adapters.fabric.items import FabricItem, FabricItemCatalogClient
from fabric_data_framework.contracts.base import FrozenModel


CertificationBindingRole = Literal[
    "item_read",
    "pipeline",
    "copy_job",
    "spark_job",
]


class CertificationBindingItem(FrozenModel):
    role: CertificationBindingRole
    item_id: UUID
    display_name: str = Field(min_length=1, max_length=256)
    item_type: str = Field(min_length=1, max_length=128)


class CertificationIntegrationBindings(FrozenModel):
    """Reviewed, credential-free physical bindings for integration input generation."""

    binding_schema_version: int = Field(default=1, ge=1)
    workspace_id: UUID
    item_read_id: UUID
    pipeline_item_id: UUID
    copy_job_id: UUID
    spark_job_id: UUID
    resolved_items: tuple[CertificationBindingItem, ...]

    def workflow_dispatch_inputs(self) -> dict[str, str]:
        """Return the UUID fields expected by candidate-integration-inputs.yml."""

        return {
            "workspace_id": str(self.workspace_id),
            "item_read_id": str(self.item_read_id),
            "pipeline_item_id": str(self.pipeline_item_id),
            "copy_job_id": str(self.copy_job_id),
            "spark_job_id": str(self.spark_job_id),
        }


def _exact_item(
    items: tuple[FabricItem, ...],
    *,
    role: CertificationBindingRole,
    display_name: str,
    item_type: str,
) -> FabricItem:
    name = display_name.strip()
    selected_type = item_type.strip()
    if not name:
        raise ValueError(f"{role} display name cannot be empty")
    if not selected_type:
        raise ValueError(f"{role} item type cannot be empty")
    matches = tuple(
        item
        for item in items
        if item.display_name == name and item.item_type == selected_type
    )
    if not matches:
        raise ValueError(
            f"no exact Fabric item match for role={role!r}, "
            f"display_name={name!r}, item_type={selected_type!r}"
        )
    if len(matches) != 1:
        raise ValueError(
            f"Fabric item binding is ambiguous for role={role!r}, "
            f"display_name={name!r}, item_type={selected_type!r}; matches={len(matches)}"
        )
    return matches[0]


def discover_certification_bindings(
    *,
    client: FabricItemCatalogClient,
    workspace_id: UUID | str,
    item_read_name: str,
    item_read_type: str,
    pipeline_name: str,
    copy_job_name: str,
    spark_job_name: str,
) -> CertificationIntegrationBindings:
    """Resolve exact certification item names to immutable UUID bindings.

    Resolution is case-sensitive and type-sensitive. Zero or multiple exact matches fail
    closed. The function only calls Fabric Core List Items; it never creates, updates,
    deletes or runs a Fabric item.
    """

    selected_workspace = UUID(str(workspace_id))
    targets: tuple[tuple[CertificationBindingRole, str, str], ...] = (
        ("item_read", item_read_name, item_read_type),
        ("pipeline", pipeline_name, "DataPipeline"),
        ("copy_job", copy_job_name, "CopyJob"),
        ("spark_job", spark_job_name, "SparkJobDefinition"),
    )

    by_type: dict[str, tuple[FabricItem, ...]] = {}
    resolved: list[CertificationBindingItem] = []
    ids: dict[CertificationBindingRole, UUID] = {}
    for role, display_name, item_type in targets:
        if item_type not in by_type:
            by_type[item_type] = client.list_items(
                workspace_id=selected_workspace,
                item_type=item_type,
            )
        item = _exact_item(
            by_type[item_type],
            role=role,
            display_name=display_name,
            item_type=item_type,
        )
        ids[role] = item.id
        resolved.append(
            CertificationBindingItem(
                role=role,
                item_id=item.id,
                display_name=item.display_name,
                item_type=item.item_type,
            )
        )

    return CertificationIntegrationBindings(
        workspace_id=selected_workspace,
        item_read_id=ids["item_read"],
        pipeline_item_id=ids["pipeline"],
        copy_job_id=ids["copy_job"],
        spark_job_id=ids["spark_job"],
        resolved_items=tuple(resolved),
    )


def discover_certification_bindings_from_names(
    *,
    token_provider,
    workspace_id: UUID | str,
    item_read_name: str,
    item_read_type: str,
    pipeline_name: str,
    copy_job_name: str,
    spark_job_name: str,
    client_kwargs: Mapping[str, object] | None = None,
) -> CertificationIntegrationBindings:
    """Convenience wrapper constructing the read-only Fabric item catalog client."""

    client = FabricItemCatalogClient(
        token_provider=token_provider,
        **dict(client_kwargs or {}),
    )
    return discover_certification_bindings(
        client=client,
        workspace_id=workspace_id,
        item_read_name=item_read_name,
        item_read_type=item_read_type,
        pipeline_name=pipeline_name,
        copy_job_name=copy_job_name,
        spark_job_name=spark_job_name,
    )


__all__ = [
    "CertificationBindingItem",
    "CertificationIntegrationBindings",
    "discover_certification_bindings",
    "discover_certification_bindings_from_names",
]
