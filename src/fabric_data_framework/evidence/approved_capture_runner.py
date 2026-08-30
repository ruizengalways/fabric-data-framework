"""Exact-release approved Copy Job and Spark capture evidence execution.

The runner never converts provider ``Completed`` into framework capture success by
itself. It reuses the concrete REST transports plus ``FabricCaptureAdapter`` and
requires a bounded customer/domain observation extension to produce the post-run facts
that Fabric's generic job APIs do not expose: row counts, landing identity, source
bounds/checkpoints and snapshot completeness.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
import json

from pydantic import Field, model_validator

from ..adapters.fabric.adapter import (
    CopyJobCaptureAdapter,
    FabricAdapterExecutionError,
    FabricCaptureExecutionResult,
    SparkJobCaptureAdapter,
)
from ..adapters.fabric.capture_transports import (
    FabricCaptureObservation,
    FabricCaptureObservationResolver,
    FabricCopyJobBinding,
    FabricCopyJobCaptureTransport,
    FabricSparkExecutionDataResolver,
    FabricSparkJobDefinitionBinding,
    FabricSparkJobDefinitionCaptureTransport,
)
from ..adapters.fabric.contracts import FabricCaptureRequest, FabricNativeRunEvidence
from ..adapters.fabric.rest import FabricJobInstance, FabricRestClient
from fabric_data_framework.metadata.config import (
    CaptureStrategy,
    DatasetConfig,
    ExecutionEngine,
    ProgressOwner,
    RunMode,
    canonical_hash,
    resolve_effective_config,
)
from fabric_data_framework.contracts.base import FrozenModel
from ..contracts.capture_receipt import CaptureReceipt
from ..contracts.execution_plan import (
    ExecutionKind,
    ExecutionRole,
    ExecutionUnit,
    compile_execution_plan,
)
from ..deployment.delivery import config_bundle_hash
from ..deployment.contracts import ReleaseManifest
from ..extensions import ExtensionKind, ExtensionRegistry
from fabric_data_framework.adapters.fabric.auth import EnvironmentAccessTokenProvider
from .integration_checks import build_fabric_capture_check_result
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
from .safety import assert_safe_retained_text


_EXTENSION_PATTERN = r"^[a-z][a-z0-9_.-]*$"
_FORBIDDEN_CAPTURE_ROLES = frozenset(
    {
        ExecutionRole.APPLY,
        ExecutionRole.PUBLISH,
        ExecutionRole.RECONCILE,
        ExecutionRole.COMMIT_STATE,
        ExecutionRole.FINALIZE,
    }
)


class ApprovedCaptureRunConfig(FrozenModel):
    """Credential-free recipe for one approved representative capture check."""

    check_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    dataset_id: str = Field(min_length=1, max_length=256)
    landing_reference: str = Field(min_length=1, max_length=2048)
    observation_extension: str = Field(pattern=_EXTENSION_PATTERN)
    extension_artifact_name: str = Field(min_length=1, max_length=512)
    spark_execution_data_extension: str | None = Field(
        default=None, pattern=_EXTENSION_PATTERN
    )
    source_lower_bound: Any | None = None
    source_upper_bound: Any | None = None
    snapshot_id: str | None = Field(default=None, max_length=1024)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_safe_recipe(self) -> "ApprovedCaptureRunConfig":
        rendered = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        )
        assert_safe_retained_text(rendered, "approved capture run config")
        return self

    @property
    def run_config_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class ApprovedCaptureEvidenceReport(FrozenModel):
    """Safe retained projection of one verified capture result.

    Arbitrary provider/observer diagnostics are intentionally excluded. Durable
    evidence references point to any richer approved provider/item-specific artifacts.
    """

    check_id: str
    kind: IntegrationEvidenceCheckKind
    run_config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt: CaptureReceipt
    workspace_id: UUID
    item_id: UUID
    native_job_instance_id: UUID
    root_activity_id: UUID
    evidence_references: tuple[str, ...]

    @model_validator(mode="after")
    def validate_safe_report(self) -> "ApprovedCaptureEvidenceReport":
        rendered = self.model_dump_json()
        assert_safe_retained_text(rendered, "approved capture evidence report")
        return self


@dataclass(frozen=True)
class ApprovedCaptureExecution:
    plan: ApprovedIntegrationRunPlan
    manifest: IntegrationEvidenceManifest
    report: ApprovedCaptureEvidenceReport | None


RestClientFactory = Callable[[EnvironmentAccessTokenProvider], FabricRestClient]


def _default_rest_client_factory(
    token_provider: EnvironmentAccessTokenProvider,
) -> FabricRestClient:
    return FabricRestClient(token_provider=token_provider)


def load_approved_capture_run_config(path: str | Path) -> ApprovedCaptureRunConfig:
    return ApprovedCaptureRunConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _require_capture_prerequisites(
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
            "approved capture execution requires the selected check to remain NOT_RUN in "
            "the prerequisite manifest; explicitly choose rerun evidence instead of "
            "auto-rerunning a mutating provider check"
        )
    for required_kind, label in (
        (IntegrationEvidenceCheckKind.FABRIC_ITEM_READ, "read-only Fabric item"),
        (
            IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            "control-plane certification",
        ),
    ):
        if not any(
            item.kind is required_kind and item.status is IntegrationEvidenceStatus.PASS
            for item in prerequisite_manifest.results
        ):
            raise ValueError(
                f"approved capture execution requires a retained PASS {label} prerequisite"
            )


def _require_exact_release_dataset(
    *,
    runner_config: ApprovedIntegrationRunnerConfig,
    capture_config: ApprovedCaptureRunConfig,
    release_manifest: ReleaseManifest,
    configs: tuple[DatasetConfig, ...],
) -> DatasetConfig:
    if release_manifest.domain != runner_config.domain:
        raise ValueError("release manifest and approved runner config domain differ")
    if release_manifest.bundle.framework_version != runner_config.framework_version:
        raise ValueError("release manifest and approved runner framework version differ")
    if release_manifest.bundle.release_hash != runner_config.release_hash:
        raise ValueError("release manifest and approved runner release hash differ")
    observed_bundle_hash = config_bundle_hash(configs)
    if observed_bundle_hash != release_manifest.bundle.config_bundle_hash:
        raise ValueError("dataset config bundle hash does not match exact release manifest")
    if capture_config.extension_artifact_name not in release_manifest.artifact_sha256:
        raise ValueError(
            "approved capture observer/execution-data extension artifact is not fingerprinted "
            "in the exact release manifest"
        )
    by_id = {item.dataset_id: item for item in configs}
    if len(by_id) != len(configs):
        raise ValueError("approved capture config bundle contains duplicate dataset_id values")
    selected = by_id.get(capture_config.dataset_id)
    if selected is None:
        raise ValueError(
            f"approved capture dataset {capture_config.dataset_id!r} is absent from release bundle"
        )
    return selected


def _physical_binding(plan: ApprovedIntegrationRunPlan) -> IntegrationCheckPhysicalBinding:
    if len(plan.bindings) != 1:
        raise ValueError("approved capture execution requires exactly one physical binding")
    binding = plan.bindings[0]
    if binding.workspace_id is None or binding.item_id is None:
        raise ValueError("approved capture physical binding is incomplete")
    return binding


def _capture_unit(
    config: DatasetConfig,
    *,
    expected_kind: ExecutionKind,
) -> tuple[ExecutionUnit, str]:
    effective = resolve_effective_config(config)
    plan = compile_execution_plan(effective, run_mode=RunMode.NORMAL)
    candidates = []
    for unit in plan.units:
        roles = frozenset(unit.roles)
        if unit.execution_kind is not expected_kind:
            continue
        if not {ExecutionRole.EXTRACT, ExecutionRole.STAGE}.issubset(roles):
            continue
        if roles.intersection(_FORBIDDEN_CAPTURE_ROLES):
            continue
        candidates.append(unit)
    if len(candidates) != 1:
        raise ValueError(
            "approved capture runner requires exactly one dedicated capture-only execution "
            f"unit of kind {expected_kind.value}; observed={len(candidates)}. A combined Spark "
            "dataset_execute unit cannot be reused as capture-only evidence because it also "
            "owns downstream lifecycle roles."
        )
    return candidates[0], plan.plan_hash


def _resolve_extensions(
    capture_config: ApprovedCaptureRunConfig,
    *,
    need_spark_execution_data: bool,
    extension_registry: ExtensionRegistry | None,
) -> tuple[FabricCaptureObservationResolver, FabricSparkExecutionDataResolver | None]:
    registry = extension_registry or ExtensionRegistry()
    if extension_registry is None:
        registry.discover(ExtensionKind.CAPTURE_OBSERVER)
        if need_spark_execution_data:
            registry.discover(ExtensionKind.SPARK_EXECUTION_DATA)
    observer = registry.factory(
        ExtensionKind.CAPTURE_OBSERVER,
        capture_config.observation_extension,
    )
    execution_data: FabricSparkExecutionDataResolver | None = None
    if need_spark_execution_data:
        if capture_config.spark_execution_data_extension is None:
            raise ValueError(
                "framework-bounded Spark capture requires spark_execution_data_extension"
            )
        execution_data = registry.factory(
            ExtensionKind.SPARK_EXECUTION_DATA,
            capture_config.spark_execution_data_extension,
        )
    elif capture_config.spark_execution_data_extension is not None:
        raise ValueError(
            "spark_execution_data_extension is only valid when the approved Spark request "
            "contains bounds or runtime parameters"
        )
    return observer, execution_data


class _RecordingObservationResolver:
    def __init__(self, inner: FabricCaptureObservationResolver) -> None:
        self._inner = inner
        self.job: FabricJobInstance | None = None

    def __call__(
        self,
        request: FabricCaptureRequest,
        job: FabricJobInstance,
    ) -> FabricCaptureObservation:
        if self.job is not None:
            raise RuntimeError("approved capture observer may be invoked only once")
        self.job = job
        return self._inner(request, job)


def _provider_uuid(evidence: FabricNativeRunEvidence | None, field_name: str) -> UUID | None:
    if evidence is None:
        return None
    provider = evidence.diagnostics.get("provider")
    if not isinstance(provider, dict):
        return None
    value = provider.get(field_name)
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _safe_failure_result(
    *,
    check_id: str,
    kind: IntegrationEvidenceCheckKind,
    dataset_run_id: UUID,
    binding: IntegrationCheckPhysicalBinding,
    evidence_references: tuple[str, ...],
    evidence: FabricNativeRunEvidence | None = None,
    job: FabricJobInstance | None = None,
    failure_type: str,
) -> IntegrationEvidenceCheckResult:
    now = job.end_time_utc if job and job.end_time_utc else None
    if evidence is not None:
        started_at = evidence.started_at
        completed_at = evidence.completed_at
    else:
        completed_at = now or __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        started_at = job.start_time_utc if job and job.start_time_utc else completed_at
    native_job_id = _provider_uuid(evidence, "job_instance_id")
    root_id = _provider_uuid(evidence, "root_activity_id")
    item_id = _provider_uuid(evidence, "item_id") or binding.item_id
    workspace_id = _provider_uuid(evidence, "workspace_id") or binding.workspace_id
    if job is not None:
        native_job_id = native_job_id or job.job_instance_id
        root_id = root_id or job.root_activity_id
    assert_safe_retained_text(failure_type, "capture failure type")
    return IntegrationEvidenceCheckResult(
        check_id=check_id,
        kind=kind,
        status=IntegrationEvidenceStatus.FAIL,
        started_at=started_at,
        completed_at=max(started_at, completed_at),
        dataset_run_id=dataset_run_id,
        workspace_id=workspace_id,
        item_id=item_id,
        native_job_instance_id=native_job_id,
        root_activity_id=root_id,
        evidence_references=evidence_references,
        detail=(
            "approved capture did not produce a verified CaptureReceipt/native evidence pair; "
            f"failure_type={failure_type}"
        ),
    )


def _report_from_result(
    *,
    check_id: str,
    kind: IntegrationEvidenceCheckKind,
    capture_config: ApprovedCaptureRunConfig,
    execution_plan_hash: str,
    result: FabricCaptureExecutionResult,
    evidence_references: tuple[str, ...],
) -> ApprovedCaptureEvidenceReport:
    provider = result.native_evidence.diagnostics.get("provider")
    if not isinstance(provider, dict):
        raise ValueError("verified capture evidence is missing provider correlation")
    try:
        workspace_id = UUID(str(provider["workspace_id"]))
        item_id = UUID(str(provider["item_id"]))
        native_job_instance_id = UUID(str(provider["job_instance_id"]))
        root_activity_id = UUID(str(provider["root_activity_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("verified capture evidence has invalid provider correlation") from exc
    return ApprovedCaptureEvidenceReport(
        check_id=check_id,
        kind=kind,
        run_config_hash=capture_config.run_config_hash,
        execution_plan_hash=execution_plan_hash,
        receipt=result.receipt,
        workspace_id=workspace_id,
        item_id=item_id,
        native_job_instance_id=native_job_instance_id,
        root_activity_id=root_activity_id,
        evidence_references=evidence_references,
    )


def execute_approved_capture(
    *,
    config: ApprovedIntegrationRunnerConfig,
    spec: IntegrationEvidenceSpec,
    prerequisite_manifest: IntegrationEvidenceManifest,
    release_manifest: ReleaseManifest,
    configs: Iterable[DatasetConfig],
    capture_config: ApprovedCaptureRunConfig,
    environ: Mapping[str, str],
    evidence_references: Iterable[str],
    allow_capture_execution: bool,
    extension_registry: ExtensionRegistry | None = None,
    rest_client_factory: RestClientFactory = _default_rest_client_factory,
) -> ApprovedCaptureExecution:
    """Execute one approved Copy Job or Spark capture check exactly once."""

    config_tuple = tuple(configs)
    check_id = capture_config.check_id
    plan = build_approved_integration_run_plan(
        config,
        spec,
        environ=environ,
        selected_check_ids=(check_id,),
        allow_mutating_checks=allow_capture_execution,
    )
    if not plan.ready:
        reasons: list[str] = []
        if plan.missing_runtime_env_vars:
            reasons.append(
                "missing runtime env vars=" + ",".join(plan.missing_runtime_env_vars)
            )
        if plan.mutating_check_ids and not plan.mutating_checks_authorized:
            reasons.append("capture execution not explicitly authorized")
        raise ValueError("approved capture preflight is not ready: " + "; ".join(reasons))

    checks = {item.check_id: item for item in spec.checks}
    selected_check = checks[check_id]
    if selected_check.kind not in {
        IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
        IntegrationEvidenceCheckKind.FABRIC_SPARK_CAPTURE,
    }:
        raise ValueError("approved capture runner supports Copy Job and Spark checks only")
    _require_capture_prerequisites(
        spec,
        prerequisite_manifest,
        selected_check_id=check_id,
    )
    dataset = _require_exact_release_dataset(
        runner_config=config,
        capture_config=capture_config,
        release_manifest=release_manifest,
        configs=config_tuple,
    )
    binding = _physical_binding(plan)

    if selected_check.kind is IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE:
        expected_engine = ExecutionEngine.FABRIC_COPY_JOB
        expected_kind = ExecutionKind.FABRIC_COPY_JOB
        if dataset.execution.progress_owner is not ProgressOwner.FABRIC_NATIVE:
            raise ValueError("approved Copy Job capture requires FABRIC_NATIVE progress ownership")
        if (
            capture_config.source_lower_bound is not None
            or capture_config.source_upper_bound is not None
            or capture_config.parameters
        ):
            raise ValueError(
                "approved Copy Job capture cannot supply framework bounds/runtime parameters; "
                "native Copy Job progress remains authoritative"
            )
    else:
        expected_engine = ExecutionEngine.SPARK
        expected_kind = ExecutionKind.SPARK_JOB_DEFINITION
        if dataset.execution.progress_owner is not ProgressOwner.FRAMEWORK:
            raise ValueError("approved Spark capture requires FRAMEWORK progress ownership")
        if dataset.load.capture_strategy in {CaptureStrategy.WATERMARK, CaptureStrategy.CDC}:
            if capture_config.source_upper_bound is None:
                raise ValueError(
                    "approved framework-bounded Spark WATERMARK/CDC capture requires a frozen "
                    "source_upper_bound"
                )

    if dataset.execution.engine is not expected_engine:
        raise ValueError(
            f"approved capture check kind requires dataset execution engine {expected_engine.value}"
        )
    capture_unit, execution_plan_hash = _capture_unit(
        dataset,
        expected_kind=expected_kind,
    )
    need_execution_data = selected_check.kind is IntegrationEvidenceCheckKind.FABRIC_SPARK_CAPTURE and (
        capture_config.source_lower_bound is not None
        or capture_config.source_upper_bound is not None
        or bool(capture_config.parameters)
    )
    observer, execution_data_resolver = _resolve_extensions(
        capture_config,
        need_spark_execution_data=need_execution_data,
        extension_registry=extension_registry,
    )

    references = tuple(evidence_references)
    if not references:
        raise ValueError("approved capture execution requires retained evidence references")
    for index, reference in enumerate(references):
        assert_safe_retained_text(reference, f"evidence_references[{index}]")

    source_reference = f"{dataset.source.system}.{dataset.source.object}"
    assert_safe_retained_text(source_reference, "source_reference")
    dataset_run_id = uuid4()
    request = FabricCaptureRequest(
        dataset_run_id=dataset_run_id,
        dataset_id=dataset.dataset_id,
        execution_unit=capture_unit,
        capture_strategy=dataset.load.capture_strategy,
        execution_engine=expected_engine,
        progress_owner=dataset.execution.progress_owner,
        source_reference=source_reference,
        landing_reference=capture_config.landing_reference,
        source_lower_bound=capture_config.source_lower_bound,
        source_upper_bound=capture_config.source_upper_bound,
        snapshot_id=capture_config.snapshot_id,
        parameters=capture_config.parameters,
    )

    report_holder: list[ApprovedCaptureEvidenceReport] = []

    def runner() -> IntegrationEvidenceCheckResult:
        token_provider = EnvironmentAccessTokenProvider(env_var=config.fabric_access_token_env_var)
        client = rest_client_factory(token_provider)
        recording_observer = _RecordingObservationResolver(observer)
        if selected_check.kind is IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE:
            transport = FabricCopyJobCaptureTransport(
                client=client,
                binding_resolver=lambda _: FabricCopyJobBinding(
                    workspace_id=binding.workspace_id,
                    copy_job_id=binding.item_id,
                    timeout_seconds=float(dataset.orchestration.timeout_seconds),
                ),
                observation_resolver=recording_observer,
            )
            adapter = CopyJobCaptureAdapter(transport)
        else:
            transport = FabricSparkJobDefinitionCaptureTransport(
                client=client,
                binding_resolver=lambda _: FabricSparkJobDefinitionBinding(
                    workspace_id=binding.workspace_id,
                    spark_job_definition_id=binding.item_id,
                    timeout_seconds=float(dataset.orchestration.timeout_seconds),
                ),
                observation_resolver=recording_observer,
                execution_data_resolver=execution_data_resolver,
            )
            adapter = SparkJobCaptureAdapter(transport)

        try:
            result = adapter.execute_with_evidence(request)
            check_result = build_fabric_capture_check_result(
                check_id=check_id,
                result=result,
                evidence_references=references,
            )
            report_holder.append(
                _report_from_result(
                    check_id=check_id,
                    kind=selected_check.kind,
                    capture_config=capture_config,
                    execution_plan_hash=execution_plan_hash,
                    result=result,
                    evidence_references=references,
                )
            )
            return check_result
        except FabricAdapterExecutionError as exc:
            return _safe_failure_result(
                check_id=check_id,
                kind=selected_check.kind,
                dataset_run_id=dataset_run_id,
                binding=binding,
                evidence_references=references,
                evidence=exc.evidence,
                job=recording_observer.job,
                failure_type=type(exc).__name__,
            )
        except Exception as exc:
            if recording_observer.job is not None:
                return _safe_failure_result(
                    check_id=check_id,
                    kind=selected_check.kind,
                    dataset_run_id=dataset_run_id,
                    binding=binding,
                    evidence_references=references,
                    job=recording_observer.job,
                    failure_type=type(exc).__name__,
                )
            raise

    manifest = run_integration_evidence(spec, runners={check_id: runner})
    report = report_holder[0] if report_holder else None
    return ApprovedCaptureExecution(plan=plan, manifest=manifest, report=report)


__all__ = [
    "ApprovedCaptureEvidenceReport",
    "ApprovedCaptureExecution",
    "ApprovedCaptureRunConfig",
    "execute_approved_capture",
    "load_approved_capture_run_config",
]
