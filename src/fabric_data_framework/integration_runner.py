"""Deprecated compatibility alias for :mod:`fabric_data_framework.evidence.integration_runner`."""

from importlib import import_module as _import_module
import sys as _sys

_module = _import_module(".evidence.integration_runner", __package__)
_sys.modules[__name__] = _module
