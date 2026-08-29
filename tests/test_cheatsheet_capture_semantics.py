from fabric_data_framework.capture.patterns import BronzeWriteMode, CapturePattern, HistoryFidelity
from fabric_data_framework.capture.semantic_contracts import (
    BronzeContract,
    CaptureProviderFamily,
    ChangeGranularity,
    CheatsheetPattern,
    DeleteSemantics,
    ReadStrategy,
    SourceSemantics,
    cheatsheet_pattern_catalog,
    cheatsheet_pattern_contract,
    project_legacy_capture_pattern,
)


def test_cheatsheet_acceptance_catalog_has_exactly_fourteen_rows():
    catalog = cheatsheet_pattern_catalog()
    assert len(catalog) == 14
    assert {pattern for pattern, _ in catalog} == set(CheatsheetPattern)


def test_full_snapshot_current_and_snapshot_history_are_distinct_bronze_contracts():
    current = cheatsheet_pattern_contract(CheatsheetPattern.FULL_SNAPSHOT_CURRENT)
    history = cheatsheet_pattern_contract(CheatsheetPattern.FULL_SNAPSHOT_HISTORY)

    assert current.source_semantics is SourceSemantics.CURRENT_STATE
    assert current.change_granularity is ChangeGranularity.SNAPSHOT
    assert current.read_strategy is ReadStrategy.FULL
    assert current.bronze_contract is BronzeContract.CURRENT
    assert current.bronze_write_mode is BronzeWriteMode.OVERWRITE
    assert current.history_fidelity is HistoryFidelity.NONE

    assert history.source_semantics is SourceSemantics.CURRENT_STATE
    assert history.change_granularity is ChangeGranularity.SNAPSHOT
    assert history.read_strategy is ReadStrategy.FULL
    assert history.bronze_contract is BronzeContract.SNAPSHOT_HISTORY
    assert history.bronze_write_mode is BronzeWriteMode.APPEND
    assert history.history_fidelity is HistoryFidelity.SNAPSHOT_GRAIN
    assert history.retry_identity == ("snapshot_id",)


def test_watermark_lookback_current_and_raw_append_are_independent_bronze_choices():
    current = cheatsheet_pattern_contract(CheatsheetPattern.WATERMARK_LOOKBACK_CURRENT)
    raw = cheatsheet_pattern_contract(CheatsheetPattern.WATERMARK_LOOKBACK_RAW)

    assert current.read_strategy is ReadStrategy.WATERMARK_LOOKBACK
    assert raw.read_strategy is ReadStrategy.WATERMARK_LOOKBACK
    assert current.delete_semantics is DeleteSemantics.NONE
    assert raw.delete_semantics is DeleteSemantics.NONE
    assert current.bronze_contract is BronzeContract.CURRENT
    assert current.bronze_write_mode is BronzeWriteMode.MERGE
    assert raw.bronze_contract is BronzeContract.RAW_OBSERVATION
    assert raw.bronze_write_mode is BronzeWriteMode.APPEND
    assert raw.history_fidelity is HistoryFidelity.OBSERVED_CHANGES
    assert "ingestion_run_id" in raw.retry_identity


def test_watermark_lookback_soft_delete_raw_is_first_class_composition():
    contract = cheatsheet_pattern_contract(
        CheatsheetPattern.WATERMARK_LOOKBACK_SOFT_DELETE_RAW
    )

    assert contract.source_semantics is SourceSemantics.CURRENT_STATE
    assert contract.change_granularity is ChangeGranularity.CURRENT
    assert contract.read_strategy is ReadStrategy.WATERMARK_LOOKBACK
    assert contract.delete_semantics is DeleteSemantics.SOFT_DELETE
    assert contract.bronze_contract is BronzeContract.RAW_OBSERVATION
    assert contract.bronze_write_mode is BronzeWriteMode.APPEND
    assert contract.history_fidelity is HistoryFidelity.OBSERVED_CHANGES
    assert "delete_marker" in contract.retry_identity


def test_plain_watermark_does_not_claim_hard_delete_visibility():
    contract = cheatsheet_pattern_contract(CheatsheetPattern.WATERMARK_CURRENT)
    assert contract.delete_semantics is DeleteSemantics.NONE
    assert contract.history_fidelity is HistoryFidelity.OBSERVED_CHANGES


def test_net_changes_current_and_append_keep_batch_grain_fidelity():
    current = cheatsheet_pattern_contract(CheatsheetPattern.NET_CHANGES_CURRENT)
    append = cheatsheet_pattern_contract(CheatsheetPattern.NET_CHANGES_APPEND)

    for contract in (current, append):
        assert contract.source_semantics is SourceSemantics.CHANGE_FEED
        assert contract.change_granularity is ChangeGranularity.NET
        assert contract.history_fidelity is HistoryFidelity.BATCH_GRAIN
        assert contract.delete_semantics is DeleteSemantics.EXPLICIT_EVENT

    assert current.bronze_contract is BronzeContract.CURRENT
    assert current.bronze_write_mode is BronzeWriteMode.MERGE
    assert append.bronze_contract is BronzeContract.RAW_OBSERVATION
    assert append.bronze_write_mode is BronzeWriteMode.APPEND


def test_full_changes_event_and_current_lossy_have_explicitly_different_history_truth():
    event = cheatsheet_pattern_contract(CheatsheetPattern.FULL_CHANGES_EVENT)
    lossy = cheatsheet_pattern_contract(CheatsheetPattern.FULL_CHANGES_CURRENT_LOSSY)

    for contract in (event, lossy):
        assert contract.source_semantics is SourceSemantics.CHANGE_FEED
        assert contract.change_granularity is ChangeGranularity.FULL
        assert contract.delete_semantics is DeleteSemantics.EXPLICIT_EVENT

    assert event.bronze_contract is BronzeContract.EVENT
    assert event.bronze_write_mode is BronzeWriteMode.APPEND
    assert event.history_fidelity is HistoryFidelity.FULL_EVENT
    assert event.intentionally_lossy is False

    assert lossy.bronze_contract is BronzeContract.CURRENT
    assert lossy.bronze_write_mode is BronzeWriteMode.MERGE
    assert lossy.history_fidelity is HistoryFidelity.NONE
    assert lossy.intentionally_lossy is True


def test_business_events_remain_distinct_from_database_change_feed():
    contract = cheatsheet_pattern_contract(CheatsheetPattern.BUSINESS_EVENTS)
    assert contract.source_semantics is SourceSemantics.BUSINESS_EVENT
    assert contract.change_granularity is ChangeGranularity.EVENT
    assert contract.bronze_contract is BronzeContract.EVENT
    assert contract.delete_semantics is DeleteSemantics.SOURCE_DEFINED
    assert contract.history_fidelity is HistoryFidelity.FULL_EVENT


def test_snapshot_diff_current_and_append_remain_snapshot_grain_only():
    current = cheatsheet_pattern_contract(CheatsheetPattern.SNAPSHOT_DIFF_CURRENT)
    append = cheatsheet_pattern_contract(CheatsheetPattern.SNAPSHOT_DIFF_APPEND)

    for contract in (current, append):
        assert contract.source_semantics is SourceSemantics.CURRENT_STATE
        assert contract.change_granularity is ChangeGranularity.SNAPSHOT
        assert contract.delete_semantics is DeleteSemantics.SNAPSHOT_ABSENCE
        assert contract.history_fidelity is HistoryFidelity.SNAPSHOT_GRAIN

    assert current.bronze_contract is BronzeContract.CURRENT
    assert current.bronze_write_mode is BronzeWriteMode.MERGE
    assert append.bronze_contract is BronzeContract.EVENT
    assert append.bronze_write_mode is BronzeWriteMode.APPEND


def test_every_legacy_capture_pattern_projects_without_changing_legacy_enum():
    projections = {pattern: project_legacy_capture_pattern(pattern) for pattern in CapturePattern}
    assert set(projections) == set(CapturePattern)
    assert all(item.pattern is pattern for pattern, item in projections.items())


def test_legacy_provider_names_project_provider_separately_from_semantics():
    debezium = project_legacy_capture_pattern(CapturePattern.DEBEZIUM_KAFKA)
    delta = project_legacy_capture_pattern(CapturePattern.DELTA_CDF)
    api = project_legacy_capture_pattern(CapturePattern.API_CURSOR_INCREMENTAL)
    files = project_legacy_capture_pattern(CapturePattern.FILE_INCREMENTAL)

    assert debezium.provider_family is CaptureProviderFamily.DEBEZIUM_KAFKA
    assert debezium.semantics.source_semantics is SourceSemantics.CHANGE_FEED
    assert debezium.semantics.change_granularity is ChangeGranularity.FULL
    assert debezium.semantics.read_strategy is ReadStrategy.PARTITION_OFFSET

    assert delta.provider_family is CaptureProviderFamily.DELTA_CDF
    assert delta.semantics.source_semantics is SourceSemantics.CHANGE_FEED
    assert delta.semantics.read_strategy is ReadStrategy.COMMIT_VERSION

    assert api.provider_family is CaptureProviderFamily.API
    assert api.semantics.source_semantics is SourceSemantics.SOURCE_DEFINED
    assert api.semantics.read_strategy is ReadStrategy.CURSOR

    assert files.provider_family is CaptureProviderFamily.FILE
    assert files.semantics.source_semantics is SourceSemantics.SOURCE_DEFINED
    assert files.semantics.read_strategy is ReadStrategy.FILE_MANIFEST


def test_provider_projection_does_not_upgrade_source_fidelity():
    debezium = project_legacy_capture_pattern(CapturePattern.DEBEZIUM_KAFKA)
    api = project_legacy_capture_pattern(CapturePattern.API_CURSOR_INCREMENTAL)

    assert debezium.semantics.history_fidelity is HistoryFidelity.FULL_EVENT
    assert api.semantics.history_fidelity is HistoryFidelity.SOURCE_DEFINED
