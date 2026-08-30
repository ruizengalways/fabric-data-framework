from __future__ import annotations

import json

import pytest

from fabric_data_framework.cli.main import main as cli_main
from fabric_data_framework.deployment.project import (
    initialize_customer_project,
    load_customer_project_layout,
    validate_customer_project,
)


def _dataset_config(
    dataset_id: str,
    *,
    apply_strategy: str = "SCD1",
    dependencies: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "dataset_id": dataset_id,
        "source": {"system": "ehr", "object": dataset_id},
        "target": {"layer": "silver", "object": dataset_id},
        "load": {
            "capture_strategy": "FULL",
            "apply_strategy": apply_strategy,
            "business_key": ["id"] if apply_strategy == "SCD2" else [],
            "merge_key": ["id"],
        },
        "orchestration": {
            "execution_group": "health-daily",
            "dependencies": list(dependencies),
        },
        "quality": {"policy_name": "default", "quarantine_policy": "FAIL"},
        "reconciliation": {"policy_name": "row-count"},
    }


def _write_project_bundle(root) -> None:
    initialize_customer_project(root, domain="health")
    configs = root / "config/datasets"
    (configs / "patient.json").write_text(
        json.dumps(_dataset_config("patient")), encoding="utf-8"
    )
    (configs / "claim.json").write_text(
        json.dumps(
            _dataset_config("claim", apply_strategy="SCD2", dependencies=("patient",))
        ),
        encoding="utf-8",
    )
    selections = [
        {
            "dataset_id": "patient",
            "cheatsheet_pattern": "FULL_SNAPSHOT_CURRENT",
            "rationale": "Source provides a complete current-state snapshot.",
        },
        {
            "dataset_id": "claim",
            "cheatsheet_pattern": "FULL_SNAPSHOT_HISTORY",
            "rationale": "Daily snapshots are retained for bounded history.",
            "known_limitations": ["History is only truthful at daily snapshot grain."],
        },
    ]
    (root / "config/capture/semantic-selections.json").write_text(
        json.dumps(selections), encoding="utf-8"
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
    assert "project-validate" in readme


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


def test_validate_customer_project_dry_runs_complete_bundle(tmp_path) -> None:
    root = tmp_path / "health"
    _write_project_bundle(root)

    report = validate_customer_project(root)

    assert report.domain == "health"
    assert report.dataset_count == 2
    assert report.semantic_selection_count == 2
    assert [(item.value, item.count) for item in report.capture_strategies] == [("FULL", 2)]
    assert [(item.value, item.count) for item in report.apply_strategies] == [
        ("SCD1", 1),
        ("SCD2", 1),
    ]
    assert [(item.value, item.count) for item in report.execution_groups] == [
        ("health-daily", 2)
    ]
    assert [(item.value, item.count) for item in report.capture_engines] == [("SPARK", 2)]
    assert [(item.value, item.count) for item in report.apply_engines] == [("SPARK", 2)]
    assert report.warnings == ()


def test_validate_customer_project_requires_semantics_for_every_dataset(tmp_path) -> None:
    root = tmp_path / "health"
    _write_project_bundle(root)
    selections_path = root / "config/capture/semantic-selections.json"
    selections = json.loads(selections_path.read_text(encoding="utf-8"))
    selections_path.write_text(json.dumps(selections[:1]), encoding="utf-8")

    with pytest.raises(ValueError, match="missing semantic capture selection: claim"):
        validate_customer_project(root)


def test_validate_customer_project_rejects_unknown_dependency(tmp_path) -> None:
    root = tmp_path / "health"
    _write_project_bundle(root)
    claim_path = root / "config/datasets/claim.json"
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    claim["orchestration"]["dependencies"] = ["missing-upstream"]
    claim_path.write_text(json.dumps(claim), encoding="utf-8")

    with pytest.raises(ValueError, match="depends on unknown datasets: missing-upstream"):
        validate_customer_project(root)


def test_validate_customer_project_rejects_dependency_cycle(tmp_path) -> None:
    root = tmp_path / "health"
    _write_project_bundle(root)
    patient_path = root / "config/datasets/patient.json"
    patient = json.loads(patient_path.read_text(encoding="utf-8"))
    patient["orchestration"]["dependencies"] = ["claim"]
    patient_path.write_text(json.dumps(patient), encoding="utf-8")

    with pytest.raises(ValueError, match="dependency cycle"):
        validate_customer_project(root)


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


def test_project_validate_cli_returns_dry_run_summary(tmp_path, capsys) -> None:
    root = tmp_path / "health"
    _write_project_bundle(root)

    exit_code = cli_main(["project-validate", str(root)])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dataset_count"] == 2
    assert payload["semantic_selection_count"] == 2
    assert payload["apply_strategies"] == [
        {"count": 1, "value": "SCD1"},
        {"count": 1, "value": "SCD2"},
    ]


def test_project_validate_cli_can_write_report(tmp_path, capsys) -> None:
    root = tmp_path / "health"
    _write_project_bundle(root)
    output = tmp_path / "reports/project-validation.json"

    exit_code = cli_main(["project-validate", str(root), "--output", str(output)])

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["domain"] == "health"
    assert payload["dataset_count"] == 2
