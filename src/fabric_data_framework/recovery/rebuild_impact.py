"""Dependency-aware rebuild impact planning over deployed DatasetConfig metadata."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterable, Mapping

from fabric_data_framework.contracts.rebuild import RebuildScope
from fabric_data_framework.contracts.rebuild_impact import (
    RebuildImpactDataset,
    RebuildImpactPlan,
    RepairIssueOrigin,
)
from fabric_data_framework.metadata.config import DatasetConfig


class RebuildImpactError(RuntimeError):
    """Deployed metadata cannot produce a safe rebuild impact plan."""


_SCOPE_RANK = {
    RebuildScope.TARGET_ONLY: 1,
    RebuildScope.CAPTURE_AND_TARGET: 2,
    RebuildScope.AUTHORITATIVE_RESET: 3,
}


def _validate_graph(configs: Mapping[str, DatasetConfig]) -> None:
    for dataset_id, config in configs.items():
        for dependency in config.orchestration.dependencies:
            if dependency not in configs:
                raise RebuildImpactError(
                    f"dataset {dataset_id} depends on undeployed dataset {dependency}"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(dataset_id: str) -> None:
        if dataset_id in visited:
            return
        if dataset_id in visiting:
            raise RebuildImpactError(f"dependency cycle detected at dataset {dataset_id}")
        visiting.add(dataset_id)
        for dependency in configs[dataset_id].orchestration.dependencies:
            visit(dependency)
        visiting.remove(dataset_id)
        visited.add(dataset_id)

    for dataset_id in sorted(configs):
        visit(dataset_id)


def _downstream_descendants(
    configs: Mapping[str, DatasetConfig],
    roots: frozenset[str],
) -> frozenset[str]:
    reverse: dict[str, set[str]] = defaultdict(set)
    for dataset_id, config in configs.items():
        for dependency in config.orchestration.dependencies:
            reverse[dependency].add(dataset_id)

    affected = set(roots)
    queue = deque(sorted(roots))
    while queue:
        current = queue.popleft()
        for child in sorted(reverse.get(current, ())):
            if child in affected:
                continue
            affected.add(child)
            queue.append(child)
    return frozenset(affected)


def _build_waves(
    configs: Mapping[str, DatasetConfig],
    affected: frozenset[str],
) -> tuple[tuple[str, ...], ...]:
    remaining = set(affected)
    completed: set[str] = set()
    waves: list[tuple[str, ...]] = []

    while remaining:
        ready = tuple(
            sorted(
                dataset_id
                for dataset_id in remaining
                if all(
                    dependency not in affected or dependency in completed
                    for dependency in configs[dataset_id].orchestration.dependencies
                )
            )
        )
        if not ready:
            raise RebuildImpactError("affected rebuild subgraph cannot be topologically ordered")
        waves.append(ready)
        completed.update(ready)
        remaining.difference_update(ready)

    return tuple(waves)


def build_rebuild_impact_plan(
    configs: Iterable[DatasetConfig],
    *,
    root_dataset_ids: Iterable[str],
    issue_origin: RepairIssueOrigin,
    scope_overrides: Mapping[str, RebuildScope] | None = None,
) -> RebuildImpactPlan:
    """Compute the minimum downstream subgraph contaminated by one or more roots.

    The root scope is derived from where trust first failed:

    TARGET_LOGIC      -> TARGET_ONLY
    CAPTURE_DATA      -> CAPTURE_AND_TARGET
    CAPTURE_SEMANTICS -> AUTHORITATIVE_RESET

    Downstream descendants default to TARGET_ONLY because their own target must be
    reconstructed from corrected authoritative upstream facts. A domain implementation
    may explicitly widen a descendant scope when its own retained capture is not safe.
    Root scope can only be widened, never narrowed below the issue-origin requirement.
    """

    by_id: dict[str, DatasetConfig] = {}
    for config in configs:
        if config.dataset_id in by_id:
            raise RebuildImpactError(f"duplicate deployed dataset id: {config.dataset_id}")
        by_id[config.dataset_id] = config
    if not by_id:
        raise RebuildImpactError("rebuild impact planning requires deployed datasets")

    _validate_graph(by_id)

    roots = tuple(sorted(set(root_dataset_ids)))
    if not roots:
        raise RebuildImpactError("root_dataset_ids cannot be empty")
    missing = sorted(set(roots) - set(by_id))
    if missing:
        raise RebuildImpactError(
            "rebuild roots are not deployed: " + ",".join(missing)
        )

    affected = _downstream_descendants(by_id, frozenset(roots))
    overrides = dict(scope_overrides or {})
    unknown_overrides = sorted(set(overrides) - set(affected))
    if unknown_overrides:
        raise RebuildImpactError(
            "scope overrides target datasets outside the affected subgraph: "
            + ",".join(unknown_overrides)
        )

    root_scope = issue_origin.root_rebuild_scope
    for root in roots:
        override = overrides.get(root)
        if override is not None and _SCOPE_RANK[override] < _SCOPE_RANK[root_scope]:
            raise RebuildImpactError(
                f"root {root} scope {override.value} is narrower than required "
                f"{root_scope.value} for {issue_origin.value}"
            )

    waves = _build_waves(by_id, affected)
    ordered_ids = tuple(dataset_id for wave in waves for dataset_id in wave)
    root_set = set(roots)
    datasets = tuple(
        RebuildImpactDataset(
            dataset_id=dataset_id,
            target_layer=by_id[dataset_id].target.layer,
            enabled=by_id[dataset_id].enabled,
            is_root=dataset_id in root_set,
            rebuild_scope=overrides.get(
                dataset_id,
                root_scope if dataset_id in root_set else RebuildScope.TARGET_ONLY,
            ),
        )
        for dataset_id in ordered_ids
    )
    disabled = tuple(item.dataset_id for item in datasets if not item.enabled)

    return RebuildImpactPlan(
        issue_origin=issue_origin,
        root_dataset_ids=roots,
        datasets=datasets,
        waves=waves,
        disabled_affected_dataset_ids=disabled,
    )


__all__ = [
    "RebuildImpactError",
    "build_rebuild_impact_plan",
]
