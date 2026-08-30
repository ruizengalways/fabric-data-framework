"""Deprecated compatibility alias for :mod:`fabric_data_framework.evidence.integration_checks`."""

from importlib import import_module as _import_module
import sys as _sys

_module = _import_module(".evidence.integration_checks", __package__)
_sys.modules[__name__] = _module
