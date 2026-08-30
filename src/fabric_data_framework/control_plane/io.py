"""Small relational control-plane persistence helpers pending the full repository adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import Field
from sqlalchemy import Engine, select

from ..capture.cdc import CDCCheckpoint, CDCCheckpointTransition
from fabric_data_framework.contracts.base import FrozenModel
from .schema import (
    apply_baseline_schema,
    capture_receipt,
    cdc_checkpoint,
    dataset_attempt_lineage,
    quarantine_batch,
    reprocess_request,
)
from ..contracts.capture_receipt import CaptureReceipt
from ..contracts.recovery import DatasetAttemptLineage, ReprocessRequest
from ..contracts.replay import QuarantineBatchEvidence
from ..runtime import StateCommitGate


class CDCCheckpointVersionConflict(RuntimeError):
    """Raised when a stale writer attempts to replace newer CDC state."""


class QuarantineReplayMarkerConflict(RuntimeError):
    """Raised when replay correlation is already owned by a different dataset run."""


class CDCCheckpointState(FrozenModel):
    dataset_id: str = Field(min_length=1)
    checkpoint: CDCCheckpoint
    committed_dataset_run_id: UUID
    version: int = Field(ge=1)


def record_capture_receipt(engine: Engine, receipt: CaptureReceipt) -> None:
    """Append one immutable native/custom capture handoff receipt."""

    apply_baseline_schema(engine)
    with engine.begin() as connection:
        existing = connection.execute(
            select(capture_receipt.c.capture_receipt_id).where(
                capture_receipt.c.capture_receipt_id == str(receipt.capture_receipt_id)
            )
        ).first()
        if existing is not None:
            raise ValueError(
                f"capture receipt {receipt.capture_receipt_id} is already recorded"
            )
        connection.execute(
            capture_receipt.insert().values(
                capture_receipt_id=str(receipt.capture_receipt_id),
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
                created_at=datetime.now(timezone.utc),
            )
        )


def record_attempt_lineage(engine: Engine, lineage: DatasetAttemptLineage) -> None:
    """Append immutable dataset-attempt linkage before/around execution."""

    apply_baseline_schema(engine)
    with engine.begin() as connection:
        existing = connection.execute(
            select(dataset_attempt_lineage.c.dataset_run_id).where(
                dataset_attempt_lineage.c.dataset_run_id == str(lineage.dataset_run_id)
            )
        ).first()
        if existing is not None:
            raise ValueError(
                f"attempt lineage already recorded for {lineage.dataset_run_id}"
            )
        connection.execute(
            dataset_attempt_lineage.insert().values(
                dataset_run_id=str(lineage.dataset_run_id),
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


def record_reprocess_request(engine: Engine, request: ReprocessRequest) -> None:
    """Insert a request or advance only its mutable lifecycle status."""

    apply_baseline_schema(engine)
    request_id = str(request.reprocess_request_id)
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
    with engine.begin() as connection:
        existing = connection.execute(
            select(reprocess_request).where(
                reprocess_request.c.reprocess_request_id == request_id
            )
        ).mappings().first()
        if existing is None:
            connection.execute(
                reprocess_request.insert().values(
                    reprocess_request_id=request_id,
                    **semantic,
                    status=request.status.value,
                    created_at=request.created_at,
                    updated_at=request.updated_at,
                )
            )
            return

        for key, expected in semantic.items():
            if existing[key] != expected:
                raise ValueError("reprocess request semantic identity cannot change")
        connection.execute(
            reprocess_request.update()
            .where(reprocess_request.c.reprocess_request_id == request_id)
            .values(
                status=request.status.value,
                updated_at=request.updated_at or datetime.now(timezone.utc),
            )
        )


def _quarantine_from_row(row: dict[str, object]) -> QuarantineBatchEvidence:
    replayed_by = row["replayed_by_dataset_run_id"]
    return QuarantineBatchEvidence(
        quarantine_id=UUID(str(row["quarantine_id"])),
        dataset_run_id=UUID(str(row["dataset_run_id"])),
        dataset_id=str(row["dataset_id"]),
        scope=str(row["scope"]),
        row_count=int(row["row_count"]),
        reason_code=str(row["reason_code"]),
        reason_detail=(
            str(row["reason_detail"]) if row["reason_detail"] is not None else None
        ),
        source_reference=(
            str(row["source_reference"]) if row["source_reference"] is not None else None
        ),
        replayed_by_dataset_run_id=(
            UUID(str(replayed_by)) if replayed_by is not None else None
        ),
        created_at=row["created_at"],
    )


def record_quarantine_batch(engine: Engine, batch: QuarantineBatchEvidence) -> None:
    """Append immutable quarantine lineage/reference evidence.

    Payload rows are deliberately not persisted here. ``source_reference`` points to
    the governed quarantine data store used by replay.
    """

    if batch.replayed_by_dataset_run_id is not None:
        raise ValueError("new quarantine evidence cannot start as already replayed")
    apply_baseline_schema(engine)
    with engine.begin() as connection:
        existing = connection.execute(
            select(quarantine_batch.c.quarantine_id).where(
                quarantine_batch.c.quarantine_id == str(batch.quarantine_id)
            )
        ).first()
        if existing is not None:
            raise ValueError(f"quarantine batch {batch.quarantine_id} is already recorded")
        connection.execute(
            quarantine_batch.insert().values(
                quarantine_id=str(batch.quarantine_id),
                dataset_run_id=str(batch.dataset_run_id),
                dataset_id=batch.dataset_id,
                scope=batch.scope,
                row_count=batch.row_count,
                reason_code=batch.reason_code,
                reason_detail=batch.reason_detail,
                source_reference=batch.source_reference,
                replayed_by_dataset_run_id=None,
                created_at=batch.created_at,
            )
        )


def read_quarantine_batches(
    engine: Engine,
    quarantine_ids: tuple[UUID, ...],
) -> tuple[QuarantineBatchEvidence, ...]:
    """Read an explicit replay scope preserving caller order."""

    if not quarantine_ids:
        raise ValueError("quarantine_ids cannot be empty")
    if len(set(quarantine_ids)) != len(quarantine_ids):
        raise ValueError("quarantine_ids cannot contain duplicates")

    apply_baseline_schema(engine)
    values = tuple(str(value) for value in quarantine_ids)
    with engine.connect() as connection:
        rows = connection.execute(
            select(quarantine_batch).where(quarantine_batch.c.quarantine_id.in_(values))
        ).mappings().all()
    by_id = {str(row["quarantine_id"]): _quarantine_from_row(dict(row)) for row in rows}
    missing = [value for value in values if value not in by_id]
    if missing:
        raise KeyError(f"quarantine batches not found: {', '.join(missing)}")
    return tuple(by_id[value] for value in values)


def read_quarantine_batches_for_run(
    engine: Engine,
    *,
    dataset_id: str,
    dataset_run_id: UUID,
) -> tuple[QuarantineBatchEvidence, ...]:
    """Read all quarantine evidence produced by one original dataset run."""

    apply_baseline_schema(engine)
    with engine.connect() as connection:
        rows = connection.execute(
            select(quarantine_batch)
            .where(
                quarantine_batch.c.dataset_id == dataset_id,
                quarantine_batch.c.dataset_run_id == str(dataset_run_id),
            )
            .order_by(quarantine_batch.c.created_at, quarantine_batch.c.quarantine_id)
        ).mappings().all()
    return tuple(_quarantine_from_row(dict(row)) for row in rows)


def mark_quarantine_replayed(
    engine: Engine,
    *,
    dataset_id: str,
    quarantine_ids: tuple[UUID, ...],
    replayed_by_dataset_run_id: UUID,
    gate: StateCommitGate,
) -> tuple[QuarantineBatchEvidence, ...]:
    """Correlate originals only after replay mutation/reconciliation is proven.

    Exact repeat with the same replay dataset-run ID is idempotent. Any different
    non-null marker is a conflict. The original quarantine row remains otherwise
    immutable and is never deleted by this operation.
    """

    if not gate.can_advance_state:
        raise ValueError(
            "quarantine replay marker cannot advance before target commit and required "
            "reconciliation"
        )
    if not quarantine_ids:
        raise ValueError("quarantine_ids cannot be empty")
    if len(set(quarantine_ids)) != len(quarantine_ids):
        raise ValueError("quarantine_ids cannot contain duplicates")

    apply_baseline_schema(engine)
    values = tuple(str(value) for value in quarantine_ids)
    replay_id = str(replayed_by_dataset_run_id)
    with engine.begin() as connection:
        rows = connection.execute(
            select(quarantine_batch).where(quarantine_batch.c.quarantine_id.in_(values))
        ).mappings().all()
        by_id = {str(row["quarantine_id"]): row for row in rows}
        missing = [value for value in values if value not in by_id]
        if missing:
            raise KeyError(f"quarantine batches not found: {', '.join(missing)}")

        for value in values:
            row = by_id[value]
            if row["dataset_id"] != dataset_id:
                raise ValueError(
                    f"quarantine {value} belongs to dataset {row['dataset_id']}, not {dataset_id}"
                )
            existing = row["replayed_by_dataset_run_id"]
            if existing is not None and str(existing) != replay_id:
                raise QuarantineReplayMarkerConflict(
                    f"quarantine {value} was already replayed by {existing}"
                )

        for value in values:
            row = by_id[value]
            if row["replayed_by_dataset_run_id"] is not None:
                continue
            result = connection.execute(
                quarantine_batch.update()
                .where(
                    quarantine_batch.c.quarantine_id == value,
                    quarantine_batch.c.replayed_by_dataset_run_id.is_(None),
                )
                .values(replayed_by_dataset_run_id=replay_id)
            )
            if result.rowcount != 1:
                raise QuarantineReplayMarkerConflict(
                    f"quarantine {value} changed concurrently during replay correlation"
                )

        updated_rows = connection.execute(
            select(quarantine_batch).where(quarantine_batch.c.quarantine_id.in_(values))
        ).mappings().all()

    updated = {
        str(row["quarantine_id"]): _quarantine_from_row(dict(row))
        for row in updated_rows
    }
    return tuple(updated[value] for value in values)


def _checkpoint_from_row(row: dict[str, object]) -> CDCCheckpointState:
    return CDCCheckpointState(
        dataset_id=str(row["dataset_id"]),
        checkpoint=CDCCheckpoint(positions=tuple(row["positions"])),
        committed_dataset_run_id=UUID(str(row["committed_dataset_run_id"])),
        version=int(row["version"]),
    )


def read_cdc_checkpoint(engine: Engine, dataset_id: str) -> CDCCheckpointState | None:
    """Read the environment-local framework CDC apply checkpoint."""

    apply_baseline_schema(engine)
    with engine.connect() as connection:
        row = connection.execute(
            select(cdc_checkpoint).where(cdc_checkpoint.c.dataset_id == dataset_id)
        ).mappings().first()
    if row is None:
        return None
    return _checkpoint_from_row(dict(row))


def commit_cdc_checkpoint(
    engine: Engine,
    *,
    dataset_id: str,
    checkpoint: CDCCheckpoint,
    dataset_run_id: UUID,
    expected_version: int,
    gate: StateCommitGate,
) -> CDCCheckpointState:
    """Commit CDC apply progress with semantic gates and optimistic concurrency.

    This is framework downstream/apply progress. For Fabric-native or external CDC,
    the provider remains the physical capture progress owner; its native checkpoint
    reference stays in ``CaptureReceipt`` and is not overwritten here.
    """

    if expected_version < 0:
        raise ValueError("expected_version must be >= 0")

    apply_baseline_schema(engine)
    now = datetime.now(timezone.utc)
    serialized = checkpoint.model_dump(mode="json")["positions"]

    with engine.begin() as connection:
        current_row = connection.execute(
            select(cdc_checkpoint).where(cdc_checkpoint.c.dataset_id == dataset_id)
        ).mappings().first()

        if current_row is None:
            if expected_version != 0:
                raise CDCCheckpointVersionConflict(
                    f"CDC checkpoint {dataset_id} does not exist at expected version "
                    f"{expected_version}"
                )
            CDCCheckpointTransition(before=None, after=checkpoint, gate=gate)
            connection.execute(
                cdc_checkpoint.insert().values(
                    dataset_id=dataset_id,
                    positions=serialized,
                    committed_dataset_run_id=str(dataset_run_id),
                    version=1,
                    created_at=now,
                    updated_at=None,
                )
            )
            return CDCCheckpointState(
                dataset_id=dataset_id,
                checkpoint=checkpoint,
                committed_dataset_run_id=dataset_run_id,
                version=1,
            )

        current = _checkpoint_from_row(dict(current_row))
        if current.version != expected_version:
            raise CDCCheckpointVersionConflict(
                f"CDC checkpoint {dataset_id} expected version {expected_version}, "
                f"current version is {current.version}"
            )
        CDCCheckpointTransition(before=current.checkpoint, after=checkpoint, gate=gate)
        next_version = current.version + 1
        result = connection.execute(
            cdc_checkpoint.update()
            .where(
                cdc_checkpoint.c.dataset_id == dataset_id,
                cdc_checkpoint.c.version == expected_version,
            )
            .values(
                positions=serialized,
                committed_dataset_run_id=str(dataset_run_id),
                version=next_version,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            raise CDCCheckpointVersionConflict(
                f"CDC checkpoint {dataset_id} changed concurrently"
            )

    return CDCCheckpointState(
        dataset_id=dataset_id,
        checkpoint=checkpoint,
        committed_dataset_run_id=dataset_run_id,
        version=next_version,
    )


__all__ = [
    "CDCCheckpointState",
    "CDCCheckpointVersionConflict",
    "QuarantineReplayMarkerConflict",
    "commit_cdc_checkpoint",
    "mark_quarantine_replayed",
    "read_cdc_checkpoint",
    "read_quarantine_batches",
    "read_quarantine_batches_for_run",
    "record_attempt_lineage",
    "record_capture_receipt",
    "record_quarantine_batch",
    "record_reprocess_request",
]
