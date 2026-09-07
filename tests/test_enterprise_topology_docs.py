from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = ROOT / "docs/ARCHITECTURE.md"
STATE = ROOT / "docs/internal/STATE.md"


def test_enterprise_topology_docs_lock_canonical_storage_roles():
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    state = STATE.read_text(encoding="utf-8")

    for text in (architecture, state):
        assert "fabric_sql_database_v1" in text
        assert "DEV" in text and "UAT" in text and "PROD" in text
        assert "Lakehouse" in text
        assert "Warehouse" in text

    assert "### Fabric SQL Database" in architecture
    assert "operational state" in architecture
    assert "warehouse_role: optional SQL-first Gold / dimensional serving" in state


def test_enterprise_topology_docs_forbid_runtime_state_promotion():
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    state = STATE.read_text(encoding="utf-8")

    assert "promote_runtime_state_between_environments: false" in state
    for token in (
        "pipeline/dataset run rows",
        "watermarks/checkpoints",
        "physical Fabric item IDs",
    ):
        assert token in architecture
