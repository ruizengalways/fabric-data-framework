"""Deployment planning for current representations derived from SCD2 history."""

from __future__ import annotations

from typing import Iterable

from pydantic import Field

from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.contracts.current_projection import (
    CurrentProjectionMode,
    MaterializedCurrentImplementation,
)
from fabric_data_framework.metadata.config import ApplyStrategy, DatasetConfig
from fabric_data_framework.metadata.config import ExecutionEngine


class CurrentProjectionDeploymentPlan(FrozenModel):
    dataset_id: str = Field(min_length=1)
    mode: CurrentProjectionMode
    source_relation: str = Field(min_length=1)
    target_relation: str = Field(min_length=1)
    projected_columns: tuple[str, ...]
    create_or_replace_sql: str | None = None
    refresh_sql: str | None = None
    enable_history_cdf_sql: str | None = None
    requires_incremental_runtime: bool = False
    materialized_implementation: MaterializedCurrentImplementation | None = None
    incremental_refresh_expected: bool | None = None


def _quote_part(value: str) -> str:
    if not value:
        raise ValueError("SQL identifier segment cannot be empty")
    return "`" + value.replace("`", "``") + "`"


def quote_spark_relation(value: str) -> str:
    parts = tuple(value.split("."))
    if not parts or any(not part for part in parts):
        raise ValueError(f"invalid Spark relation identifier: {value!r}")
    return ".".join(_quote_part(part) for part in parts)


def _source_relation(config: DatasetConfig) -> str:
    return quote_spark_relation(config.source.object)


def _target_relation(config: DatasetConfig) -> str:
    return ".".join((_quote_part(config.target.layer), _quote_part(config.target.object)))


def _projected_columns(config: DatasetConfig) -> tuple[str, ...]:
    if config.schema_contract is None:
        raise ValueError("current projection dataset requires schema_contract")
    return tuple(field.name for field in config.schema_contract.fields)


def _select_sql(config: DatasetConfig) -> str:
    projection = config.current_projection
    if projection is None:
        raise ValueError("dataset is not a current projection")
    columns = _projected_columns(config)
    column_sql = ", ".join(_quote_part(column) for column in columns)
    return (
        f"SELECT {column_sql} FROM {_source_relation(config)} "
        f"WHERE {_quote_part(projection.history_current_flag_column)} = true"
    )


def compile_current_projection_deployment(
    config: DatasetConfig,
) -> CurrentProjectionDeploymentPlan:
    """Compile stable current-projection semantics into Fabric Spark SQL/runtime intent."""

    projection = config.current_projection
    if projection is None or config.load.apply_strategy is not ApplyStrategy.CURRENT_PROJECTION:
        raise ValueError("dataset is not configured as CURRENT_PROJECTION")
    if config.execution.engine not in {ExecutionEngine.AUTO, ExecutionEngine.SPARK} or (
        config.execution.apply_engine not in {ExecutionEngine.AUTO, ExecutionEngine.SPARK}
    ):
        raise ValueError(
            "Spark SQL current-projection deployment requires AUTO or SPARK capture/apply engines"
        )

    source = _source_relation(config)
    target = _target_relation(config)
    columns = _projected_columns(config)
    select_sql = _select_sql(config)

    if projection.mode is CurrentProjectionMode.VIEW:
        return CurrentProjectionDeploymentPlan(
            dataset_id=config.dataset_id,
            mode=projection.mode,
            source_relation=source,
            target_relation=target,
            projected_columns=columns,
            create_or_replace_sql=f"CREATE OR REPLACE VIEW {target} AS {select_sql}",
        )

    if projection.mode is CurrentProjectionMode.MATERIALIZED:
        implementation = projection.materialized_implementation
        if implementation is MaterializedCurrentImplementation.AUTO:
            implementation = MaterializedCurrentImplementation.FABRIC_MATERIALIZED_LAKE_VIEW
        cdf_sql = (
            f"ALTER TABLE {source} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)"
        )
        if implementation is MaterializedCurrentImplementation.FABRIC_MATERIALIZED_LAKE_VIEW:
            return CurrentProjectionDeploymentPlan(
                dataset_id=config.dataset_id,
                mode=projection.mode,
                source_relation=source,
                target_relation=target,
                projected_columns=columns,
                create_or_replace_sql=(
                    f"CREATE OR REPLACE MATERIALIZED LAKE VIEW {target} AS {select_sql}"
                ),
                refresh_sql=f"REFRESH MATERIALIZED LAKE VIEW {target}",
                enable_history_cdf_sql=cdf_sql,
                materialized_implementation=implementation,
                # SCD2 normally updates the former current row to is_current=false.
                # Fabric MLV optimal refresh therefore falls back to full refresh for
                # refresh cycles that observe those source updates/deletes.
                incremental_refresh_expected=False,
            )
        return CurrentProjectionDeploymentPlan(
            dataset_id=config.dataset_id,
            mode=projection.mode,
            source_relation=source,
            target_relation=target,
            projected_columns=columns,
            create_or_replace_sql=(
                f"CREATE OR REPLACE TABLE {target} USING DELTA AS {select_sql}"
            ),
            refresh_sql=f"CREATE OR REPLACE TABLE {target} USING DELTA AS {select_sql}",
            materialized_implementation=implementation,
            incremental_refresh_expected=False,
        )

    if projection.mode is CurrentProjectionMode.DELTA_PROJECTION:
        return CurrentProjectionDeploymentPlan(
            dataset_id=config.dataset_id,
            mode=projection.mode,
            source_relation=source,
            target_relation=target,
            projected_columns=columns,
            enable_history_cdf_sql=(
                f"ALTER TABLE {source} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)"
            ),
            requires_incremental_runtime=True,
            incremental_refresh_expected=True,
        )

    raise ValueError(f"unsupported current projection mode: {projection.mode}")


def recommended_current_object_name(history_object: str) -> str:
    """Return the preferred consumer-facing name for a ``*_history`` object."""

    leaf = history_object.split(".")[-1]
    if not leaf.endswith("_history") or leaf == "_history":
        raise ValueError("history object must end with '_history' to derive a current name")
    return leaf[: -len("_history")]


def validate_current_projection_bundle(
    configs: Iterable[DatasetConfig],
) -> tuple[str, ...]:
    """Validate cross-dataset ownership and return non-blocking naming/cost warnings."""

    items = tuple(configs)
    by_id = {config.dataset_id: config for config in items}
    if len(by_id) != len(items):
        raise ValueError("dataset bundle contains duplicate dataset_id values")

    warnings: list[str] = []
    for config in items:
        projection = config.current_projection
        if projection is None:
            continue
        try:
            history = by_id[projection.authoritative_history_dataset_id]
        except KeyError as exc:
            raise ValueError(
                f"current projection {config.dataset_id!r} references unknown authoritative "
                f"history dataset {projection.authoritative_history_dataset_id!r}"
            ) from exc
        if history.load.apply_strategy is not ApplyStrategy.SCD2:
            raise ValueError(
                f"current projection {config.dataset_id!r} authoritative dataset must use SCD2"
            )
        if config.source.system != "framework_dataset":
            raise ValueError(
                f"current projection {config.dataset_id!r} source system must be 'framework_dataset'"
            )
        if projection.authoritative_history_dataset_id not in config.orchestration.dependencies:
            raise ValueError(
                f"current projection {config.dataset_id!r} must depend on its authoritative history dataset"
            )
        if config.load.business_key != history.load.business_key:
            raise ValueError(
                f"current projection {config.dataset_id!r} business_key must equal authoritative history business_key"
            )
        expected_source = f"{history.target.layer}.{history.target.object}"
        if config.source.object != expected_source:
            raise ValueError(
                f"current projection {config.dataset_id!r} source must exactly reference "
                f"authoritative history target {expected_source!r}"
            )
        if config.target.object == history.target.object and config.target.layer == history.target.layer:
            raise ValueError("current projection target must differ from authoritative history target")

        if history.schema_contract is None:
            raise ValueError(
                f"current projection {config.dataset_id!r} authoritative history "
                "requires an explicit schema contract"
            )
        if config.schema_contract is not None:
            history_fields = {field.name: field for field in history.schema_contract.fields}
            projection_fields = {field.name: field for field in config.schema_contract.fields}
            missing_keys = sorted(set(config.load.business_key) - set(projection_fields))
            if missing_keys:
                raise ValueError(
                    f"current projection {config.dataset_id!r} schema must include business key fields: "
                    + ", ".join(missing_keys)
                )
            unknown = sorted(set(projection_fields) - set(history_fields))
            if unknown:
                raise ValueError(
                    f"current projection {config.dataset_id!r} schema contains fields absent from history contract: "
                    + ", ".join(unknown)
                )
            incompatible = sorted(
                name
                for name, field in projection_fields.items()
                if field != history_fields[name]
            )
            if incompatible:
                raise ValueError(
                    f"current projection {config.dataset_id!r} schema fields do not match "
                    "authoritative history types/nullability: "
                    + ", ".join(incompatible)
                )

        try:
            recommended = recommended_current_object_name(history.target.object)
        except ValueError:
            recommended = None
        if recommended is not None and config.target.object != recommended:
            warnings.append(
                f"{config.dataset_id}: preferred current object name is {recommended!r} for history {history.target.object!r}"
            )
        if projection.mode is CurrentProjectionMode.MATERIALIZED:
            warnings.append(
                f"{config.dataset_id}: Fabric Materialized Lake View refresh cycles that observe SCD2 source updates/deletes may fall back to full refresh"
            )

    return tuple(warnings)


__all__ = [
    "CurrentProjectionDeploymentPlan",
    "compile_current_projection_deployment",
    "quote_spark_relation",
    "recommended_current_object_name",
    "validate_current_projection_bundle",
]
