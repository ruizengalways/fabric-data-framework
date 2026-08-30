from __future__ import annotations

import json

from fabric_data_framework.cli.main import main


CANDIDATE = "a" * 40


def _write_spec(path):
    path.write_text(
        json.dumps(
            {
                "readiness_schema_version": 1,
                "framework_version": "0.4.0",
                "gates": [
                    {
                        "gate_id": "source.tests",
                        "kind": "SOURCE_VERIFICATION",
                        "required": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_release_readiness_cli_writes_blocked_report_without_claiming_evidence(tmp_path):
    spec = tmp_path / "spec.json"
    output = tmp_path / "report.json"
    _write_spec(spec)

    exit_code = main(
        [
            "release-readiness",
            "--spec",
            str(spec),
            "--candidate-sha",
            CANDIDATE,
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["release_ready"] is False
    assert report["blockers"] == ["source.tests"]
    assert report["results"][0]["status"] == "NOT_RUN"


def test_release_readiness_cli_require_ready_exits_nonzero(tmp_path, capsys):
    spec = tmp_path / "spec.json"
    _write_spec(spec)

    exit_code = main(
        [
            "release-readiness",
            "--spec",
            str(spec),
            "--candidate-sha",
            CANDIDATE,
            "--require-ready",
        ]
    )

    assert exit_code == 2
    assert "release candidate is blocked" in capsys.readouterr().err
