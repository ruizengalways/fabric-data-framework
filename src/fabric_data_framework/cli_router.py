"""Deprecated compatibility alias for the pre-package CLI router.

All CLI implementation lives under :mod:`fabric_data_framework.cli`. New code
should import ``fabric_data_framework.cli`` or ``fabric_data_framework.cli.approved``.
This module intentionally contains no CLI/business implementation.
"""

from __future__ import annotations

import sys

from .cli import approved as _approved
from .cli.main import main as _main

# Preserve old tests/extensions that monkeypatch symbols on ``cli_router``: make
# this historical module name resolve to the actual approved command module.
_approved.main = _main
sys.modules[__name__] = _approved
