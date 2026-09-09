def test_canonical_approved_evidence_modules_import():
    from fabric_data_framework.evidence.integration.approved import capture
    from fabric_data_framework.evidence.integration.approved import control_plane
    from fabric_data_framework.evidence.integration.approved import pipeline
    from fabric_data_framework.evidence.integration.approved import warehouse
    from fabric_data_framework.evidence.integration.approved import warehouse_fault

    assert capture.execute_approved_capture
    assert control_plane.execute_approved_control_plane_certification
    assert pipeline.execute_approved_pipeline
    assert warehouse.execute_approved_warehouse
    assert warehouse_fault.execute_approved_warehouse_fault_drill
