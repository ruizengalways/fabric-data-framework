"""Bounded domain extension discovery and registration."""

from .registry import (
    ExtensionKind,
    ExtensionNotFoundError,
    ExtensionRegistrationError,
    ExtensionRegistry,
)

__all__ = [
    "ExtensionKind",
    "ExtensionNotFoundError",
    "ExtensionRegistrationError",
    "ExtensionRegistry",
]
