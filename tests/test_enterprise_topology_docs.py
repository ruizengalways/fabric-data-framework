from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_enterprise_topology_docs_lock_canonical_storage_roles():
    human = (ROOT / "docs/human/ENTERPRISE_FABRIC_ARCHITECTURE.md").read_text(
        encoding="utf-8"
    )
    machine = (ROOT / "docs/machine/ENTERPRISE_TOPOLOGY.md").read_text(
        encoding="utf-8"
    )
    index = (ROOT / "docs/human/README.md").read_text(encoding="utf-8")

    for text in (human, machine):
        assert "fabric_sql_database_v1" in text
        assert "DEV" in text and "UAT" in text and "PROD" in text
        assert "Lakehouse" in text
        assert "Warehouse" in text

    assert "### Fabric SQL Database — operational control plane" in human
    assert "lakehouse_as_enterprise_canonical_control_plane: false" in machine
    assert "ENTERPRISE_FABRIC_ARCHITECTURE.md" in index


def test_enterprise_topology_docs_forbid_runtime_state_promotion():
    machine = (ROOT / "docs/machine/ENTERPRISE_TOPOLOGY.md").read_text(
        encoding="utf-8"
    )
    assert "promote_runtime_state_between_environments: false" in machine
    assert "pipeline_run rows" in machine
    assert "watermarks/checkpoints" in machine
    assert "physical item/resource IDs" in machine
