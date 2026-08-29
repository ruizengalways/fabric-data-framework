"""Provider-neutral source/target schema contracts.

The framework models schema intent independently of Spark/Delta/SQL provider types so
compatibility policy is source-controlled and deterministic rather than delegated to
a runtime engine's automatic schema-merging behavior.
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenSchemaModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class SchemaCompatibilityPolicy(str, Enum):
    EXACT = "EXACT"
    ADDITIVE_ONLY = "ADDITIVE_ONLY"
    SAFE_EVOLUTION = "SAFE_EVOLUTION"


class LogicalType(str, Enum):
    BOOLEAN = "BOOLEAN"
    INT32 = "INT32"
    INT64 = "INT64"
    FLOAT32 = "FLOAT32"
    FLOAT64 = "FLOAT64"
    DECIMAL = "DECIMAL"
    STRING = "STRING"
    DATE = "DATE"
    TIMESTAMP = "TIMESTAMP"
    BINARY = "BINARY"
    JSON = "JSON"


class SchemaField(FrozenSchemaModel):
    name: str = Field(min_length=1)
    logical_type: LogicalType
    nullable: bool = True
    precision: int | None = Field(default=None, gt=0)
    scale: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_type_parameters(self) -> "SchemaField":
        if self.logical_type is LogicalType.DECIMAL:
            if self.precision is None or self.scale is None:
                raise ValueError("DECIMAL requires precision and scale")
            if self.scale > self.precision:
                raise ValueError("DECIMAL scale cannot exceed precision")
        elif self.precision is not None or self.scale is not None:
            raise ValueError("precision/scale are only valid for DECIMAL")

        if self.logical_type is not LogicalType.STRING and self.max_length is not None:
            raise ValueError("max_length is only valid for STRING")
        return self

    def canonical_definition(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class SchemaShape(FrozenSchemaModel):
    fields: tuple[SchemaField, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_fields(self) -> "SchemaShape":
        names = [field.name for field in self.fields]
        if len(set(names)) != len(names):
            raise ValueError("schema field names must be unique")
        return self

    def canonical_definition(self) -> list[dict[str, object]]:
        return [
            field.canonical_definition()
            for field in sorted(self.fields, key=lambda item: item.name)
        ]

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.canonical_definition(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class SchemaContract(SchemaShape):
    contract_version: int = Field(default=1, ge=1)
    compatibility_policy: SchemaCompatibilityPolicy = SchemaCompatibilityPolicy.EXACT

    def persisted_definition(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "compatibility_policy": self.compatibility_policy.value,
            "fields": self.canonical_definition(),
        }


__all__ = [
    "LogicalType",
    "SchemaCompatibilityPolicy",
    "SchemaContract",
    "SchemaField",
    "SchemaShape",
]
