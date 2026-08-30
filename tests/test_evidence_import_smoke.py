def test_canonical_approved_evidence_modules_import():
    from fabric_data_framework.evidence import approved_capture_runner
    from fabric_data_framework.evidence import approved_control_plane_runner
    from fabric_data_framework.evidence import approved_pipeline_runner
    from fabric_data_framework.evidence import approved_warehouse_fault_runner
    from fabric_data_framework.evidence import approved_warehouse_runner

    assert approved_capture_runner.execute_approved_capture
    assert approved_control_plane_runner.execute_approved_control_plane_certification
    assert approved_pipeline_runner.execute_approved_pipeline
    assert approved_warehouse_runner.execute_approved_warehouse
    assert approved_warehouse_fault_runner.execute_approved_warehouse_fault_drill
