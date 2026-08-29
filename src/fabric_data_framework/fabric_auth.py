"""Credential adapters for Microsoft Fabric REST clients.

The framework never serializes access tokens or client secrets. Authentication remains
an environment concern and is injected into ``FabricRestClient`` as a zero-argument
token provider.
"""

from __future__ import annotations

from collections.abc import Mapping
import os
from typing import Protocol, runtime_checkable


FABRIC_REST_SCOPE = "https://api.fabric.microsoft.com/.default"


class FabricAuthenticationError(RuntimeError):
    """Raised when an injected authentication source cannot provide a token."""


class EnvironmentAccessTokenProvider:
    """Read an ephemeral Fabric access token from an environment variable on demand.

    Only the environment-variable *name* is retained by this object. The token value is
    never cached on the provider, which keeps accidental object serialization/repr from
    becoming a credential leak.
    """

    def __init__(
        self,
        *,
        env_var: str = "FABRIC_ACCESS_TOKEN",
        environ: Mapping[str, str] | None = None,
    ) -> None:
        if not env_var.strip():
            raise ValueError("env_var cannot be empty")
        self.env_var = env_var
        self._environ = environ if environ is not None else os.environ

    def __call__(self) -> str:
        value = self._environ.get(self.env_var, "").strip()
        if not value:
            raise FabricAuthenticationError(
                f"Fabric access token environment variable {self.env_var!r} is empty or missing"
            )
        return value

    def __repr__(self) -> str:
        return f"EnvironmentAccessTokenProvider(env_var={self.env_var!r})"


@runtime_checkable
class AzureTokenCredential(Protocol):
    """Structural subset implemented by Azure Identity TokenCredential objects."""

    def get_token(self, *scopes: str, **kwargs): ...


class AzureIdentityTokenProvider:
    """Adapt any Azure Identity-compatible credential without a hard dependency.

    Applications may construct ``DefaultAzureCredential``, ``ManagedIdentityCredential``
    or another approved credential in their environment and inject it here. The core
    framework deliberately does not import or configure ``azure-identity`` itself.
    """

    def __init__(
        self,
        credential: AzureTokenCredential,
        *,
        scope: str = FABRIC_REST_SCOPE,
    ) -> None:
        if not scope.strip():
            raise ValueError("scope cannot be empty")
        self._credential = credential
        self.scope = scope

    def __call__(self) -> str:
        access_token = self._credential.get_token(self.scope)
        value = getattr(access_token, "token", "")
        if not isinstance(value, str) or not value.strip():
            raise FabricAuthenticationError(
                "Azure Identity credential returned an empty Fabric access token"
            )
        return value.strip()

    def __repr__(self) -> str:
        return f"AzureIdentityTokenProvider(scope={self.scope!r})"


__all__ = [
    "FABRIC_REST_SCOPE",
    "AzureIdentityTokenProvider",
    "AzureTokenCredential",
    "EnvironmentAccessTokenProvider",
    "FabricAuthenticationError",
]
