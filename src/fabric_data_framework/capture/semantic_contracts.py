"""Orthogonal capture semantics aligned to the data-engineering cheatsheet.

The existing :class:`CapturePattern` catalog remains a supported onboarding preset
surface.  This module is the composition layer that keeps source semantics, change
granularity, read strategy, delete semantics and Bronze meaning independent so new
valid combinations do not require a Cartesian-product enum member.
"""

from __future__ import annotations

from enum import Enum

from fabric_data_framework.contracts.base import FrozenModel
from .patterns import BronzeWriteMode, CapturePattern, HistoryFidelity


class SourceSemantics(str, Enum):
    CURRENT_STATE = "CURRENT_STATE"
    CHANGE_FEED = "CHANGE_FEED"
    BUSINESS_EVENT = "BUSINESS_EVENT"
    SOURCE_DEFINED = "SOURCE_DEFINED"


class ChangeGranularity(str, Enum):
    CURRENT = "CURRENT"
    SNAPSHOT = "SNAPSHOT"
    NET = "NET"
    FULL = "FULL"
    EVENT = "EVENT"
    SOURCE_DEFINED = "SOURCE_DEFINED"


class ReadStrategy(str, Enum):
    FULL = "FULL"
    WATERMARK = "WATERMARK"
    WATERMARK_LOOKBACK = "WATERMARK_LOOKBACK"
    CHANGE_WINDOW = "CHANGE_WINDOW"
    SOURCE_POSITION = "SOURCE_POSITION"
    PARTITION_OFFSET = "PARTITION_OFFSET"
    COMMIT_VERSION = "COMMIT_VERSION"
    CURSOR = "CURSOR"
    FILE_MANIFEST = "FILE_MANIFEST"
    SOURCE_DEFINED = "SOURCE_DEFINED"


class DeleteSemantics(str, Enum):
    NONE = "NONE"
    SNAPSHOT_ABSENCE = "SNAPSHOT_ABSENCE"
    SOFT_DELETE = "SOFT_DELETE"
    EXPLICIT_EVENT = "EXPLICIT_EVENT"
    SOURCE_DEFINED = "SOURCE_DEFINED"


class BronzeContract(str, Enum):
    CURRENT = "CURRENT"
    RAW_OBSERVATION = "RAW_OBSERVATION"
    SNAPSHOT_HISTORY = "SNAPSHOT_HISTORY"
    EVENT = "EVENT"


class CheatsheetPattern(str, Enum):
    FULL_SNAPSHOT_CURRENT = "FULL_SNAPSHOT_CURRENT"
    FULL_SNAPSHOT_HISTORY = "FULL_SNAPSHOT_HISTORY"
    WATERMARK_CURRENT = "WATERMARK_CURRENT"
    WATERMARK_LOOKBACK_CURRENT = "WATERMARK_LOOKBACK_CURRENT"
    WATERMARK_LOOKBACK_RAW = "WATERMARK_LOOKBACK_RAW"
    WATERMARK_SOFT_DELETE_CURRENT = "WATERMARK_SOFT_DELETE_CURRENT"
    WATERMARK_LOOKBACK_SOFT_DELETE_RAW = "WATERMARK_LOOKBACK_SOFT_DELETE_RAW"
    NET_CHANGES_CURRENT = "NET_CHANGES_CURRENT"
    NET_CHANGES_APPEND = "NET_CHANGES_APPEND"
    FULL_CHANGES_EVENT = "FULL_CHANGES_EVENT"
    FULL_CHANGES_CURRENT_LOSSY = "FULL_CHANGES_CURRENT_LOSSY"
    BUSINESS_EVENTS = "BUSINESS_EVENTS"
    SNAPSHOT_DIFF_CURRENT = "SNAPSHOT_DIFF_CURRENT"
    SNAPSHOT_DIFF_APPEND = "SNAPSHOT_DIFF_APPEND"


class CaptureProviderFamily(str, Enum):
    GENERIC = "GENERIC"
    DB_QUERY = "DB_QUERY"
    NATIVE_CDC = "NATIVE_CDC"
    TRANSACTION_LOG = "TRANSACTION_LOG"
    DEBEZIUM_KAFKA = "DEBEZIUM_KAFKA"
    DELTA_CDF = "DELTA_CDF"
    API = "API"
    FILE = "FILE"
    BUSINESS_EVENT_SOURCE = "BUSINESS_EVENT_SOURCE"


class CaptureSemanticContract(FrozenModel):
    source_semantics: SourceSemantics
    change_granularity: ChangeGranularity
    read_strategy: ReadStrategy
    delete_semantics: DeleteSemantics
    bronze_contract: BronzeContract
    bronze_write_mode: BronzeWriteMode
    history_fidelity: HistoryFidelity
    retry_identity: tuple[str, ...]
    scd1_supported: bool = True
    scd2_supported: bool = True
    intentionally_lossy: bool = False
    guidance: str


class LegacyCapturePatternProjection(FrozenModel):
    pattern: CapturePattern
    semantics: CaptureSemanticContract
    provider_family: CaptureProviderFamily


def _contract(
    *,
    source: SourceSemantics,
    granularity: ChangeGranularity,
    read: ReadStrategy,
    delete: DeleteSemantics,
    bronze: BronzeContract,
    write: BronzeWriteMode,
    history: HistoryFidelity,
    retry_identity: tuple[str, ...],
    guidance: str,
    intentionally_lossy: bool = False,
) -> CaptureSemanticContract:
    return CaptureSemanticContract(
        source_semantics=source,
        change_granularity=granularity,
        read_strategy=read,
        delete_semantics=delete,
        bronze_contract=bronze,
        bronze_write_mode=write,
        history_fidelity=history,
        retry_identity=retry_identity,
        intentionally_lossy=intentionally_lossy,
        guidance=guidance,
    )


_CHEATSHEET_CONTRACTS: dict[CheatsheetPattern, CaptureSemanticContract] = {
    CheatsheetPattern.FULL_SNAPSHOT_CURRENT: _contract(
        source=SourceSemantics.CURRENT_STATE,
        granularity=ChangeGranularity.SNAPSHOT,
        read=ReadStrategy.FULL,
        delete=DeleteSemantics.SNAPSHOT_ABSENCE,
        bronze=BronzeContract.CURRENT,
        write=BronzeWriteMode.OVERWRITE,
        history=HistoryFidelity.NONE,
        retry_identity=("snapshot_id",),
        guidance="Complete authoritative snapshot materialized as current Bronze.",
    ),
    CheatsheetPattern.FULL_SNAPSHOT_HISTORY: _contract(
        source=SourceSemantics.CURRENT_STATE,
        granularity=ChangeGranularity.SNAPSHOT,
        read=ReadStrategy.FULL,
        delete=DeleteSemantics.SNAPSHOT_ABSENCE,
        bronze=BronzeContract.SNAPSHOT_HISTORY,
        write=BronzeWriteMode.APPEND,
        history=HistoryFidelity.SNAPSHOT_GRAIN,
        retry_identity=("snapshot_id",),
        guidance="Append complete periodic source pictures; history is snapshot-grain, not full change history.",
    ),
    CheatsheetPattern.WATERMARK_CURRENT: _contract(
        source=SourceSemantics.CURRENT_STATE,
        granularity=ChangeGranularity.CURRENT,
        read=ReadStrategy.WATERMARK,
        delete=DeleteSemantics.NONE,
        bronze=BronzeContract.CURRENT,
        write=BronzeWriteMode.MERGE,
        history=HistoryFidelity.OBSERVED_CHANGES,
        retry_identity=("business_key", "source_version_or_watermark", "tie_breaker"),
        guidance="Current rows after a reliable watermark; hard deletes are invisible without another signal.",
    ),
    CheatsheetPattern.WATERMARK_LOOKBACK_CURRENT: _contract(
        source=SourceSemantics.CURRENT_STATE,
        granularity=ChangeGranularity.CURRENT,
        read=ReadStrategy.WATERMARK_LOOKBACK,
        delete=DeleteSemantics.NONE,
        bronze=BronzeContract.CURRENT,
        write=BronzeWriteMode.MERGE,
        history=HistoryFidelity.OBSERVED_CHANGES,
        retry_identity=("business_key", "source_version_or_order"),
        guidance="Overlap is intentionally reread and absorbed idempotently into current Bronze.",
    ),
    CheatsheetPattern.WATERMARK_LOOKBACK_RAW: _contract(
        source=SourceSemantics.CURRENT_STATE,
        granularity=ChangeGranularity.CURRENT,
        read=ReadStrategy.WATERMARK_LOOKBACK,
        delete=DeleteSemantics.NONE,
        bronze=BronzeContract.RAW_OBSERVATION,
        write=BronzeWriteMode.APPEND,
        history=HistoryFidelity.OBSERVED_CHANGES,
        retry_identity=("ingestion_run_id", "business_key", "source_version_or_order"),
        guidance="Retain intentional lookback rereads in Bronze; Silver collapses the same source version across deliveries.",
    ),
    CheatsheetPattern.WATERMARK_SOFT_DELETE_CURRENT: _contract(
        source=SourceSemantics.CURRENT_STATE,
        granularity=ChangeGranularity.CURRENT,
        read=ReadStrategy.WATERMARK,
        delete=DeleteSemantics.SOFT_DELETE,
        bronze=BronzeContract.CURRENT,
        write=BronzeWriteMode.MERGE,
        history=HistoryFidelity.OBSERVED_CHANGES,
        retry_identity=("business_key", "source_version_or_order", "delete_marker"),
        guidance="Soft-delete rows keep logical deletes observable while retained by the source.",
    ),
    CheatsheetPattern.WATERMARK_LOOKBACK_SOFT_DELETE_RAW: _contract(
        source=SourceSemantics.CURRENT_STATE,
        granularity=ChangeGranularity.CURRENT,
        read=ReadStrategy.WATERMARK_LOOKBACK,
        delete=DeleteSemantics.SOFT_DELETE,
        bronze=BronzeContract.RAW_OBSERVATION,
        write=BronzeWriteMode.APPEND,
        history=HistoryFidelity.OBSERVED_CHANGES,
        retry_identity=("ingestion_run_id", "business_key", "source_version_or_order", "delete_marker"),
        guidance="Combine overlap safety, retained extraction observations and explicit soft-delete state without a combinatorial legacy enum.",
    ),
    CheatsheetPattern.NET_CHANGES_CURRENT: _contract(
        source=SourceSemantics.CHANGE_FEED,
        granularity=ChangeGranularity.NET,
        read=ReadStrategy.CHANGE_WINDOW,
        delete=DeleteSemantics.EXPLICIT_EVENT,
        bronze=BronzeContract.CURRENT,
        write=BronzeWriteMode.MERGE,
        history=HistoryFidelity.BATCH_GRAIN,
        retry_identity=("change_window", "business_key"),
        guidance="Apply the final net result per entity/window to current Bronze; intermediate source changes are already lost.",
    ),
    CheatsheetPattern.NET_CHANGES_APPEND: _contract(
        source=SourceSemantics.CHANGE_FEED,
        granularity=ChangeGranularity.NET,
        read=ReadStrategy.CHANGE_WINDOW,
        delete=DeleteSemantics.EXPLICIT_EVENT,
        bronze=BronzeContract.RAW_OBSERVATION,
        write=BronzeWriteMode.APPEND,
        history=HistoryFidelity.BATCH_GRAIN,
        retry_identity=("change_window", "business_key"),
        guidance="Append net-window observations for audit/replay while retaining only batch-grain source fidelity.",
    ),
    CheatsheetPattern.FULL_CHANGES_EVENT: _contract(
        source=SourceSemantics.CHANGE_FEED,
        granularity=ChangeGranularity.FULL,
        read=ReadStrategy.SOURCE_POSITION,
        delete=DeleteSemantics.EXPLICIT_EVENT,
        bronze=BronzeContract.EVENT,
        write=BronzeWriteMode.APPEND,
        history=HistoryFidelity.FULL_EVENT,
        retry_identity=("source_position", "event_or_row_sequence"),
        guidance="Preserve every captured ordered row change as Event Bronze.",
    ),
    CheatsheetPattern.FULL_CHANGES_CURRENT_LOSSY: _contract(
        source=SourceSemantics.CHANGE_FEED,
        granularity=ChangeGranularity.FULL,
        read=ReadStrategy.SOURCE_POSITION,
        delete=DeleteSemantics.EXPLICIT_EVENT,
        bronze=BronzeContract.CURRENT,
        write=BronzeWriteMode.MERGE,
        history=HistoryFidelity.NONE,
        retry_identity=("source_window", "business_key", "terminal_source_position"),
        intentionally_lossy=True,
        guidance="Order and collapse full changes per business key before MERGE; this intentionally discards Event Bronze replay history.",
    ),
    CheatsheetPattern.BUSINESS_EVENTS: _contract(
        source=SourceSemantics.BUSINESS_EVENT,
        granularity=ChangeGranularity.EVENT,
        read=ReadStrategy.SOURCE_DEFINED,
        delete=DeleteSemantics.SOURCE_DEFINED,
        bronze=BronzeContract.EVENT,
        write=BronzeWriteMode.APPEND,
        history=HistoryFidelity.FULL_EVENT,
        retry_identity=("event_id_or_provider_record_identity",),
        guidance="Preserve immutable domain events; relational current/SCD2 views are downstream projections.",
    ),
    CheatsheetPattern.SNAPSHOT_DIFF_CURRENT: _contract(
        source=SourceSemantics.CURRENT_STATE,
        granularity=ChangeGranularity.SNAPSHOT,
        read=ReadStrategy.FULL,
        delete=DeleteSemantics.SNAPSHOT_ABSENCE,
        bronze=BronzeContract.CURRENT,
        write=BronzeWriteMode.MERGE,
        history=HistoryFidelity.SNAPSHOT_GRAIN,
        retry_identity=("previous_snapshot_id", "current_snapshot_id", "business_key"),
        guidance="Diff two complete comparable snapshots and apply derived I/U/D to current Bronze.",
    ),
    CheatsheetPattern.SNAPSHOT_DIFF_APPEND: _contract(
        source=SourceSemantics.CURRENT_STATE,
        granularity=ChangeGranularity.SNAPSHOT,
        read=ReadStrategy.FULL,
        delete=DeleteSemantics.SNAPSHOT_ABSENCE,
        bronze=BronzeContract.EVENT,
        write=BronzeWriteMode.APPEND,
        history=HistoryFidelity.SNAPSHOT_GRAIN,
        retry_identity=("previous_snapshot_id", "current_snapshot_id", "business_key"),
        guidance="Append derived snapshot-to-snapshot change events; changes between snapshots remain unknowable.",
    ),
}


def cheatsheet_pattern_contract(pattern: CheatsheetPattern) -> CaptureSemanticContract:
    return _CHEATSHEET_CONTRACTS[pattern]


def cheatsheet_pattern_catalog() -> tuple[tuple[CheatsheetPattern, CaptureSemanticContract], ...]:
    return tuple((pattern, _CHEATSHEET_CONTRACTS[pattern]) for pattern in CheatsheetPattern)


_LEGACY_PROJECTIONS: dict[CapturePattern, LegacyCapturePatternProjection] = {
    CapturePattern.FULL_SNAPSHOT: LegacyCapturePatternProjection(
        pattern=CapturePattern.FULL_SNAPSHOT,
        semantics=_CHEATSHEET_CONTRACTS[CheatsheetPattern.FULL_SNAPSHOT_CURRENT],
        provider_family=CaptureProviderFamily.DB_QUERY,
    ),
    CapturePattern.WATERMARK_INCREMENTAL: LegacyCapturePatternProjection(
        pattern=CapturePattern.WATERMARK_INCREMENTAL,
        semantics=_CHEATSHEET_CONTRACTS[CheatsheetPattern.WATERMARK_CURRENT],
        provider_family=CaptureProviderFamily.DB_QUERY,
    ),
    CapturePattern.WATERMARK_LOOKBACK: LegacyCapturePatternProjection(
        pattern=CapturePattern.WATERMARK_LOOKBACK,
        semantics=_CHEATSHEET_CONTRACTS[CheatsheetPattern.WATERMARK_LOOKBACK_CURRENT],
        provider_family=CaptureProviderFamily.DB_QUERY,
    ),
    CapturePattern.WATERMARK_TOMBSTONE: LegacyCapturePatternProjection(
        pattern=CapturePattern.WATERMARK_TOMBSTONE,
        semantics=_CHEATSHEET_CONTRACTS[CheatsheetPattern.WATERMARK_SOFT_DELETE_CURRENT],
        provider_family=CaptureProviderFamily.DB_QUERY,
    ),
    CapturePattern.CDC_NET_CURRENT: LegacyCapturePatternProjection(
        pattern=CapturePattern.CDC_NET_CURRENT,
        semantics=_CHEATSHEET_CONTRACTS[CheatsheetPattern.NET_CHANGES_CURRENT],
        provider_family=CaptureProviderFamily.NATIVE_CDC,
    ),
    CapturePattern.CDC_NET_OBSERVATION: LegacyCapturePatternProjection(
        pattern=CapturePattern.CDC_NET_OBSERVATION,
        semantics=_CHEATSHEET_CONTRACTS[CheatsheetPattern.NET_CHANGES_APPEND],
        provider_family=CaptureProviderFamily.NATIVE_CDC,
    ),
    CapturePattern.CDC_FULL: LegacyCapturePatternProjection(
        pattern=CapturePattern.CDC_FULL,
        semantics=_CHEATSHEET_CONTRACTS[CheatsheetPattern.FULL_CHANGES_EVENT],
        provider_family=CaptureProviderFamily.NATIVE_CDC,
    ),
    CapturePattern.TRANSACTION_LOG_CDC: LegacyCapturePatternProjection(
        pattern=CapturePattern.TRANSACTION_LOG_CDC,
        semantics=_CHEATSHEET_CONTRACTS[CheatsheetPattern.FULL_CHANGES_EVENT].model_copy(
            update={"read_strategy": ReadStrategy.SOURCE_POSITION}
        ),
        provider_family=CaptureProviderFamily.TRANSACTION_LOG,
    ),
    CapturePattern.DEBEZIUM_KAFKA: LegacyCapturePatternProjection(
        pattern=CapturePattern.DEBEZIUM_KAFKA,
        semantics=_CHEATSHEET_CONTRACTS[CheatsheetPattern.FULL_CHANGES_EVENT].model_copy(
            update={
                "read_strategy": ReadStrategy.PARTITION_OFFSET,
                "retry_identity": ("topic", "partition", "offset"),
            }
        ),
        provider_family=CaptureProviderFamily.DEBEZIUM_KAFKA,
    ),
    CapturePattern.DELTA_CDF: LegacyCapturePatternProjection(
        pattern=CapturePattern.DELTA_CDF,
        semantics=_CHEATSHEET_CONTRACTS[CheatsheetPattern.FULL_CHANGES_EVENT].model_copy(
            update={
                "read_strategy": ReadStrategy.COMMIT_VERSION,
                "retry_identity": ("commit_version", "row_event_identity"),
            }
        ),
        provider_family=CaptureProviderFamily.DELTA_CDF,
    ),
    CapturePattern.EVENT_SOURCE: LegacyCapturePatternProjection(
        pattern=CapturePattern.EVENT_SOURCE,
        semantics=_CHEATSHEET_CONTRACTS[CheatsheetPattern.BUSINESS_EVENTS],
        provider_family=CaptureProviderFamily.BUSINESS_EVENT_SOURCE,
    ),
    CapturePattern.SNAPSHOT_DIFF: LegacyCapturePatternProjection(
        pattern=CapturePattern.SNAPSHOT_DIFF,
        semantics=_CHEATSHEET_CONTRACTS[CheatsheetPattern.SNAPSHOT_DIFF_APPEND],
        provider_family=CaptureProviderFamily.DB_QUERY,
    ),
    CapturePattern.API_CURSOR_INCREMENTAL: LegacyCapturePatternProjection(
        pattern=CapturePattern.API_CURSOR_INCREMENTAL,
        semantics=_contract(
            source=SourceSemantics.SOURCE_DEFINED,
            granularity=ChangeGranularity.SOURCE_DEFINED,
            read=ReadStrategy.CURSOR,
            delete=DeleteSemantics.SOURCE_DEFINED,
            bronze=BronzeContract.CURRENT,
            write=BronzeWriteMode.MERGE,
            history=HistoryFidelity.SOURCE_DEFINED,
            retry_identity=("frozen_window", "cursor_chain", "primary_key_or_event_id"),
            guidance="API pagination is transport/progress; payload semantics and fidelity remain source-defined.",
        ),
        provider_family=CaptureProviderFamily.API,
    ),
    CapturePattern.FILE_INCREMENTAL: LegacyCapturePatternProjection(
        pattern=CapturePattern.FILE_INCREMENTAL,
        semantics=_contract(
            source=SourceSemantics.SOURCE_DEFINED,
            granularity=ChangeGranularity.SOURCE_DEFINED,
            read=ReadStrategy.FILE_MANIFEST,
            delete=DeleteSemantics.SOURCE_DEFINED,
            bronze=BronzeContract.RAW_OBSERVATION,
            write=BronzeWriteMode.APPEND,
            history=HistoryFidelity.SOURCE_DEFINED,
            retry_identity=("file_uri", "version_token_or_checksum"),
            guidance="File discovery/delivery does not define row semantics; classify file contents separately.",
        ),
        provider_family=CaptureProviderFamily.FILE,
    ),
}


def project_legacy_capture_pattern(pattern: CapturePattern) -> LegacyCapturePatternProjection:
    """Project an existing combined preset into orthogonal semantics + provider family."""

    return _LEGACY_PROJECTIONS[pattern]


__all__ = [
    "BronzeContract",
    "CaptureProviderFamily",
    "CaptureSemanticContract",
    "ChangeGranularity",
    "CheatsheetPattern",
    "DeleteSemantics",
    "LegacyCapturePatternProjection",
    "ReadStrategy",
    "SourceSemantics",
    "cheatsheet_pattern_catalog",
    "cheatsheet_pattern_contract",
    "project_legacy_capture_pattern",
]
