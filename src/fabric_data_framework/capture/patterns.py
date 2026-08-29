"""Executable catalog for mainstream enterprise data-engineering capture patterns.

CapturePattern is an onboarding/source-fidelity classification. It deliberately does
not replace the coarser CaptureStrategy semantic contract. Provider families such as
Debezium/Kafka, Delta CDF, API cursors and file manifests can share framework capture
semantics while exposing materially different delete visibility, change fidelity,
Bronze storage and retry identities.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from ..config import ApplyStrategy, CaptureStrategy, DatasetConfig, FrozenModel


class CapturePattern(str, Enum):
    FULL_SNAPSHOT = "FULL_SNAPSHOT"
    WATERMARK_INCREMENTAL = "WATERMARK_INCREMENTAL"
    WATERMARK_LOOKBACK = "WATERMARK_LOOKBACK"
    WATERMARK_TOMBSTONE = "WATERMARK_TOMBSTONE"
    CDC_NET_CURRENT = "CDC_NET_CURRENT"
    CDC_NET_OBSERVATION = "CDC_NET_OBSERVATION"
    CDC_FULL = "CDC_FULL"
    TRANSACTION_LOG_CDC = "TRANSACTION_LOG_CDC"
    DEBEZIUM_KAFKA = "DEBEZIUM_KAFKA"
    DELTA_CDF = "DELTA_CDF"
    EVENT_SOURCE = "EVENT_SOURCE"
    SNAPSHOT_DIFF = "SNAPSHOT_DIFF"
    API_CURSOR_INCREMENTAL = "API_CURSOR_INCREMENTAL"
    FILE_INCREMENTAL = "FILE_INCREMENTAL"


class ChangeFidelity(str, Enum):
    CURRENT_STATE = "CURRENT_STATE"
    NET_CHANGE = "NET_CHANGE"
    FULL_CHANGE = "FULL_CHANGE"
    FULL_EVENT = "FULL_EVENT"
    SOURCE_DEFINED = "SOURCE_DEFINED"


class DeleteVisibility(str, Enum):
    NONE = "NONE"
    SNAPSHOT_INFERRED = "SNAPSHOT_INFERRED"
    TOMBSTONE = "TOMBSTONE"
    EXPLICIT_EVENT = "EXPLICIT_EVENT"
    SOURCE_DEFINED = "SOURCE_DEFINED"


class BronzeWriteMode(str, Enum):
    OVERWRITE = "OVERWRITE"
    MERGE = "MERGE"
    APPEND = "APPEND"


class BronzeContent(str, Enum):
    CURRENT_SNAPSHOT = "CURRENT_SNAPSHOT"
    CURRENT_STATE = "CURRENT_STATE"
    BATCH_OBSERVATIONS = "BATCH_OBSERVATIONS"
    CHANGE_EVENTS = "CHANGE_EVENTS"
    BUSINESS_EVENTS = "BUSINESS_EVENTS"
    SNAPSHOT_DIFF_EVENTS = "SNAPSHOT_DIFF_EVENTS"
    RAW_FILES_OR_CURRENT_STATE = "RAW_FILES_OR_CURRENT_STATE"


class HistoryFidelity(str, Enum):
    NONE = "NONE"
    OBSERVED_CHANGES = "OBSERVED_CHANGES"
    BATCH_GRAIN = "BATCH_GRAIN"
    FULL_EVENT = "FULL_EVENT"
    SNAPSHOT_GRAIN = "SNAPSHOT_GRAIN"
    SOURCE_DEFINED = "SOURCE_DEFINED"


class CapturePatternSpec(FrozenModel):
    pattern: CapturePattern
    source_description: str = Field(min_length=1)
    compatible_capture_strategies: frozenset[CaptureStrategy]
    change_fidelity: ChangeFidelity
    delete_visibility: DeleteVisibility
    default_bronze_write_mode: BronzeWriteMode
    allowed_bronze_write_modes: frozenset[BronzeWriteMode]
    bronze_content: BronzeContent
    retry_identity: tuple[str, ...]
    scd1_supported: bool = True
    scd2_history_fidelity: HistoryFidelity
    recommended_apply_strategies: tuple[ApplyStrategy, ...]
    guidance: str = Field(min_length=1)


class CapturePatternAssessment(FrozenModel):
    pattern: CapturePattern
    valid: bool
    warnings: tuple[str, ...] = ()
    scd2_history_fidelity: HistoryFidelity
    delete_visibility: DeleteVisibility
    bronze_write_mode: BronzeWriteMode


_PATTERN_SPECS = (
    CapturePatternSpec(
        pattern=CapturePattern.FULL_SNAPSHOT,
        source_description="Authoritative full current-state snapshot of the source object.",
        compatible_capture_strategies=frozenset({CaptureStrategy.FULL}),
        change_fidelity=ChangeFidelity.CURRENT_STATE,
        delete_visibility=DeleteVisibility.SNAPSHOT_INFERRED,
        default_bronze_write_mode=BronzeWriteMode.OVERWRITE,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.OVERWRITE}),
        bronze_content=BronzeContent.CURRENT_SNAPSHOT,
        retry_identity=("snapshot_id",),
        scd2_history_fidelity=HistoryFidelity.SNAPSHOT_GRAIN,
        recommended_apply_strategies=(ApplyStrategy.REPLACE, ApplyStrategy.SCD1),
        guidance=(
            "Best for authoritative refresh/current-state targets. Deletes are inferable only "
            "by comparing complete snapshots. For SCD2 or delete propagation choose the "
            "SNAPSHOT_DIFF pattern rather than pretending one full snapshot contains row events."
        ),
    ),
    CapturePatternSpec(
        pattern=CapturePattern.WATERMARK_INCREMENTAL,
        source_description="Rows newer than a monotonic updated/version watermark.",
        compatible_capture_strategies=frozenset({CaptureStrategy.WATERMARK}),
        change_fidelity=ChangeFidelity.CURRENT_STATE,
        delete_visibility=DeleteVisibility.NONE,
        default_bronze_write_mode=BronzeWriteMode.MERGE,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.MERGE}),
        bronze_content=BronzeContent.CURRENT_STATE,
        retry_identity=("primary_key", "watermark", "tie_breaker"),
        scd2_history_fidelity=HistoryFidelity.OBSERVED_CHANGES,
        recommended_apply_strategies=(ApplyStrategy.UPSERT, ApplyStrategy.SCD1, ApplyStrategy.SCD2),
        guidance=(
            "Use only when source updates advance the watermark reliably. Hard deletes are not "
            "visible. SCD2 records captured observations, not every intermediate source change."
        ),
    ),
    CapturePatternSpec(
        pattern=CapturePattern.WATERMARK_LOOKBACK,
        source_description="Watermark incremental with an overlap/lookback window that intentionally re-reads rows.",
        compatible_capture_strategies=frozenset({CaptureStrategy.WATERMARK}),
        change_fidelity=ChangeFidelity.CURRENT_STATE,
        delete_visibility=DeleteVisibility.NONE,
        default_bronze_write_mode=BronzeWriteMode.MERGE,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.MERGE}),
        bronze_content=BronzeContent.CURRENT_STATE,
        retry_identity=("primary_key", "event_time_or_version"),
        scd2_history_fidelity=HistoryFidelity.OBSERVED_CHANGES,
        recommended_apply_strategies=(ApplyStrategy.UPSERT, ApplyStrategy.SCD1, ApplyStrategy.SCD2),
        guidance=(
            "Preferred over a brittle strict timestamp boundary when clocks/transactions can be "
            "late. Overlap must be positive and downstream apply must be idempotent."
        ),
    ),
    CapturePatternSpec(
        pattern=CapturePattern.WATERMARK_TOMBSTONE,
        source_description="Watermark/current-state changes plus an explicit source delete marker.",
        compatible_capture_strategies=frozenset({CaptureStrategy.WATERMARK}),
        change_fidelity=ChangeFidelity.NET_CHANGE,
        delete_visibility=DeleteVisibility.TOMBSTONE,
        default_bronze_write_mode=BronzeWriteMode.MERGE,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.MERGE, BronzeWriteMode.APPEND}),
        bronze_content=BronzeContent.CURRENT_STATE,
        retry_identity=("primary_key", "event_time_or_version", "delete_marker"),
        scd2_history_fidelity=HistoryFidelity.OBSERVED_CHANGES,
        recommended_apply_strategies=(ApplyStrategy.UPSERT, ApplyStrategy.SCD1, ApplyStrategy.SCD2),
        guidance=(
            "Use when deletes are exposed as soft-delete/tombstone rows. The delete marker must "
            "participate in ordering/idempotency and map to an explicit delete policy."
        ),
    ),
    CapturePatternSpec(
        pattern=CapturePattern.CDC_NET_CURRENT,
        source_description="Native CDC window collapsed to the final change/state per business key.",
        compatible_capture_strategies=frozenset({CaptureStrategy.CDC}),
        change_fidelity=ChangeFidelity.NET_CHANGE,
        delete_visibility=DeleteVisibility.EXPLICIT_EVENT,
        default_bronze_write_mode=BronzeWriteMode.MERGE,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.MERGE}),
        bronze_content=BronzeContent.CURRENT_STATE,
        retry_identity=("cdc_position", "primary_key"),
        scd2_history_fidelity=HistoryFidelity.BATCH_GRAIN,
        recommended_apply_strategies=(ApplyStrategy.UPSERT, ApplyStrategy.SCD1, ApplyStrategy.SCD2),
        guidance=(
            "Efficient current-state feed. Intermediate changes inside the CDC window are already "
            "lost at capture, so SCD2 can only represent the surviving batch-level observation."
        ),
    ),
    CapturePatternSpec(
        pattern=CapturePattern.CDC_NET_OBSERVATION,
        source_description="Native CDC net changes appended as one observation per key per capture window.",
        compatible_capture_strategies=frozenset({CaptureStrategy.CDC}),
        change_fidelity=ChangeFidelity.NET_CHANGE,
        delete_visibility=DeleteVisibility.EXPLICIT_EVENT,
        default_bronze_write_mode=BronzeWriteMode.APPEND,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.APPEND}),
        bronze_content=BronzeContent.BATCH_OBSERVATIONS,
        retry_identity=("capture_batch_id", "primary_key"),
        scd2_history_fidelity=HistoryFidelity.BATCH_GRAIN,
        recommended_apply_strategies=(ApplyStrategy.APPEND, ApplyStrategy.UPSERT, ApplyStrategy.SCD1, ApplyStrategy.SCD2),
        guidance=(
            "Preserves what each batch observed without claiming full source history. Useful for "
            "audit/diagnostics, but multiple source updates collapsed by native net-change capture "
            "cannot be reconstructed later."
        ),
    ),
    CapturePatternSpec(
        pattern=CapturePattern.CDC_FULL,
        source_description="Every ordered source INSERT/UPDATE/DELETE change in the capture window.",
        compatible_capture_strategies=frozenset({CaptureStrategy.CDC}),
        change_fidelity=ChangeFidelity.FULL_CHANGE,
        delete_visibility=DeleteVisibility.EXPLICIT_EVENT,
        default_bronze_write_mode=BronzeWriteMode.APPEND,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.APPEND}),
        bronze_content=BronzeContent.CHANGE_EVENTS,
        retry_identity=("source_position", "event_id"),
        scd2_history_fidelity=HistoryFidelity.FULL_EVENT,
        recommended_apply_strategies=(ApplyStrategy.APPEND, ApplyStrategy.UPSERT, ApplyStrategy.SCD1, ApplyStrategy.SCD2),
        guidance="Preferred CDC shape when complete change history is required.",
    ),
    CapturePatternSpec(
        pattern=CapturePattern.TRANSACTION_LOG_CDC,
        source_description="Ordered database transaction-log changes such as LSN/SCN/binlog positions.",
        compatible_capture_strategies=frozenset({CaptureStrategy.CDC}),
        change_fidelity=ChangeFidelity.FULL_CHANGE,
        delete_visibility=DeleteVisibility.EXPLICIT_EVENT,
        default_bronze_write_mode=BronzeWriteMode.APPEND,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.APPEND}),
        bronze_content=BronzeContent.CHANGE_EVENTS,
        retry_identity=("log_position", "row_sequence_or_event_id"),
        scd2_history_fidelity=HistoryFidelity.FULL_EVENT,
        recommended_apply_strategies=(ApplyStrategy.APPEND, ApplyStrategy.UPSERT, ApplyStrategy.SCD1, ApplyStrategy.SCD2),
        guidance=(
            "Normalize provider log coordinates into canonical CDCSourcePosition. If one log "
            "position contains several row changes, row sequence is required to prove order."
        ),
    ),
    CapturePatternSpec(
        pattern=CapturePattern.DEBEZIUM_KAFKA,
        source_description="Debezium change events consumed from Kafka in topic/partition/offset order.",
        compatible_capture_strategies=frozenset({CaptureStrategy.CDC}),
        change_fidelity=ChangeFidelity.FULL_CHANGE,
        delete_visibility=DeleteVisibility.EXPLICIT_EVENT,
        default_bronze_write_mode=BronzeWriteMode.APPEND,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.APPEND}),
        bronze_content=BronzeContent.CHANGE_EVENTS,
        retry_identity=("topic", "partition", "offset"),
        scd2_history_fidelity=HistoryFidelity.FULL_EVENT,
        recommended_apply_strategies=(ApplyStrategy.APPEND, ApplyStrategy.UPSERT, ApplyStrategy.SCD1, ApplyStrategy.SCD2),
        guidance=(
            "Use the built-in debezium_kafka_v1 provider adapter/profile. Kafka offset is the "
            "canonical consumed order; database LSN/binlog values remain provider metadata."
        ),
    ),
    CapturePatternSpec(
        pattern=CapturePattern.DELTA_CDF,
        source_description="Delta Change Data Feed row events identified by commit version and change type.",
        compatible_capture_strategies=frozenset({CaptureStrategy.CDC}),
        change_fidelity=ChangeFidelity.FULL_CHANGE,
        delete_visibility=DeleteVisibility.EXPLICIT_EVENT,
        default_bronze_write_mode=BronzeWriteMode.APPEND,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.APPEND}),
        bronze_content=BronzeContent.CHANGE_EVENTS,
        retry_identity=("commit_version", "row_event_identity"),
        scd2_history_fidelity=HistoryFidelity.FULL_EVENT,
        recommended_apply_strategies=(ApplyStrategy.APPEND, ApplyStrategy.UPSERT, ApplyStrategy.SCD1, ApplyStrategy.SCD2),
        guidance=(
            "Preserve _change_type/_commit_version evidence and normalize insert/delete/update "
            "pre/post images before canonical CDC apply. Retention is part of recovery safety."
        ),
    ),
    CapturePatternSpec(
        pattern=CapturePattern.EVENT_SOURCE,
        source_description="Source records are immutable business/domain events rather than table mutations.",
        compatible_capture_strategies=frozenset({CaptureStrategy.STREAM}),
        change_fidelity=ChangeFidelity.FULL_EVENT,
        delete_visibility=DeleteVisibility.SOURCE_DEFINED,
        default_bronze_write_mode=BronzeWriteMode.APPEND,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.APPEND}),
        bronze_content=BronzeContent.BUSINESS_EVENTS,
        retry_identity=("event_id_or_partition_offset",),
        scd2_history_fidelity=HistoryFidelity.FULL_EVENT,
        recommended_apply_strategies=(ApplyStrategy.APPEND, ApplyStrategy.UPSERT, ApplyStrategy.SCD1, ApplyStrategy.SCD2),
        guidance=(
            "Keep raw events immutable. A business 'delete' exists only if the event contract "
            "defines one; do not infer relational deletes from event absence."
        ),
    ),
    CapturePatternSpec(
        pattern=CapturePattern.SNAPSHOT_DIFF,
        source_description="Complete snapshot N compared with complete snapshot N-1 to derive net I/U/D changes.",
        compatible_capture_strategies=frozenset({CaptureStrategy.SNAPSHOT}),
        change_fidelity=ChangeFidelity.NET_CHANGE,
        delete_visibility=DeleteVisibility.SNAPSHOT_INFERRED,
        default_bronze_write_mode=BronzeWriteMode.APPEND,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.MERGE, BronzeWriteMode.APPEND}),
        bronze_content=BronzeContent.SNAPSHOT_DIFF_EVENTS,
        retry_identity=("snapshot_id", "primary_key"),
        scd2_history_fidelity=HistoryFidelity.SNAPSHOT_GRAIN,
        recommended_apply_strategies=(ApplyStrategy.SNAPSHOT_DIFF, ApplyStrategy.SCD1, ApplyStrategy.SCD2),
        guidance=(
            "Requires complete authoritative snapshots. It can infer deletes and produce SCD2, "
            "but only at snapshot cadence; changes between snapshots are unknowable."
        ),
    ),
    CapturePatternSpec(
        pattern=CapturePattern.API_CURSOR_INCREMENTAL,
        source_description="API exposes changes or records through a stable cursor/pagination window.",
        compatible_capture_strategies=frozenset({CaptureStrategy.WATERMARK, CaptureStrategy.STREAM}),
        change_fidelity=ChangeFidelity.SOURCE_DEFINED,
        delete_visibility=DeleteVisibility.SOURCE_DEFINED,
        default_bronze_write_mode=BronzeWriteMode.MERGE,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.MERGE, BronzeWriteMode.APPEND}),
        bronze_content=BronzeContent.CURRENT_STATE,
        retry_identity=("frozen_window", "cursor_chain", "primary_key_or_event_id"),
        scd2_history_fidelity=HistoryFidelity.SOURCE_DEFINED,
        recommended_apply_strategies=(ApplyStrategy.UPSERT, ApplyStrategy.SCD1, ApplyStrategy.SCD2, ApplyStrategy.APPEND),
        guidance=(
            "Freeze bounds/predicate before page 1 and validate cursor continuity/completeness. "
            "Whether deletes and full history exist depends on the API contract, not pagination."
        ),
    ),
    CapturePatternSpec(
        pattern=CapturePattern.FILE_INCREMENTAL,
        source_description="New or changed immutable/versioned files discovered from governed storage.",
        compatible_capture_strategies=frozenset({CaptureStrategy.SNAPSHOT, CaptureStrategy.STREAM}),
        change_fidelity=ChangeFidelity.SOURCE_DEFINED,
        delete_visibility=DeleteVisibility.SOURCE_DEFINED,
        default_bronze_write_mode=BronzeWriteMode.APPEND,
        allowed_bronze_write_modes=frozenset({BronzeWriteMode.APPEND, BronzeWriteMode.MERGE}),
        bronze_content=BronzeContent.RAW_FILES_OR_CURRENT_STATE,
        retry_identity=("file_uri", "version_token_or_checksum"),
        scd2_history_fidelity=HistoryFidelity.SOURCE_DEFINED,
        recommended_apply_strategies=(ApplyStrategy.APPEND, ApplyStrategy.UPSERT, ApplyStrategy.SCD1, ApplyStrategy.SCD2),
        guidance=(
            "Freeze a complete manifest of ready files and stable version tokens. History/delete "
            "capability depends on whether file rows are events, snapshots or current-state extracts."
        ),
    ),
)

_PATTERN_BY_NAME = {item.pattern: item for item in _PATTERN_SPECS}


def capture_pattern_spec(pattern: CapturePattern) -> CapturePatternSpec:
    return _PATTERN_BY_NAME[pattern]


def capture_pattern_catalog() -> tuple[CapturePatternSpec, ...]:
    return _PATTERN_SPECS


def assess_dataset_capture_pattern(
    config: DatasetConfig,
    pattern: CapturePattern,
    *,
    bronze_write_mode: BronzeWriteMode | None = None,
) -> CapturePatternAssessment:
    """Validate a DatasetConfig against the selected onboarding capture pattern.

    The assessment intentionally does not claim provider transport certification. It
    validates semantic fit and returns history/delete caveats that should be visible
    during domain CI/review.
    """

    spec = capture_pattern_spec(pattern)
    if config.load.capture_strategy not in spec.compatible_capture_strategies:
        expected = ", ".join(sorted(item.value for item in spec.compatible_capture_strategies))
        raise ValueError(
            f"capture pattern {pattern.value} expects capture strategy in [{expected}], "
            f"got {config.load.capture_strategy.value}"
        )

    selected_bronze_mode = bronze_write_mode or spec.default_bronze_write_mode
    if selected_bronze_mode not in spec.allowed_bronze_write_modes:
        allowed = ", ".join(sorted(item.value for item in spec.allowed_bronze_write_modes))
        raise ValueError(
            f"capture pattern {pattern.value} does not allow Bronze {selected_bronze_mode.value}; "
            f"allowed=[{allowed}]"
        )

    if pattern is CapturePattern.WATERMARK_LOOKBACK:
        watermark = config.load.watermark
        if watermark is None or watermark.overlap_window_seconds <= 0:
            raise ValueError("WATERMARK_LOOKBACK requires a positive watermark overlap window")

    if pattern is CapturePattern.WATERMARK_INCREMENTAL:
        watermark = config.load.watermark
        if watermark is None:
            raise ValueError("WATERMARK_INCREMENTAL requires watermark configuration")

    warnings: list[str] = []
    if config.load.apply_strategy is ApplyStrategy.SCD2:
        if spec.scd2_history_fidelity is HistoryFidelity.OBSERVED_CHANGES:
            warnings.append(
                "SCD2 records only changes observed by the incremental capture; hard deletes and "
                "intermediate source changes may be missing."
            )
        elif spec.scd2_history_fidelity is HistoryFidelity.BATCH_GRAIN:
            warnings.append(
                "SCD2 is limited to net/batch-grain history because intermediate source changes "
                "were collapsed before framework apply."
            )
        elif spec.scd2_history_fidelity is HistoryFidelity.SNAPSHOT_GRAIN:
            warnings.append(
                "SCD2 history is snapshot-grain; multiple changes between snapshots cannot be reconstructed."
            )
        elif spec.scd2_history_fidelity is HistoryFidelity.SOURCE_DEFINED:
            warnings.append(
                "SCD2 fidelity depends on the source contract; verify event/change completeness before claiming full history."
            )

    if spec.delete_visibility is DeleteVisibility.NONE and config.load.delete_policy != "IGNORE":
        warnings.append(
            "The source pattern does not expose hard deletes; a non-IGNORE delete policy cannot discover absent rows."
        )

    if pattern is CapturePattern.FULL_SNAPSHOT and config.load.apply_strategy is ApplyStrategy.SCD2:
        warnings.append(
            "Use SNAPSHOT_DIFF when SCD2/delete inference is required from recurring complete snapshots."
        )

    return CapturePatternAssessment(
        pattern=pattern,
        valid=True,
        warnings=tuple(warnings),
        scd2_history_fidelity=spec.scd2_history_fidelity,
        delete_visibility=spec.delete_visibility,
        bronze_write_mode=selected_bronze_mode,
    )


__all__ = [
    "BronzeContent",
    "BronzeWriteMode",
    "CapturePattern",
    "CapturePatternAssessment",
    "CapturePatternSpec",
    "ChangeFidelity",
    "DeleteVisibility",
    "HistoryFidelity",
    "assess_dataset_capture_pattern",
    "capture_pattern_catalog",
    "capture_pattern_spec",
]
