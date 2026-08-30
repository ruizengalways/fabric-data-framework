import pytest

from fabric_data_framework.adapters.fabric.auth import (
    FABRIC_REST_SCOPE,
    AzureIdentityTokenProvider,
    EnvironmentAccessTokenProvider,
    FabricAuthenticationError,
)


def test_environment_token_provider_reads_ephemeral_value_without_repr_leak():
    provider = EnvironmentAccessTokenProvider(
        env_var="FABRIC_ACCESS_TOKEN",
        environ={"FABRIC_ACCESS_TOKEN": "  secret-token-value  "},
    )

    assert provider() == "secret-token-value"
    assert "secret-token-value" not in repr(provider)
    assert "FABRIC_ACCESS_TOKEN" in repr(provider)


def test_environment_token_provider_fails_when_missing():
    provider = EnvironmentAccessTokenProvider(environ={})

    with pytest.raises(FabricAuthenticationError, match="empty or missing"):
        provider()


class _Token:
    token = "azure-identity-token"
    expires_on = 1234567890


class _Credential:
    def __init__(self):
        self.scopes = []

    def get_token(self, *scopes, **kwargs):
        self.scopes.append((scopes, kwargs))
        return _Token()


def test_azure_identity_adapter_uses_fabric_default_scope_without_hard_dependency():
    credential = _Credential()
    provider = AzureIdentityTokenProvider(credential)

    assert provider() == "azure-identity-token"
    assert credential.scopes == [((FABRIC_REST_SCOPE,), {})]
    assert "azure-identity-token" not in repr(provider)


def test_azure_identity_adapter_rejects_empty_token():
    class EmptyCredential:
        def get_token(self, *scopes, **kwargs):
            return type("AccessToken", (), {"token": ""})()

    with pytest.raises(FabricAuthenticationError, match="empty Fabric access token"):
        AzureIdentityTokenProvider(EmptyCredential())()
