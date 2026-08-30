"""Optional command-line interface for fabric-data-framework.

Dependency direction is intentionally one-way: ``cli -> framework core``.
Importing or using the framework core must not require this package.
"""

from .main import main

__all__ = ["main"]
