from fabric_data_framework.extensions import ExtensionKind


def test_approved_evidence_extension_kinds_have_stable_entry_point_groups():
    assert (
        ExtensionKind.CAPTURE_OBSERVER.entry_point_group
        == "fabric_data_framework.capture_observers"
    )
    assert (
        ExtensionKind.SPARK_EXECUTION_DATA.entry_point_group
        == "fabric_data_framework.spark_execution_data"
    )
    assert (
        ExtensionKind.WAREHOUSE_MUTATION.entry_point_group
        == "fabric_data_framework.warehouse_mutations"
    )
    assert (
        ExtensionKind.WAREHOUSE_COMMIT_FAULT_INJECTOR.entry_point_group
        == "fabric_data_framework.warehouse_commit_fault_injectors"
    )
