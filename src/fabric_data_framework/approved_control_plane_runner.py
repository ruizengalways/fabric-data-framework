"""Deprecated compatibility alias for :mod:`fabric_data_framework.evidence.approved_control_plane_runner`."""

from importlib import import_module as _import_module
import sys as _sys

_module = _import_module(".evidence.approved_control_plane_runner", __package__)
_sys.modules[__name__] = _module
