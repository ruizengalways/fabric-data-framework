"""Provider-neutral logical-to-physical Fabric environment resolution contracts."""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class EnvironmentName(str, Enum):
    DEV = "DEV"
    UAT = "UAT"
    PROD = "PROD"


class ResourceKind(str, Enum):
    WORKSPACE = "WORKSPACE"
    LAKEHOUSE = "LAKEHOUSE"
    WAREHOUSE = "WAREHOUSE"
    CONNECTION = "CONNECTION"
    VARIABLE_LIBRARY = "VARIABLE_LIBRARY"


class LogicalResourceRef(FrozenModel):
    kind: ResourceKind
    logical_name: str = Field(min_length=1)


class ResolvedResource(FrozenModel):
    ref: LogicalResourceRef
    environment: EnvironmentName
    domain: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    workspace_id: str | None = None
    endpoint: str | None = None


@runtime_checkable
class EnvironmentResolver(Protocol):
    """Resolve logical resources without embedding physical IDs in domain config."""

    def resolve(
        self,
        *,
        environment: EnvironmentName,
        domain: str,
        resource: LogicalResourceRef,
    ) -> ResolvedResource: ...
