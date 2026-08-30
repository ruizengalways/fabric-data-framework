"""Exact-release approved Microsoft Fabric Data Pipeline evidence execution.

The runner deliberately reuses :class:`FabricPipelineBackend` rather than treating a
remote Fabric ``Completed`` state as framework semantic success. A PASS result is built
only after the backend has read the exact durable ``DatasetDispatchOutcome`` for the
same generated ``dataset_run_id`` from the relational control plane.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Engine, create_engine

from ..adapters.fabric.pipeline import (
    FabricPipelineBinding,
    FabricPipelineInvocation,
    FabricPipelineTransport,
    FabricRestPipelineTransport,
)
from ..adapters.fabric.rest import FabricJobInstance, FabricRestClient
from ..config import (
    DatasetConfig,
    DatasetStatus,
    PipelineStatus,
    RunMode,
    resolve_effective_config,
)
from ..control_plane.certification import get_control_plane_backend_profile
from ..delivery import config_bundle_hash
from ..deployment import ReleaseManifest
from ..fabric_auth import EnvironmentAccessTokenProvider
from ..execution.backends.fabric_pipeline import FabricPipelineBackend
from .integration_checks import build_fabric_pipeline_check_result
from .integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
    run_integration_evidence,
    validate_integration_evidence_manifest,
)
from .integration_runner import (
    ApprovedIntegrationRunPlan,
    ApprovedIntegrationRunnerConfig,
    IntegrationCheckPhysicalBinding,
    build_approved_integration_run_plan,
)
from ..operations import PipelineRunAudit
from ..control_plane.sqlalchemy_repository import SqlAlchemyControlPlaneRepository
from .safety import assert_safe_retained_text


EngineFactory = Callable[[str], Engine]
PipelineTransportFactory = Callable[[FabricRestClient], FabricPipelineTransport]


@dataclass(frozen=True)
class ApprovedPipelineExecution:
    """Credential-free result wrapper for one approved Pipeline stage."""

    plan: ApprovedIntegrationRunPlan
    manifest: IntegrationEvidenceManifest


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_pipeline_prerequisites(
    spec: IntegrationEvidenceSpec,
    prerequisite_manifest: IntegrationEvidenceManifest,
    *,
    selected_check_id: str,
) -> None:
    validate_integration_evidence_manifest(spec, prerequisite_manifest)
    results_by_id = {item.check_id: item for item in prerequisite_manifest.results}
    selected = results_by_id[selected_check_id]
    if selected.status is not IntegrationEvidenceStatus.NOT_RUN:
        raise ValueError(
            "approved Pipeline execution requires the selected check to remain NOT_RUN in the "
            "prerequisite manifest; explicitly choose rerun evidence instead of auto-rerunning"
        )

    for required_kind, label in (
        (IntegrationEvidenceCheckKind.FABRIC_ITEM_READ, "read-only Fabric item"),
        (
            IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            "control-plane certification",
        ),
    ):
        candidates = [
            item
            for item in prerequisite_manifest.results
            if item.kind is required_kind
            and item.status is IntegrationEvidenceStatus.PASS
        ]
        if not candidates:
            raise ValueError(
                f"approved Pipeline execution requires a retained PASS {label} prerequisite"
            )


def _require_exact_release_artifacts(
    *,
    config: ApprovedIntegrationRunnerConfig,
    release_manifest: ReleaseManifest,
    configs: tuple[DatasetConfig, ...],
    dataset_id: str,
) -> DatasetConfig:
    if release_manifest.domain != config.domain:
        raise ValueError("release manifest and approved runner config domain differ")
    if release_manifest.bundle.framework_version != config.framework_version:
        raise ValueError("release manifest and approved runner framework version differ")
    if release_manifest.bundle.release_hash != config.release_hash:
        raise ValueError("release manifest and approved runner release hash differ")
    observed_bundle_hash = config_bundle_hash(configs)
    if observed_bundle_hash != release_manifest.bundle.config_bundle_hash:
        raise ValueError("dataset config bundle hash does not match exact release manifest")
    by_id = {item.dataset_id: item for item in configs}
    if len(by_id) != len(configs):
        raise ValueError("approved Pipeline config bundle contains duplicate dataset_id values")
    selected = by_id.get(dataset_id)
    if selected is None:
        raise ValueError(f"approved Pipeline dataset {dataset_id!r} is absent from release bundle")
    return selected


def _pipeline_binding(plan: ApprovedIntegrationRunPlan) -> IntegrationCheckPhysicalBinding:
    if len(plan.bindings) != 1:
        raise ValueError("approved Pipeline execution requires exactly one physical binding")
    binding = plan.bindings[0]
    if binding.workspace_id is None or binding.item_id is None:
        raise ValueError("approved Pipeline physical binding is incomplete")
    return binding


def _record_parent(
    repository: SqlAlchemyControlPlaneRepository,
    *,
    pipeline_run_id: UUID,
    config: ApprovedIntegrationRunnerConfig,
    release_manifest: ReleaseManifest,
    status: PipelineStatus,
    started_at: datetime,
    completed_at: datetime | None,
) -> None:
    repository.record_pipeline_run(
        PipelineRunAudit(
            pipeline_run_id=pipeline_run_id,
            environment=config.environment.value,
            domain=config.domain,
            status=status,
            run_mode=RunMode.NORMAL,
            started_at=started_at,
            completed_at=completed_at,
            domain_git_sha=release_manifest.bundle.domain_git_sha,
            framework_version=config.framework_version,
            config_bundle_hash=release_manifest.bundle.config_bundle_hash,
        )
    )


class _RecordingPipelineTransport:
    """Capture exact invocation/native job while delegating execution once."""

    def __init__(self, inner: FabricPipelineTransport) -> None:
        self._inner = inner
        self.invocation: FabricPipelineInvocation | None = None
        self.job: FabricJobInstance | None = None

    def invoke(self, invocation: FabricPipelineInvocation) -> FabricJobInstance:
        if self.invocation is not None:
            raise RuntimeError("approved Pipeline transport may be invoked only once")
        self.invocation = invocation
        job = self._inner.invoke(invocation)
        self.job = job
        return job


def _safe_failure_result(
    *,
    check_id: str,
    invocation: FabricPipelineInvocation | None,
    job: FabricJobInstance | None,
    outcome_status: DatasetStatus,
    error_code: str | None,
    evidence_references: tuple[str, ...],
) -> IntegrationEvidenceCheckResult:
    safe_code = error_code or "UNSPECIFIED"
    try:
        assert_safe_retained_text(safe_code, "Pipeline outcome error_code")
    except ValueError:
        safe_code = "UNSAFE_PROVIDER_ERROR_CODE_REDACTED"
    now = _utcnow()
    started_at = job.start_time_utc if job and job.start_time_utc else now
    completed_at = job.end_time_utc if job and job.end_time_utc else now
    return IntegrationEvidenceCheckResult(
        check_id=check_id,
        kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
        status=IntegrationEvidenceStatus.FAIL,
        started_at=started_at,
        completed_at=max(started_at, completed_at),
        framework_pipeline_run_id=invocation.pipeline_run_id if invocation else None,
        dataset_run_id=invocation.dataset_run_id if invocation else None,
        workspace_id=invocation.binding.workspace_id if invocation else None,
        item_id=invocation.binding.pipeline_item_id if invocation else None,
        native_job_instance_id=job.job_instance_id if job else None,
        root_activity_id=job.root_activity_id if job else None,
        evidence_references=evidence_references,
        detail=(
            "approved Pipeline execution did not produce framework semantic success; "
            f"dataset_status={outcome_status.value}; error_code={safe_code}"
        ),
    )


def execute_approved_pipeline(
    *,
    config: ApprovedIntegrationRunnerConfig,
    spec: IntegrationEvidenceSpec,
    prerequisite_manifest: IntegrationEvidenceManifest,
    release_manifest: ReleaseManifest,
    configs: Iterable[DatasetConfig],
    check_id: str,
    dataset_id: str,
    environ: Mapping[str, str],
    evidence_references: Iterable[str],
    allow_pipeline_execution: bool,
    engine_factory: EngineFactory = create_engine,
    transport_factory: PipelineTransportFactory | None = None,
) -> ApprovedPipelineExecution:
    """Execute one exact-release Pipeline check after prerequisite evidence passes."""

    config_tuple = tuple(configs)
    plan = build_approved_integration_run_plan(
        config,
        spec,
        environ=environ,
        selected_check_ids=(check_id,),
        allow_mutating_checks=allow_pipeline_execution,
    )
    if not plan.ready:
        reasons: list[str] = []
        if plan.missing_runtime_env_vars:
            reasons.append(
                "missing runtime env vars=" + ",".join(plan.missing_runtime_env_vars)
            )
        if plan.mutating_check_ids and not plan.mutating_checks_authorized:
            reasons.append("Pipeline execution not explicitly authorized")
        raise ValueError("approved Pipeline preflight is not ready: " + "; ".join(reasons))

    check_by_id = {item.check_id: item for item in spec.checks}
    selected_check = check_by_id[check_id]
    if selected_check.kind is not IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN:
        raise ValueError("approved Pipeline runner requires FABRIC_PIPELINE_RUN check kind")
    _require_pipeline_prerequisites(
        spec,
        prerequisite_manifest,
        selected_check_id=check_id,
    )
    selected_config = _require_exact_release_artifacts(
        config=config,
        release_manifest=release_manifest,
        configs=config_tuple,
        dataset_id=dataset_id,
    )
    binding = _pipeline_binding(plan)

    if config.control_plane_profile is None or config.control_plane_database_url_env_var is None:
        raise ValueError("approved Pipeline runner requires control-plane runtime configuration")
    profile = get_control_plane_backend_profile(config.control_plane_profile)
    if not profile.production_eligible:
        raise ValueError("approved Pipeline runner requires a production-eligible control-plane profile")

    references = tuple(evidence_references)
    if not references:
        raise ValueError("approved Pipeline execution requires retained evidence references")
    for index, reference in enumerate(references):
        assert_safe_retained_text(reference, f"evidence_references[{index}]")

    # Actual secret-bearing values are retrieved only after exact-release artifacts,
    # prerequisite evidence, physical binding and mutation authorization have passed.
    database_url = environ[config.control_plane_database_url_env_var]

    def runner() -> IntegrationEvidenceCheckResult:
        engine = engine_factory(database_url)
        repository: SqlAlchemyControlPlaneRepository | None = None
        pipeline_run_id = uuid4()
        pipeline_started = _utcnow()
        parent_recorded = False
        try:
            repository = SqlAlchemyControlPlaneRepository(
                engine,
                domain=config.domain,
                domain_git_sha=release_manifest.bundle.domain_git_sha,
                framework_version=config.framework_version,
                configs=config_tuple,
            )
            deployed = repository.get_dataset(dataset_id)
            if deployed.config_hash != selected_config.config_hash:
                raise RuntimeError("approved Pipeline deployed/release config identity mismatch")
            effective = resolve_effective_config(deployed)
            _record_parent(
                repository,
                pipeline_run_id=pipeline_run_id,
                config=config,
                release_manifest=release_manifest,
                status=PipelineStatus.RUNNING,
                started_at=pipeline_started,
                completed_at=None,
            )
            parent_recorded = True

            client = FabricRestClient(
                token_provider=EnvironmentAccessTokenProvider(
                    env_var=config.fabric_access_token_env_var
                )
            )
            inner_transport = (
                transport_factory(client)
                if transport_factory is not None
                else FabricRestPipelineTransport(client)
            )
            recording = _RecordingPipelineTransport(inner_transport)
            backend = FabricPipelineBackend(
                transport=recording,
                binding_resolver=lambda _: FabricPipelineBinding(
                    workspace_id=binding.workspace_id,
                    pipeline_item_id=binding.item_id,
                ),
                outcome_reader=repository.get_dataset_outcome,
            )
            outcome = backend.execute_one(
                repository=repository,
                pipeline_run_id=pipeline_run_id,
                effective=effective,
                run_mode=RunMode.NORMAL,
            )
            final_status = (
                PipelineStatus.SUCCESS
                if outcome.status is DatasetStatus.SUCCEEDED
                else PipelineStatus.FAILED
            )
            _record_parent(
                repository,
                pipeline_run_id=pipeline_run_id,
                config=config,
                release_manifest=release_manifest,
                status=final_status,
                started_at=pipeline_started,
                completed_at=_utcnow(),
            )

            if outcome.status is not DatasetStatus.SUCCEEDED:
                return _safe_failure_result(
                    check_id=check_id,
                    invocation=recording.invocation,
                    job=recording.job,
                    outcome_status=outcome.status,
                    error_code=outcome.error_code,
                    evidence_references=references,
                )
            if recording.invocation is None or recording.job is None:
                raise RuntimeError("successful Pipeline backend did not retain invocation/native job")
            if outcome.dataset_run_id != recording.invocation.dataset_run_id:
                raise RuntimeError("Pipeline backend outcome does not match invocation dataset_run_id")
            return build_fabric_pipeline_check_result(
                check_id=check_id,
                invocation=recording.invocation,
                job=recording.job,
                evidence_references=references,
            )
        except Exception:
            if repository is not None and parent_recorded:
                try:
                    _record_parent(
                        repository,
                        pipeline_run_id=pipeline_run_id,
                        config=config,
                        release_manifest=release_manifest,
                        status=PipelineStatus.FAILED,
                        started_at=pipeline_started,
                        completed_at=_utcnow(),
                    )
                except Exception:
                    pass
            raise
        finally:
            engine.dispose()

    manifest = run_integration_evidence(spec, runners={check_id: runner})
    return ApprovedPipelineExecution(plan=plan, manifest=manifest)


__all__ = ["ApprovedPipelineExecution", "execute_approved_pipeline"]
