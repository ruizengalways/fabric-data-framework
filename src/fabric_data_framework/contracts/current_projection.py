"""Provider-neutral contracts for current-state projections derived from SCD2 history.

The authoritative object is always the SCD2 history dataset. A current representation
is a rebuildable projection and must never become an independent interpretation of the
original source. VIEW and MATERIALIZED modes are deployment physicalizations; the
DELTA_PROJECTION mode owns an independent downstream checkpoint over history Delta CDF.
"""

from __future__ import annotations

from enum import Enum
import hashlib
from uuid import UUID

from pydantic import Field, model_validator

from .base import FrozenModel
from .typed_values import canonical_typed_json_bytes


class CurrentProjectionMode(str, Enum):
    VIEW = "VIEW"
    MATERIALIZED = "MATERIALIZED"
    DELTA_PROJECTION = "DELTA_PROJECTION"


class MaterializedCurrentImplementation(str, Enum):
    AUTO = "AUTO"
    FABRIC_MATERIALIZED_LAKE_VIEW = "FABRIC_MATERIALIZED_LAKE_VIEW"
    DELTA_TABLE_REFRESH = "DELTA_TABLE_REFRESH"


class CurrentProjectionConfig(FrozenModel):
    """Source-controlled semantics for one canonical current representation.

    ``authoritative_history_dataset_id`` points at the framework dataset that owns the
    canonical SCD2 history. The projection dataset must depend on that dataset. Mode 3
    consumes committed history Delta changes and therefore has its own downstream CDC
    checkpoint; it never consumes the original business source directly.
    """

    authoritative_history_dataset_id: str = Field(min_length=1)
    mode: CurrentProjectionMode = CurrentProjectionMode.VIEW
    history_current_flag_column: str = Field(default="_framework_is_current", min_length=1)
    materialized_implementation: MaterializedCurrentImplementation = (
        MaterializedCurrentImplementation.AUTO
    )
    lag_warning_versions: int = Field(default=1, ge=0)
    lag_error_versions: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_projection(self) -> "CurrentProjectionConfig":
        if self.history_current_flag_column != "_framework_is_current":
            raise ValueError(
                "current projections over framework SCD2 history must use "
                "'_framework_is_current'"
            )
        if (
            self.mode is not CurrentProjectionMode.MATERIALIZED
            and self.materialized_implementation
            is not MaterializedCurrentImplementation.AUTO
        ):
            raise ValueError(
                "materialized_implementation is only valid for MATERIALIZED current projection"
            )
        if (
            self.lag_error_versions is not None
            and self.lag_error_versions < self.lag_warning_versions
        ):
            raise ValueError("lag_error_versions cannot be less than lag_warning_versions")
        return self


class CurrentProjectionHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    LAGGING = "LAGGING"
    STALE = "STALE"
    UNINITIALIZED = "UNINITIALIZED"


class CurrentProjectionHealth(FrozenModel):
    dataset_id: str = Field(min_length=1)
    history_latest_delta_version: int = Field(ge=0)
    current_projection_processed_version: int | None = Field(default=None, ge=0)
    projection_lag: int = Field(ge=0)
    status: CurrentProjectionHealthStatus
    last_successful_projection_run_id: UUID | None = None


def current_projection_checkpoint_partition(
    *,
    table_reference: str,
    business_key: tuple[str, ...],
    projected_columns: tuple[str, ...],
    current_flag_column: str,
) -> str:
    """Bind Mode-3 runtime progress to the exact projection semantics it processed."""

    if (
        not table_reference
        or not business_key
        or not projected_columns
        or not current_flag_column
    ):
        raise ValueError("current projection checkpoint identity inputs cannot be empty")
    payload = {
        "semantic_version": 1,
        "table_reference": table_reference,
        "business_key": business_key,
        "projected_columns": projected_columns,
        "current_flag_column": current_flag_column,
    }
    digest = hashlib.sha256(canonical_typed_json_bytes(payload)).hexdigest()
    return f"current-projection:{digest}"


def evaluate_current_projection_health(
    *,
    dataset_id: str,
    history_latest_delta_version: int,
    processed_version: int | None,
    lag_warning_versions: int = 1,
    lag_error_versions: int | None = None,
    last_successful_projection_run_id: UUID | None = None,
) -> CurrentProjectionHealth:
    """Derive projection health without introducing a second operational state store."""

    if history_latest_delta_version < 0:
        raise ValueError("history_latest_delta_version must be non-negative")
    if lag_warning_versions < 0:
        raise ValueError("lag_warning_versions must be non-negative")
    if lag_error_versions is not None and lag_error_versions < lag_warning_versions:
        raise ValueError("lag_error_versions cannot be less than lag_warning_versions")
    if processed_version is not None:
        if processed_version < 0:
            raise ValueError("processed_version must be non-negative")
        if processed_version > history_latest_delta_version:
            raise ValueError(
                "current projection checkpoint cannot be ahead of authoritative history"
            )

    if processed_version is None:
        lag = history_latest_delta_version + 1
        status = CurrentProjectionHealthStatus.UNINITIALIZED
    else:
        lag = history_latest_delta_version - processed_version
        if lag == 0:
            status = CurrentProjectionHealthStatus.HEALTHY
        elif lag_error_versions is not None and lag >= lag_error_versions:
            status = CurrentProjectionHealthStatus.STALE
        elif lag < lag_warning_versions:
            status = CurrentProjectionHealthStatus.HEALTHY
        else:
            status = CurrentProjectionHealthStatus.LAGGING

    return CurrentProjectionHealth(
        dataset_id=dataset_id,
        history_latest_delta_version=history_latest_delta_version,
        current_projection_processed_version=processed_version,
        projection_lag=lag,
        status=status,
        last_successful_projection_run_id=last_successful_projection_run_id,
    )


__all__ = [
    "CurrentProjectionConfig",
    "CurrentProjectionHealth",
    "CurrentProjectionHealthStatus",
    "CurrentProjectionMode",
    "MaterializedCurrentImplementation",
    "current_projection_checkpoint_partition",
    "evaluate_current_projection_health",
]
