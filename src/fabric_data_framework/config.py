"""Typed metadata contracts and effective runtime configuration resolution."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    """Base model for immutable, strict framework contracts."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class CaptureStrategy(str, Enum):
    FULL = "FULL"
    WATERMARK = "WATERMARK"
    CDC = "CDC"
    MIRROR = "MIRROR"
    STREAM = "STREAM"
    SNAPSHOT = "SNAPSHOT"


class ApplyStrategy(str, Enum):
    APPEND = "APPEND"
    REPLACE = "REPLACE"
    UPSERT = "UPSERT"
    SCD1 = "SCD1"
    SCD2 = "SCD2"
    SNAPSHOT_DIFF = "SNAPSHOT_DIFF"


class RunMode(str, Enum):
    NORMAL = "NORMAL"
    RETRY = "RETRY"
    BACKFILL = "BACKFILL"
    REPLAY = "REPLAY"
    FULL_REBUILD = "FULL_REBUILD"


class DatasetStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class PipelineStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class Criticality(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExecutionEngine(str, Enum):
    """Physical engine selected to perform the dataset capture/execution boundary."""

    AUTO = "AUTO"
    FABRIC_COPY_JOB = "FABRIC_COPY_JOB"
    FABRIC_COPY_ACTIVITY = "FABRIC_COPY_ACTIVITY"
    DATAFLOW_GEN2 = "DATAFLOW_GEN2"
    SPARK = "SPARK"
    FABRIC_MIRRORING = "FABRIC_MIRRORING"
    EXTERNAL_CDC = "EXTERNAL_CDC"
    SQL = "SQL"
    CUSTOM = "CUSTOM"


class ProgressOwner(str, Enum):
    """Single authoritative checkpoint owner for one physical capture operation."""

    FRAMEWORK = "FRAMEWORK"
    FABRIC_NATIVE = "FABRIC_NATIVE"
    EXTERNAL = "EXTERNAL"


class SourceConfig(FrozenModel):
    system: str = Field(min_length=1)
    object: str = Field(min_length=1)
    connection_ref: str | None = None


class TargetConfig(FrozenModel):
    layer: str = Field(min_length=1)
    object: str = Field(min_length=1)


class WatermarkConfig(FrozenModel):
    column: str = Field(min_length=1)
    tie_breaker: tuple[str, ...] = ()
    overlap_window_seconds: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_tie_breaker(self) -> "WatermarkConfig":
        if len(set(self.tie_breaker)) != len(self.tie_breaker):
            raise ValueError("watermark tie_breaker columns must be unique")
        if self.column in self.tie_breaker:
            raise ValueError("watermark column must not also be a tie_breaker column")
        return self


_STATEFUL_APPLY = {
    ApplyStrategy.UPSERT,
    ApplyStrategy.SCD1,
    ApplyStrategy.SCD2,
    ApplyStrategy.SNAPSHOT_DIFF,
}


class LoadPolicy(FrozenModel):
    capture_strategy: CaptureStrategy
    apply_strategy: ApplyStrategy
    business_key: tuple[str, ...] = ()
    merge_key: tuple[str, ...] = ()
    watermark: WatermarkConfig | None = None
    event_time_column: str | None = None
    version_column: str | None = None
    sequence_column: str | None = None
    tracked_columns: tuple[str, ...] = ()
    delete_policy: str = "IGNORE"

    @model_validator(mode="after")
    def validate_load_policy(self) -> "LoadPolicy":
        for label, columns in (
            ("business_key", self.business_key),
            ("merge_key", self.merge_key),
            ("tracked_columns", self.tracked_columns),
        ):
            if len(set(columns)) != len(columns):
                raise ValueError(f"{label} columns must be unique")

        if self.capture_strategy is CaptureStrategy.WATERMARK:
            if self.watermark is None:
                raise ValueError("WATERMARK capture requires watermark configuration")
            if not self.watermark.tie_breaker and self.watermark.overlap_window_seconds == 0:
                raise ValueError(
                    "WATERMARK capture requires a tie_breaker or a positive overlap window"
                )
        elif self.watermark is not None:
            raise ValueError("watermark configuration is only valid for WATERMARK capture")

        if self.apply_strategy in _STATEFUL_APPLY and not self.merge_key:
            raise ValueError(f"{self.apply_strategy.value} apply requires merge_key")
        if self.apply_strategy is ApplyStrategy.SCD2 and not self.business_key:
            raise ValueError("SCD2 apply requires business_key")
        return self


class OrchestrationPolicy(FrozenModel):
    execution_group: str = Field(min_length=1)
    criticality: Criticality = Criticality.MEDIUM
    dependencies: tuple[str, ...] = ()
    priority: int = Field(default=100, ge=0)
    retry_count: int = Field(default=2, ge=0)
    timeout_seconds: int = Field(default=3600, gt=0)
    batch_size: int = Field(default=100_000, gt=0)
    max_concurrency: int = Field(default=4, gt=0)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "OrchestrationPolicy":
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("dependencies must be unique")
        return self


class DataQualityPolicy(FrozenModel):
    policy_name: str = Field(min_length=1)
    quarantine_policy: str = Field(min_length=1)


class ReconciliationPolicy(FrozenModel):
    policy_name: str = Field(min_length=1)
    required_for_state_commit: bool = True


class ExecutionPolicy(FrozenModel):
    """Source-controlled physical execution selection for one dataset."""

    engine: ExecutionEngine = ExecutionEngine.AUTO
    progress_owner: ProgressOwner = ProgressOwner.FRAMEWORK
    capability_profile: str | None = None


_EXTENSION_NAME_PATTERN = r"^[a-z][a-z0-9_.-]*$"


class ExtensionConfig(FrozenModel):
    """Logical names resolved from a controlled domain extension registry."""

    capture: str | None = Field(default=None, pattern=_EXTENSION_NAME_PATTERN)
    parser: str | None = Field(default=None, pattern=_EXTENSION_NAME_PATTERN)
    transform: str | None = Field(default=None, pattern=_EXTENSION_NAME_PATTERN)
    quality: str | None = Field(default=None, pattern=_EXTENSION_NAME_PATTERN)
    apply: str | None = Field(default=None, pattern=_EXTENSION_NAME_PATTERN)


class DatasetConfig(FrozenModel):
    dataset_id: str = Field(min_length=1)
    source: SourceConfig
    target: TargetConfig
    load: LoadPolicy
    orchestration: OrchestrationPolicy
    quality: DataQualityPolicy
    reconciliation: ReconciliationPolicy
    execution: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    extensions: ExtensionConfig = Field(default_factory=ExtensionConfig)
    enabled: bool = True
    config_schema_version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_dataset(self) -> "DatasetConfig":
        if self.dataset_id in self.orchestration.dependencies:
            raise ValueError("dataset must not depend on itself")
        if self.execution.engine is ExecutionEngine.CUSTOM and not self.extensions.capture:
            raise ValueError("CUSTOM execution requires extensions.capture")
        return self

    @property
    def config_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class OverrideField(str, Enum):
    ENABLED = "enabled"
    PRIORITY = "orchestration.priority"
    RETRY_COUNT = "orchestration.retry_count"
    TIMEOUT_SECONDS = "orchestration.timeout_seconds"
    BATCH_SIZE = "orchestration.batch_size"
    MAX_CONCURRENCY = "orchestration.max_concurrency"
    WATERMARK_OVERLAP_SECONDS = "load.watermark.overlap_window_seconds"


_BOOL_OVERRIDE_FIELDS = {OverrideField.ENABLED}
_NONNEGATIVE_INT_OVERRIDE_FIELDS = {
    OverrideField.PRIORITY,
    OverrideField.RETRY_COUNT,
    OverrideField.WATERMARK_OVERLAP_SECONDS,
}
_POSITIVE_INT_OVERRIDE_FIELDS = {
    OverrideField.TIMEOUT_SECONDS,
    OverrideField.BATCH_SIZE,
    OverrideField.MAX_CONCURRENCY,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class RuntimeOverride(FrozenModel):
    override_id: UUID = Field(default_factory=uuid4)
    dataset_id: str = Field(min_length=1)
    field: OverrideField
    value: bool | int
    reason: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=_utcnow)
    valid_from: datetime = Field(default_factory=_utcnow)
    valid_to: datetime | None = None
    precedence: int = Field(default=0, ge=0)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_override(self) -> "RuntimeOverride":
        _require_aware(self.created_at, "created_at")
        _require_aware(self.valid_from, "valid_from")
        if self.valid_to is not None:
            _require_aware(self.valid_to, "valid_to")
            if self.valid_to <= self.valid_from:
                raise ValueError("valid_to must be after valid_from")

        if self.field in _BOOL_OVERRIDE_FIELDS:
            if type(self.value) is not bool:
                raise ValueError(f"{self.field.value} override requires bool value")
        elif self.field in _NONNEGATIVE_INT_OVERRIDE_FIELDS:
            if type(self.value) is not int or self.value < 0:
                raise ValueError(f"{self.field.value} override requires non-negative int")
        elif self.field in _POSITIVE_INT_OVERRIDE_FIELDS:
            if type(self.value) is not int or self.value <= 0:
                raise ValueError(f"{self.field.value} override requires positive int")
        return self

    def is_active(self, at: datetime) -> bool:
        _require_aware(at, "at")
        return self.enabled and self.valid_from <= at and (
            self.valid_to is None or at < self.valid_to
        )


class EffectiveDatasetConfig(FrozenModel):
    config: DatasetConfig
    base_config_hash: str
    effective_config_hash: str
    applied_override_ids: tuple[UUID, ...] = ()


class OverrideConflictError(ValueError):
    """Raised when equally-precedent active overrides disagree."""


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _select_overrides(
    config: DatasetConfig,
    overrides: tuple[RuntimeOverride, ...],
    as_of: datetime,
) -> tuple[RuntimeOverride, ...]:
    grouped: dict[OverrideField, list[RuntimeOverride]] = defaultdict(list)
    for override in overrides:
        if override.dataset_id != config.dataset_id:
            raise ValueError(
                f"override {override.override_id} targets {override.dataset_id}, "
                f"not {config.dataset_id}"
            )
        if override.is_active(as_of):
            grouped[override.field].append(override)

    selected: list[RuntimeOverride] = []
    for field, candidates in grouped.items():
        highest_precedence = max(item.precedence for item in candidates)
        winners = [item for item in candidates if item.precedence == highest_precedence]
        distinct_values = {json.dumps(item.value, sort_keys=True) for item in winners}
        if len(distinct_values) > 1:
            raise OverrideConflictError(
                f"conflicting active overrides for {field.value} at precedence "
                f"{highest_precedence}"
            )
        selected.append(max(winners, key=lambda item: (item.created_at, str(item.override_id))))
    return tuple(sorted(selected, key=lambda item: item.field.value))


def _apply_override(config: DatasetConfig, override: RuntimeOverride) -> DatasetConfig:
    field = override.field
    value = override.value

    if field is OverrideField.ENABLED:
        return config.model_copy(update={"enabled": value})

    if field in {
        OverrideField.PRIORITY,
        OverrideField.RETRY_COUNT,
        OverrideField.TIMEOUT_SECONDS,
        OverrideField.BATCH_SIZE,
        OverrideField.MAX_CONCURRENCY,
    }:
        attribute = field.value.split(".")[-1]
        orchestration = config.orchestration.model_copy(update={attribute: value})
        return config.model_copy(update={"orchestration": orchestration})

    if field is OverrideField.WATERMARK_OVERLAP_SECONDS:
        if config.load.watermark is None:
            raise ValueError("watermark overlap override requires WATERMARK configuration")
        watermark = config.load.watermark.model_copy(update={"overlap_window_seconds": value})
        load = config.load.model_copy(update={"watermark": watermark})
        return config.model_copy(update={"load": load})

    raise ValueError(f"unsupported override field: {field}")


def resolve_effective_config(
    config: DatasetConfig,
    overrides: tuple[RuntimeOverride, ...] = (),
    *,
    as_of: datetime | None = None,
) -> EffectiveDatasetConfig:
    """Resolve audited operational overrides into one immutable execution snapshot."""

    evaluation_time = as_of or _utcnow()
    _require_aware(evaluation_time, "as_of")
    selected = _select_overrides(config, overrides, evaluation_time)
    effective = config
    for override in selected:
        effective = _apply_override(effective, override)

    return EffectiveDatasetConfig(
        config=effective,
        base_config_hash=config.config_hash,
        effective_config_hash=effective.config_hash,
        applied_override_ids=tuple(item.override_id for item in selected),
    )
