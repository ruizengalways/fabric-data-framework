"""Controlled domain extension registry.

Metadata refers to logical names; implementations are registered explicitly or via
Python package entry points. Arbitrary import paths are not executed from metadata.
"""

from __future__ import annotations

from enum import Enum
from importlib.metadata import entry_points
from typing import Any, Callable


class ExtensionKind(str, Enum):
    CAPTURE = "capture"
    PARSER = "parser"
    TRANSFORM = "transform"
    QUALITY = "quality"
    APPLY = "apply"
    CAPTURE_OBSERVER = "capture_observer"
    SPARK_EXECUTION_DATA = "spark_execution_data"
    WAREHOUSE_MUTATION = "warehouse_mutation"
    WAREHOUSE_COMMIT_FAULT_INJECTOR = "warehouse_commit_fault_injector"
    BUSINESS_PATH_OBSERVER = "business_path_observer"
    BUSINESS_PATH_DRIVER = "business_path_driver"

    @property
    def entry_point_group(self) -> str:
        if self is ExtensionKind.CAPTURE_OBSERVER:
            return "fabric_data_framework.capture_observers"
        if self is ExtensionKind.SPARK_EXECUTION_DATA:
            return "fabric_data_framework.spark_execution_data"
        if self is ExtensionKind.WAREHOUSE_MUTATION:
            return "fabric_data_framework.warehouse_mutations"
        if self is ExtensionKind.WAREHOUSE_COMMIT_FAULT_INJECTOR:
            return "fabric_data_framework.warehouse_commit_fault_injectors"
        if self is ExtensionKind.BUSINESS_PATH_OBSERVER:
            return "fabric_data_framework.business_path_observers"
        if self is ExtensionKind.BUSINESS_PATH_DRIVER:
            return "fabric_data_framework.business_path_drivers"
        return f"fabric_data_framework.{self.value}s"


class ExtensionRegistrationError(ValueError):
    pass


class ExtensionNotFoundError(LookupError):
    pass


class ExtensionRegistry:
    def __init__(self) -> None:
        self._items: dict[tuple[ExtensionKind, str], Any] = {}

    def register(self, kind: ExtensionKind, name: str, implementation: Any) -> None:
        key = (kind, name)
        if key in self._items:
            raise ExtensionRegistrationError(
                f"extension already registered: {kind.value}:{name}"
            )
        self._items[key] = implementation

    def resolve(self, kind: ExtensionKind, name: str) -> Any:
        try:
            return self._items[(kind, name)]
        except KeyError as exc:
            raise ExtensionNotFoundError(
                f"extension not registered: {kind.value}:{name}"
            ) from exc

    def discover(self, kind: ExtensionKind) -> tuple[str, ...]:
        discovered: list[str] = []
        for item in entry_points(group=kind.entry_point_group):
            self.register(kind, item.name, item.load())
            discovered.append(item.name)
        return tuple(sorted(discovered))

    def factory(self, kind: ExtensionKind, name: str) -> Callable[..., Any]:
        implementation = self.resolve(kind, name)
        if not callable(implementation):
            raise TypeError(f"extension is not callable: {kind.value}:{name}")
        return implementation
