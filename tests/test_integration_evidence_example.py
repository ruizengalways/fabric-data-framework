from pathlib import Path

from fabric_data_framework.integration_evidence import load_integration_evidence_spec


def test_dev_integration_evidence_spec_example_is_valid():
    spec = load_integration_evidence_spec(Path("examples/dev_integration_evidence_spec.json"))
    assert spec.environment.value == "DEV"
    assert spec.domain == "customer"
    assert {item.check_id for item in spec.checks} >= {
        "fabric.item.read",
        "control.cert",
        "fabric.pipeline",
        "fabric.copy",
        "fabric.spark",
        "warehouse.commit",
    }
