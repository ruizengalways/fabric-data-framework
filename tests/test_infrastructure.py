from fabric_data_framework.infrastructure import (
    EnvironmentName,
    EnvironmentResolver,
    LogicalResourceRef,
    ResolvedResource,
    ResourceKind,
)


class FakeResolver:
    def resolve(self, *, environment, domain, resource):
        return ResolvedResource(
            ref=resource,
            environment=environment,
            domain=domain,
            resource_id=f"{environment.value.lower()}-{resource.logical_name}-id",
        )


def test_environment_resolver_is_provider_neutral_protocol():
    resolver = FakeResolver()
    assert isinstance(resolver, EnvironmentResolver)
    result = resolver.resolve(
        environment=EnvironmentName.UAT,
        domain="customer",
        resource=LogicalResourceRef(kind=ResourceKind.WAREHOUSE, logical_name="control"),
    )
    assert result.resource_id == "uat-control-id"
    assert result.ref.logical_name == "control"
