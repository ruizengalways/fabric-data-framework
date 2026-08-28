"""Compatibility export for stage-specific control-plane definitions.

The canonical ``apply_execution_policy`` table now lives in ``control_plane.py`` so
schema creation, deployment classification and CLI migration all see the same
metadata.  This module remains temporarily to avoid breaking the in-flight delivery
import while the unreleased package structure is hardened.
"""

from .control_plane import apply_execution_policy

__all__ = ["apply_execution_policy"]
