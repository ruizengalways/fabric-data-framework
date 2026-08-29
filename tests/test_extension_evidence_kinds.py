from fabric_data_framework.extensions import ExtensionKind


def test_capture_evidence_extension_kinds_have_stable_entry_point_groups():
    assert (
        ExtensionKind.CAPTURE_OBSERVER.entry_point_group
        == "fabric_data_framework.capture_observers"
    )
    assert (
        ExtensionKind.SPARK_EXECUTION_DATA.entry_point_group
        == "fabric_data_framework.spark_execution_data"
    )
