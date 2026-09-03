"""Console-script composition root.

Only this module decides which CLI command family handles an invocation. The
reusable framework never depends on this package.
"""

from __future__ import annotations

import sys

from .approved import run_if_matched as run_approved_if_matched
from .base import main as run_base
from .business_path import run_if_matched as run_business_path_if_matched
from .certification import run_if_matched as run_certification_if_matched
from .project import run_if_matched as run_project_if_matched
from .release import run_if_matched as run_release_if_matched


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    project_result = run_project_if_matched(effective_argv)
    if project_result is not None:
        return project_result
    release_result = run_release_if_matched(effective_argv)
    if release_result is not None:
        return release_result
    certification_result = run_certification_if_matched(effective_argv)
    if certification_result is not None:
        return certification_result
    business_path_result = run_business_path_if_matched(effective_argv)
    if business_path_result is not None:
        return business_path_result
    approved_result = run_approved_if_matched(effective_argv)
    if approved_result is not None:
        return approved_result
    return run_base(effective_argv)


__all__ = ["main"]
