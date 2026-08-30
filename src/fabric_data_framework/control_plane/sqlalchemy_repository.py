"""SQLAlchemy-backed production runtime repository over the certified control plane.

Semantic DatasetConfig values still originate from the released/source-controlled
config bundle. The relational store materializes and fingerprints that bundle, while
this adapter validates the in-process released catalog against the deployed hash before
returning a dataset. This avoids inventing a second configuration source and also
avoids reconstructing fields that older normalized schema versions did not persist.

Runtime construction never migrates the database. Schema migration remains an explicit
deployment operation (`control-plane-migrate`) as required by the certification model.
"""

from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Iterable
from uuid import UUID

from sqlalchemy import Engine, select

from ..config import DatasetConfig, DatasetStatus
from ..contracts.capture_receipt import CaptureReceipt
from ..contracts.dispatch import DatasetDispatchOutcome
from ..contracts.recovery import DatasetAttemptLineage, ReprocessRequest
from .schema import (
    CONTROL_PLANE_SCHEMA_VERSION,
    capture_receipt,
    current_schema_version,
    dataset,
    dataset_attempt_lineage,
    dataset_run,
    pipeline_run,
    quarantine_batch,
    reconciliation_result,
    reprocess_request,
    step_run,
    watermark,
)
from ..deployment.delivery import materialize_semantic_metadata
from ..operations import (
    DatasetRunAudit,
    PipelineRunAudit,
    QuarantineBatch,
    ReconciliationResult,
    StepRunAudit,
)
from ..runtime import WatermarkPosition


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_current_schema(engine: Engine) -> None:
    observed = current_schema_version(engine)
    if observed != CONTROL_PLANE_SCHEMA_VERSION:
        raise RuntimeError(
            "control-plane runtime requires an explicitly migrated schema: "
            f"observed={observed}, required={CONTROL_PLANE_SCHEMA_VERSION}"
        )


def _assert_semantic_identity(
    existing: dict[str, object],
    expected: dict[str, object],
    *,
    label: str,
) -> None:
    changed = [key for key, value in expected.items() if existing[key] != value]
    if changed:
        raise ValueError(
            f"{label} semantic identity cannot change: {', '.join(sorted(changed))}"
        )


class SqlAlchemyControlPlaneRepository:
    """Durable runtime repository for one environment/domain.

    ``configs`` must come from the immutable domain artifact/config bundle used for the
    deployment. SQL materialization is checked by config hash on every dataset read.
    """

    def __init__(
        self,
        engine: Engine,
        *,
        domain: str,
        domain_git_sha: str,
        framework_version: str,
        configs: Iterable[DatasetConfig] = (),
    ) -> None:
        if not domain.strip():
            raise ValueError("domain cannot be empty")
        if not domain_git_sha.strip():
            raise ValueError("domain_git_sha cannot be empty")
        if not framework_version.strip():
            raise ValueError("framework_version cannot be empty")
        _require_current_schema(engine)
        config_tuple = tuple(configs)
        by_id = {item.dataset_id: item for item in config_tuple}
        if len(by_id) != len(config_tuple):
            raise ValueError("runtime config catalog contains duplicate dataset_id values")
        self.engine = engine
        self.domain = domain
        self.domain_git_sha = domain_git_sha
        self.framework_version = framework_version
        self._configs = by_id
        self._catalog_lock = RLock()

    def deploy_dataset(self, config: DatasetConfig) -> None:
        """Explicit deployment/materialization operation, not a runtime read side effect."""

        materialize_semantic_metadata(
            self.engine,
            configs=(config,),
            domain=self.domain,
            domain_git_sha=self.domain_git_sha,
            framework_version=self.framework_version,
        )
        with self._catalog_lock:
            self._configs[config.dataset_id] = config

    def _deployed_dataset_row(self, dataset_id: str) -> dict[str, object]:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(dataset).where(dataset.c.dataset_id == dataset_id)
            ).mappings().first()
        if row is None:
            raise KeyError(f"dataset not deployed: {dataset_id}")
        return dict(row)

    def get_dataset(self, dataset_id: str) -> DatasetConfig:
        row = self._deployed_dataset_row(dataset_id)
        with self._catalog_lock:
            config = self._configs.get(dataset_id)
        if config is None:
            raise KeyError(
                f"dataset {dataset_id!r} is deployed but absent from the released runtime config catalog"
            )
        if row["config_hash"] != config.config_hash:
            raise RuntimeError(
                f"deployed config hash mismatch for {dataset_id}: "
                f"control-plane={row['config_hash']}, artifact={config.config_hash}"
            )
        if row["domain"] != self.domain:
            raise RuntimeError(
                f"dataset {dataset_id} belongs to deployed domain {row['domain']!r}, "
                f"runtime expected {self.domain!r}"
            )
        return config

    def list_datasets(self) -> tuple[DatasetConfig, ...]:
        with self.engine.connect() as connection:
            ids = connection.execute(
                select(dataset.c.dataset_id)
                .where(dataset.c.domain == self.domain)
                .order_by(dataset.c.dataset_id)
            ).scalars().all()
        return tuple(self.get_dataset(str(dataset_id)) for dataset_id in ids)

    def get_watermark(self, dataset_id: str) -> WatermarkPosition | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(watermark).where(watermark.c.dataset_id == dataset_id)
            ).mappings().first()
        if row is None:
            return None
        return WatermarkPosition(
            value=row["committed_value"],
            tie_breaker=tuple(row["committed_tie_breaker"] or ()),
        )

    def commit_watermark(self, dataset_id: str, position: WatermarkPosition) -> None:
        # Compatibility method for the older repository Protocol. Stateful execution
        # should use the dedicated gated/CAS state primitives for commit decisions.
        self._deployed_dataset_row(dataset_id)
        now = _utcnow()
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(watermark).where(watermark.c.dataset_id == dataset_id)
            ).mappings().first()
            if existing is None:
                connection.execute(
                    watermark.insert().values(
                        dataset_id=dataset_id,
                        committed_value=position.value,
                        committed_tie_breaker=list(position.tie_breaker),
                        committed_dataset_run_id=None,
                        version=1,
                        created_at=now,
                        updated_at=None,
                    )
                )
                return
            connection.execute(
                watermark.update()
                .where(watermark.c.dataset_id == dataset_id)
                .values(
                    committed_value=position.value,
                    committed_tie_breaker=list(position.tie_breaker),
                    version=int(existing["version"]) + 1,
                    updated_at=now,
                )
            )

    def record_pipeline_run(self, audit: PipelineRunAudit) -> None:
        key = str(audit.pipeline_run_id)
        semantic = {
            "environment": audit.environment,
            "domain": audit.domain,
            "run_mode": audit.run_mode.value,
            "domain_git_sha": audit.domain_git_sha,
            "framework_version": audit.framework_version,
            "config_bundle_hash": audit.config_bundle_hash,
        }
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(pipeline_run).where(pipeline_run.c.pipeline_run_id == key)
            ).mappings().first()
            if existing is None:
                connection.execute(
                    pipeline_run.insert().values(
                        pipeline_run_id=key,
                        **semantic,
                        status=audit.status.value,
                        deployment_id=None,
                        started_at=audit.started_at,
                        completed_at=audit.completed_at,
                    )
                )
                return
            _assert_semantic_identity(dict(existing), semantic, label="pipeline run")
            connection.execute(
                pipeline_run.update()
                .where(pipeline_run.c.pipeline_run_id == key)
                .values(status=audit.status.value, completed_at=audit.completed_at)
            )

    def record_dataset_run(self, audit: DatasetRunAudit) -> None:
        key = str(audit.dataset_run_id)
        semantic = {
            "pipeline_run_id": str(audit.pipeline_run_id),
            "dataset_id": audit.dataset_id,
            "attempt": audit.attempt,
            "effective_config_hash": audit.effective_config_hash,
        }
        accounting = audit.row_accounting
        mutations = audit.mutations
        mutable = {
            "status": audit.status.value,
            "rows_read": accounting.rows_read if accounting is not None else None,
            "rows_accepted": accounting.rows_accepted if accounting is not None else None,
            "rows_quarantined": accounting.rows_quarantined if accounting is not None else None,
            "rows_filtered": accounting.rows_filtered if accounting is not None else None,
            "rows_inserted": mutations.inserted,
            "rows_updated": mutations.updated,
            "rows_deleted": mutations.deleted,
            "error_code": audit.error_code,
            "error_message": audit.error_message,
            "retryable": audit.retryable,
            "completed_at": audit.completed_at,
        }
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(dataset_run).where(dataset_run.c.dataset_run_id == key)
            ).mappings().first()
            if existing is None:
                connection.execute(
                    dataset_run.insert().values(
                        dataset_run_id=key,
                        **semantic,
                        **mutable,
                        started_at=audit.started_at,
                    )
                )
                return
            _assert_semantic_identity(dict(existing), semantic, label="dataset run")
            connection.execute(
                dataset_run.update()
                .where(dataset_run.c.dataset_run_id == key)
                .values(**mutable)
            )

    def get_dataset_outcome(self, dataset_run_id: UUID) -> DatasetDispatchOutcome | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(dataset_run).where(
                    dataset_run.c.dataset_run_id == str(dataset_run_id)
                )
            ).mappings().first()
        if row is None:
            return None
        return DatasetDispatchOutcome(
            dataset_run_id=dataset_run_id,
            status=DatasetStatus(str(row["status"])),
            retryable=row["retryable"],
            error_code=str(row["error_code"]) if row["error_code"] is not None else None,
            error_message=(
                str(row["error_message"]) if row["error_message"] is not None else None
            ),
        )

    def record_capture_receipt(self, receipt: CaptureReceipt) -> None:
        key = str(receipt.capture_receipt_id)
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(capture_receipt.c.capture_receipt_id).where(
                    capture_receipt.c.capture_receipt_id == key
                )
            ).first()
            if existing is not None:
                raise ValueError(f"capture receipt {receipt.capture_receipt_id} is already recorded")
            connection.execute(
                capture_receipt.insert().values(
                    capture_receipt_id=key,
                    dataset_run_id=str(receipt.dataset_run_id),
                    dataset_id=receipt.dataset_id,
                    capture_strategy=receipt.capture_strategy.value,
                    execution_engine=receipt.execution_engine.value,
                    progress_owner=receipt.progress_owner.value,
                    native_run_id=receipt.native_run_id,
                    source_reference=receipt.source_reference,
                    landing_reference=receipt.landing_reference,
                    rows_read=receipt.rows_read,
                    rows_written=receipt.rows_written,
                    source_lower_bound=receipt.source_lower_bound,
                    source_upper_bound=receipt.source_upper_bound,
                    snapshot_id=receipt.snapshot_id,
                    complete_snapshot=receipt.complete_snapshot,
                    external_checkpoint_reference=receipt.external_checkpoint_reference,
                    schema_version=receipt.schema_version,
                    started_at=receipt.started_at,
                    completed_at=receipt.completed_at,
                    created_at=_utcnow(),
                )
            )

    def record_step_run(self, audit: StepRunAudit) -> None:
        key = str(audit.step_run_id)
        semantic = {
            "dataset_run_id": str(audit.dataset_run_id),
            "step_name": audit.step_name,
        }
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(step_run).where(step_run.c.step_run_id == key)
            ).mappings().first()
            if existing is None:
                connection.execute(
                    step_run.insert().values(
                        step_run_id=key,
                        **semantic,
                        status=audit.status.value,
                        started_at=audit.started_at,
                        completed_at=audit.completed_at,
                        details=audit.details,
                    )
                )
                return
            _assert_semantic_identity(dict(existing), semantic, label="step run")
            connection.execute(
                step_run.update()
                .where(step_run.c.step_run_id == key)
                .values(
                    status=audit.status.value,
                    completed_at=audit.completed_at,
                    details=audit.details,
                )
            )

    def record_reconciliation(self, result: ReconciliationResult) -> None:
        key = str(result.reconciliation_id)
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(reconciliation_result.c.reconciliation_id).where(
                    reconciliation_result.c.reconciliation_id == key
                )
            ).first()
            if existing is not None:
                raise ValueError(
                    f"reconciliation {result.reconciliation_id} is already recorded"
                )
            connection.execute(
                reconciliation_result.insert().values(
                    reconciliation_id=key,
                    dataset_run_id=str(result.dataset_run_id),
                    dataset_id=result.dataset_id,
                    policy_name=result.policy_name,
                    status=result.status.value,
                    metrics=[item.model_dump(mode="json") for item in result.metrics],
                    blocks_state_advance=result.blocks_state_advance,
                    created_at=result.created_at,
                )
            )

    def record_quarantine(self, batch: QuarantineBatch) -> None:
        if batch.replayed_by_dataset_run_id is not None:
            raise ValueError("new quarantine evidence cannot start as already replayed")
        key = str(batch.quarantine_id)
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(quarantine_batch.c.quarantine_id).where(
                    quarantine_batch.c.quarantine_id == key
                )
            ).first()
            if existing is not None:
                raise ValueError(f"quarantine batch {batch.quarantine_id} is already recorded")
            connection.execute(
                quarantine_batch.insert().values(
                    quarantine_id=key,
                    dataset_run_id=str(batch.dataset_run_id),
                    dataset_id=batch.dataset_id,
                    scope=batch.scope.value,
                    row_count=batch.row_count,
                    reason_code=batch.reason_code,
                    reason_detail=batch.reason_detail,
                    source_reference=batch.source_reference,
                    replayed_by_dataset_run_id=None,
                    created_at=batch.created_at,
                )
            )

    def record_attempt_lineage(self, lineage: DatasetAttemptLineage) -> None:
        key = str(lineage.dataset_run_id)
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(dataset_attempt_lineage.c.dataset_run_id).where(
                    dataset_attempt_lineage.c.dataset_run_id == key
                )
            ).first()
            if existing is not None:
                raise ValueError(f"attempt lineage already recorded for {lineage.dataset_run_id}")
            connection.execute(
                dataset_attempt_lineage.insert().values(
                    dataset_run_id=key,
                    dataset_id=lineage.dataset_id,
                    root_dataset_run_id=str(lineage.root_dataset_run_id),
                    previous_dataset_run_id=(
                        str(lineage.previous_dataset_run_id)
                        if lineage.previous_dataset_run_id is not None
                        else None
                    ),
                    attempt=lineage.attempt,
                    run_mode=lineage.run_mode.value,
                    reprocess_request_id=(
                        str(lineage.reprocess_request_id)
                        if lineage.reprocess_request_id is not None
                        else None
                    ),
                    created_at=lineage.created_at,
                )
            )

    def record_reprocess_request(self, request: ReprocessRequest) -> None:
        key = str(request.reprocess_request_id)
        semantic = {
            "dataset_id": request.dataset_id,
            "run_mode": request.run_mode.value,
            "reason": request.reason,
            "requested_by": request.requested_by,
            "original_pipeline_run_id": (
                str(request.original_pipeline_run_id)
                if request.original_pipeline_run_id is not None
                else None
            ),
            "original_dataset_run_id": (
                str(request.original_dataset_run_id)
                if request.original_dataset_run_id is not None
                else None
            ),
            "range_json": request.range_json,
        }
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(reprocess_request).where(
                    reprocess_request.c.reprocess_request_id == key
                )
            ).mappings().first()
            if existing is None:
                connection.execute(
                    reprocess_request.insert().values(
                        reprocess_request_id=key,
                        **semantic,
                        status=request.status.value,
                        created_at=request.created_at,
                        updated_at=request.updated_at,
                    )
                )
                return
            _assert_semantic_identity(dict(existing), semantic, label="reprocess request")
            connection.execute(
                reprocess_request.update()
                .where(reprocess_request.c.reprocess_request_id == key)
                .values(
                    status=request.status.value,
                    updated_at=request.updated_at or _utcnow(),
                )
            )


__all__ = ["SqlAlchemyControlPlaneRepository"]
