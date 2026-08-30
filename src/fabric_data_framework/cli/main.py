"""Console-script composition root.

Only this module decides which CLI command family handles an invocation. The
reusable framework never depends on this package.
"""

from __future__ import annotations

import sys

from .approved import run_if_matched
from .base import main as run_base


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    approved_result = run_if_matched(effective_argv)
    if approved_result is not None:
        return approved_result
    return run_base(effective_argv)


__all__ = ["main"]
