from __future__ import annotations

from fabric_data_framework import cli_router
from fabric_data_framework.cli import approved


def test_legacy_cli_router_resolves_to_approved_cli_module():
    assert cli_router is approved
    assert callable(cli_router.main)
