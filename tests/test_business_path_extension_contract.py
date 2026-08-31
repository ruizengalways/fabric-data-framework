from fabric_data_framework.extensions.registry import ExtensionKind, ExtensionRegistry


def test_business_path_observer_has_dedicated_entry_point_group():
    assert (
        ExtensionKind.BUSINESS_PATH_OBSERVER.entry_point_group
        == "fabric_data_framework.business_path_observers"
    )


def test_business_path_observer_resolves_only_through_controlled_registry():
    registry = ExtensionRegistry()

    def observer(request):
        return request

    registry.register(
        ExtensionKind.BUSINESS_PATH_OBSERVER,
        "health.business_path_observer_v1",
        observer,
    )

    assert (
        registry.factory(
            ExtensionKind.BUSINESS_PATH_OBSERVER,
            "health.business_path_observer_v1",
        )
        is observer
    )
