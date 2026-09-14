"""Minimal structural Spark protocols shared by Fabric adapters.

The framework intentionally avoids importing pyspark at package-import time so the wheel
remains usable for local validation, planning, and installed-wheel certification.
"""

from __future__ import annotations

from typing import Protocol


class SparkFrameLike(Protocol):
    def collect(self): ...
    def createOrReplaceTempView(self, name: str) -> None: ...


class SparkReaderLike(Protocol):
    def format(self, value: str) -> "SparkReaderLike": ...
    def option(self, key: str, value: object) -> "SparkReaderLike": ...
    def table(self, name: str) -> SparkFrameLike: ...


class SparkCatalogLike(Protocol):
    def tableExists(self, name: str) -> bool: ...


class SparkSessionLike(Protocol):
    @property
    def read(self) -> SparkReaderLike: ...

    @property
    def catalog(self) -> SparkCatalogLike: ...

    def sql(self, query: str) -> SparkFrameLike: ...


__all__ = [
    "SparkCatalogLike",
    "SparkFrameLike",
    "SparkReaderLike",
    "SparkSessionLike",
]
