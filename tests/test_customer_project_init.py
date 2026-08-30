from __future__ import annotations

import json

import pytest

from fabric_data_framework.cli.main import main as cli_main
from fabric_data_framework.deployment.project import (
    initialize_customer_project,
    load_customer_project_layout,
)


def test_initialize_customer_project_creates_product_layout(tmp_path) -> None:
    root = tmp_path / "health"

    result = initialize_customer_project(root, domain="health")

    assert result.domain == "health"
    assert result.existing_paths == ()
    assert (root / "fabric-project.json").is_file()
    assert (root / "config/datasets/README.md").is_file()
    assert (root / "config/capture/semantic-selections.example.json").read_text(
        encoding="utf-8"
    ) == "[]\n"
    assert (root / "docs/dataset-inventory.csv").read_text(encoding="utf-8").startswith(
        "dataset_id,source_system,source_object"
    )

    layout = load_customer_project_layout(root)
    assert layout.domain == "health"
    assert layout.dataset_config_dir == "config/datasets"

    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "50 full-refresh datasets" in readme
    assert "20 SCD2 datasets" in readme
    assert "10 CDC datasets" in readme
    assert "Do not create separate repos" in readme


def test_initialize_customer_project_rejects_nonempty_root_by_default(tmp_path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    (root / "README.md").write_text("owned by customer\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not empty"):
        initialize_customer_project(root, domain="health")


def test_allow_existing_never_overwrites_customer_files(tmp_path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    existing_readme = "customer-owned README\n"
    (root / "README.md").write_text(existing_readme, encoding="utf-8")

    result = initialize_customer_project(root, domain="health", allow_existing=True)

    assert (root / "README.md").read_text(encoding="utf-8") == existing_readme
    assert "README.md" in result.existing_paths
    assert "fabric-project.json" in result.created_paths
    assert (root / "config/datasets/README.md").is_file()


def test_allow_existing_rejects_domain_mismatch(tmp_path) -> None:
    root = tmp_path / "existing"
    initialize_customer_project(root, domain="health")

    with pytest.raises(ValueError, match="domain does not match"):
        initialize_customer_project(root, domain="finance", allow_existing=True)


def test_project_init_cli_returns_json_summary(tmp_path, capsys) -> None:
    root = tmp_path / "health"

    exit_code = cli_main(["project-init", str(root), "--domain", "health"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["domain"] == "health"
    assert payload["manifest_path"] == "fabric-project.json"
    assert "config/datasets/README.md" in payload["created_paths"]


def test_project_init_cli_fails_closed_on_invalid_domain(tmp_path, capsys) -> None:
    exit_code = cli_main(["project-init", str(tmp_path / "x"), "--domain", "Health Care"])

    assert exit_code == 2
    assert "error:" in capsys.readouterr().err
