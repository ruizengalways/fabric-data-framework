"""Provider-neutral orchestration planning and dependency decisions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Mapping

from fabric_data_framework.metadata.config import (
    Criticality,
    DatasetStatus,
    EffectiveDatasetConfig,
    PipelineStatus,
    RuntimeOverride,
    resolve_effective_config,
)
from ..contracts.dispatch import DatasetDispatchOutcome
from ..metadata.capabilities import CapabilityRegistry, DEFAULT_CAPABILITY_REGISTRY
from ..control_plane.repository import ControlPlaneRepository


_DEFAULT_REQUIRED_CRITICALITIES = frozenset({Criticality.HIGH, Criticality.CRITICAL})


class PipelineFailurePolicy(str, Enum):
    """How terminal dataset outcomes determine the parent Pipeline status.

    FAIL_AT_END is the production default: dataset fault boundaries isolate siblings,
    every independently runnable dataset is allowed to finish, and any terminal
    non-success makes the parent Pipeline fail only after aggregation.  The legacy
    CRITICALITY_AWARE mode remains available for domains that intentionally tolerate
    LOW/MEDIUM failures as PARTIAL_SUCCESS.
    """

    FAIL_AT_END = "FAIL_AT_END"
    CRITICALITY_AWARE = "CRITICALITY_AWARE"


class OrchestrationIntegrityError(RuntimeError):
    """Raised when deployed metadata cannot be scheduled safely."""


@dataclass(frozen=True)
class DispatchPlan:
    """Immutable selection/dependency plan independent of an execution backend."""

    evaluation_time: datetime
    selected_dataset_ids: tuple[str, ...]
    effective_configs: tuple[tuple[str, EffectiveDatasetConfig], ...]
    deployed_dataset_ids: frozenset[str]
    max_concurrency: int

    def effective_for(self, dataset_id: str) -> EffectiveDatasetConfig:
        for candidate, effective in self.effective_configs:
            if candidate == dataset_id:
                return effective
        raise KeyError(f"dataset not selected in dispatch plan: {dataset_id}")

    @property
    def selected_dataset_id_set(self) -> frozenset[str]:
        return frozenset(self.selected_dataset_ids)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _overrides_by_dataset(
    overrides: Iterable[RuntimeOverride],
) -> dict[str, tuple[RuntimeOverride, ...]]:
    grouped: dict[str, list[RuntimeOverride]] = defaultdict(list)
    for override in overrides:
        grouped[override.dataset_id].append(override)
    return {dataset_id: tuple(items) for dataset_id, items in grouped.items()}


def _validate_dependency_graph(
    selected: Mapping[str, EffectiveDatasetConfig],
    deployed_ids: frozenset[str],
) -> None:
    for dataset_id, effective in selected.items():
        for dependency in effective.config.orchestration.dependencies:
            if dependency not in deployed_ids:
                raise OrchestrationIntegrityError(
                    f"dataset {dataset_id} depends on undeployed dataset {dependency}"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(dataset_id: str) -> None:
        if dataset_id in visited:
            return
        if dataset_id in visiting:
            raise OrchestrationIntegrityError(
                f"dependency cycle detected at dataset {dataset_id}"
            )
        visiting.add(dataset_id)
        for dependency in selected[dataset_id].config.orchestration.dependencies:
            if dependency in selected:
                visit(dependency)
        visiting.remove(dataset_id)
        visited.add(dataset_id)

    for dataset_id in sorted(selected):
        visit(dataset_id)


def build_dispatch_plan(
    *,
    repository: ControlPlaneRepository,
    execution_group: str | None = None,
    requested_dataset_ids: Iterable[str] | None = None,
    overrides: Iterable[RuntimeOverride] = (),
    max_concurrency: int = 4,
    as_of: datetime | None = None,
    capability_registry: CapabilityRegistry = DEFAULT_CAPABILITY_REGISTRY,
) -> DispatchPlan:
    """Resolve effective metadata and validate engine compatibility before execution."""

    if max_concurrency <= 0:
        raise ValueError("max_concurrency must be positive")

    evaluation_time = as_of or _utcnow()
    deployed = {config.dataset_id: config for config in repository.list_datasets()}
    deployed_ids = frozenset(deployed)
    requested = None if requested_dataset_ids is None else frozenset(requested_dataset_ids)

    if requested is not None:
        unknown = sorted(requested - deployed_ids)
        if unknown:
            raise OrchestrationIntegrityError(
                f"requested datasets are not deployed: {','.join(unknown)}"
            )

    overrides_by_dataset = _overrides_by_dataset(overrides)
    unknown_override_ids = sorted(set(overrides_by_dataset) - deployed_ids)
    if unknown_override_ids:
        raise OrchestrationIntegrityError(
            "runtime overrides target undeployed datasets: " + ",".join(unknown_override_ids)
        )

    effective_by_id: dict[str, EffectiveDatasetConfig] = {}
    for dataset_id, base in deployed.items():
        effective = resolve_effective_config(
            base,
            overrides_by_dataset.get(dataset_id, ()),
            as_of=evaluation_time,
        )
        config = effective.config
        if not config.enabled:
            continue
        if execution_group is not None and config.orchestration.execution_group != execution_group:
            continue
        if requested is not None and dataset_id not in requested:
            continue
        capability_registry.validate(config)
        effective_by_id[dataset_id] = effective

    _validate_dependency_graph(effective_by_id, deployed_ids)

    selected_ids = tuple(
        sorted(
            effective_by_id,
            key=lambda dataset_id: (
                effective_by_id[dataset_id].config.orchestration.priority,
                dataset_id,
            ),
        )
    )

    if effective_by_id:
        config_limit = min(
            item.config.orchestration.max_concurrency for item in effective_by_id.values()
        )
        effective_concurrency = min(max_concurrency, config_limit, len(effective_by_id))
    else:
        effective_concurrency = 1

    return DispatchPlan(
        evaluation_time=evaluation_time,
        selected_dataset_ids=selected_ids,
        effective_configs=tuple(
            (dataset_id, effective_by_id[dataset_id]) for dataset_id in selected_ids
        ),
        deployed_dataset_ids=deployed_ids,
        max_concurrency=effective_concurrency,
    )


def blocking_dependencies(
    plan: DispatchPlan,
    dataset_id: str,
    outcomes: Mapping[str, DatasetDispatchOutcome],
) -> tuple[str, ...]:
    dependencies = plan.effective_for(dataset_id).config.orchestration.dependencies
    selected = plan.selected_dataset_id_set
    unavailable = tuple(dependency for dependency in dependencies if dependency not in selected)
    failed = tuple(
        dependency
        for dependency in dependencies
        if dependency in outcomes
        and outcomes[dependency].status is not DatasetStatus.SUCCEEDED
    )
    return tuple(sorted(set(unavailable + failed)))


def ready_dataset_ids(
    plan: DispatchPlan,
    remaining: set[str],
    outcomes: Mapping[str, DatasetDispatchOutcome],
) -> tuple[str, ...]:
    return tuple(
        dataset_id
        for dataset_id in plan.selected_dataset_ids
        if dataset_id in remaining
        and all(
            dependency in outcomes
            and outcomes[dependency].status is DatasetStatus.SUCCEEDED
            for dependency in plan.effective_for(dataset_id).config.orchestration.dependencies
        )
    )


def aggregate_pipeline_status(
    plan: DispatchPlan,
    outcomes: Mapping[str, DatasetDispatchOutcome],
    *,
    failure_policy: PipelineFailurePolicy = PipelineFailurePolicy.FAIL_AT_END,
    required_criticalities: frozenset[Criticality] = _DEFAULT_REQUIRED_CRITICALITIES,
) -> PipelineStatus:
    if not plan.selected_dataset_ids:
        return PipelineStatus.SUCCESS
    if all(outcome.status is DatasetStatus.SUCCEEDED for outcome in outcomes.values()):
        return PipelineStatus.SUCCESS

    if failure_policy is PipelineFailurePolicy.FAIL_AT_END:
        return PipelineStatus.FAILED

    for dataset_id, outcome in outcomes.items():
        if (
            outcome.status is not DatasetStatus.SUCCEEDED
            and plan.effective_for(dataset_id).config.orchestration.criticality
            in required_criticalities
        ):
            return PipelineStatus.FAILED
    return PipelineStatus.PARTIAL_SUCCESS


DEFAULT_REQUIRED_CRITICALITIES = _DEFAULT_REQUIRED_CRITICALITIES

__all__ = [
    "DEFAULT_REQUIRED_CRITICALITIES",
    "DispatchPlan",
    "OrchestrationIntegrityError",
    "PipelineFailurePolicy",
    "aggregate_pipeline_status",
    "blocking_dependencies",
    "build_dispatch_plan",
    "ready_dataset_ids",
]
