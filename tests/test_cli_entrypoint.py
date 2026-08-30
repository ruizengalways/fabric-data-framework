from __future__ import annotations

import fabric_data_framework.cli as cli
from fabric_data_framework.cli import approved


def test_cli_package_exports_main():
    assert callable(cli.main)


def test_approved_command_registry_matches_router_surface():
    assert approved.APPROVED_COMMANDS == {
        "integration-evidence-merge",
        "integration-control-plane-certify-run",
        "integration-pipeline-run",
        "integration-capture-run",
        "integration-warehouse-run",
        "integration-warehouse-fault-drill-run",
    }
