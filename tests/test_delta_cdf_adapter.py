from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from fabric_data_framework.adapters.cdc.delta_cdf import (
    DeltaCDFAdapterError,
    DeltaCDFChangeType,
    DeltaCDFRecord,
    normalize_delta_cdf_batch,
)
from fabric_data_framework.capture.cdc import CDCOperation


TS = datetime(2026, 8, 29, 5, tzinfo=timezone.utc)


def _record(change_type, version, row):
    return DeltaCDFRecord(
        change_type=change_type,
        commit_version=version,
        commit_timestamp=TS,
        data=row,
    )


def test_delta_cdf_requires_timezone_aware_commit_timestamp():
    with pytest.raises(ValidationError, match="timezone-aware"):
        DeltaCDFRecord(
            change_type=DeltaCDFChangeType.INSERT,
            commit_version=1,
            commit_timestamp=datetime(2026, 8, 29, 5),
            data={"id": 1},
        )


def test_delta_cdf_insert_delete_and_update_pair_normalize_to_canonical_events():
    result = normalize_delta_cdf_batch(
        [
            _record(DeltaCDFChangeType.INSERT, 10, {"id": 1, "name": "A"}),
            _record(DeltaCDFChangeType.UPDATE_PREIMAGE, 11, {"id": 1, "name": "A"}),
            _record(DeltaCDFChangeType.UPDATE_POSTIMAGE, 11, {"id": 1, "name": "B"}),
            _record(DeltaCDFChangeType.DELETE, 12, {"id": 1, "name": "B"}),
        ],
        table_reference="lh.bronze.customer",
        key_columns=("id",),
        upper_commit_version=12,
        complete_through_upper=True,
    )

    events = result.normalized_batch.events
    assert [event.operation for event in events] == [
        CDCOperation.INSERT,
        CDCOperation.UPDATE,
        CDCOperation.DELETE,
    ]
    assert events[1].before == {"id": 1, "name": "A"}
    assert events[1].after == {"id": 1, "name": "B"}
    assert result.update_pairs == 1
    assert result.logical_events == 3


def test_delta_cdf_position_is_commit_version_plus_deterministic_row_sequence():
    result = normalize_delta_cdf_batch(
        [
            _record(DeltaCDFChangeType.INSERT, 20, {"id": 2, "name": "B"}),
            _record(DeltaCDFChangeType.INSERT, 20, {"id": 1, "name": "A"}),
        ],
        table_reference="table",
        key_columns=("id",),
        upper_commit_version=20,
        complete_through_upper=True,
    )

    events = result.normalized_batch.events
    assert [event.key["id"] for event in events] == [1, 2]
    assert [event.position.values for event in events] == [(20, 0), (20, 1)]
    assert all(
        event.metadata["within_commit_order"]
        == "deterministic_key_order_not_source_temporal_order"
        for event in events
    )


def test_delta_cdf_exact_input_duplicate_is_idempotently_ignored():
    record = _record(DeltaCDFChangeType.INSERT, 10, {"id": 1, "name": "A"})
    result = normalize_delta_cdf_batch(
        [record, record],
        table_reference="table",
        key_columns=("id",),
        upper_commit_version=10,
        complete_through_upper=True,
    )
    assert result.duplicate_records_ignored == 1
    assert result.logical_events == 1


def test_delta_cdf_ambiguous_multiple_same_key_mutations_in_one_commit_fail_closed():
    with pytest.raises(DeltaCDFAdapterError, match="ambiguous set of change records"):
        normalize_delta_cdf_batch(
            [
                _record(DeltaCDFChangeType.INSERT, 10, {"id": 1, "name": "A"}),
                _record(DeltaCDFChangeType.DELETE, 10, {"id": 1, "name": "A"}),
            ],
            table_reference="table",
            key_columns=("id",),
            upper_commit_version=10,
            complete_through_upper=True,
        )


def test_delta_cdf_missing_update_pair_fails_closed():
    with pytest.raises(DeltaCDFAdapterError, match="ambiguous set of change records"):
        normalize_delta_cdf_batch(
            [_record(DeltaCDFChangeType.UPDATE_POSTIMAGE, 10, {"id": 1, "name": "B"})],
            table_reference="table",
            key_columns=("id",),
            upper_commit_version=10,
            complete_through_upper=True,
        )


def test_delta_cdf_same_type_conflict_for_same_key_commit_fails_closed():
    with pytest.raises(DeltaCDFAdapterError, match="more than one non-identical record"):
        normalize_delta_cdf_batch(
            [
                _record(DeltaCDFChangeType.INSERT, 10, {"id": 1, "name": "A"}),
                _record(DeltaCDFChangeType.INSERT, 10, {"id": 1, "name": "B"}),
            ],
            table_reference="table",
            key_columns=("id",),
            upper_commit_version=10,
            complete_through_upper=True,
        )


def test_delta_cdf_key_must_be_present_and_non_null():
    with pytest.raises(DeltaCDFAdapterError, match="cannot be null/missing"):
        normalize_delta_cdf_batch(
            [_record(DeltaCDFChangeType.INSERT, 10, {"id": None, "name": "A"})],
            table_reference="table",
            key_columns=("id",),
            upper_commit_version=10,
            complete_through_upper=True,
        )


def test_delta_cdf_record_beyond_frozen_upper_fails():
    with pytest.raises(DeltaCDFAdapterError, match="exceeds frozen upper"):
        normalize_delta_cdf_batch(
            [_record(DeltaCDFChangeType.INSERT, 11, {"id": 1})],
            table_reference="table",
            key_columns=("id",),
            upper_commit_version=10,
            complete_through_upper=True,
        )


def test_delta_cdf_lower_committed_version_makes_overlap_idempotent():
    result = normalize_delta_cdf_batch(
        [
            _record(DeltaCDFChangeType.INSERT, 10, {"id": 1}),
            _record(DeltaCDFChangeType.INSERT, 11, {"id": 2}),
        ],
        table_reference="table",
        key_columns=("id",),
        lower_committed_version=10,
        upper_commit_version=11,
        complete_through_upper=True,
    )
    assert [event.key["id"] for event in result.normalized_batch.events] == [2]
    assert result.normalized_batch.already_committed_events_ignored == 1


def test_delta_cdf_requires_completeness_evidence():
    with pytest.raises(Exception, match="completeness evidence"):
        normalize_delta_cdf_batch(
            [_record(DeltaCDFChangeType.INSERT, 10, {"id": 1})],
            table_reference="table",
            key_columns=("id",),
            upper_commit_version=10,
            complete_through_upper=False,
        )


def test_delta_cdf_lower_version_cannot_exceed_upper():
    with pytest.raises(DeltaCDFAdapterError, match="cannot exceed"):
        normalize_delta_cdf_batch(
            [],
            table_reference="table",
            key_columns=("id",),
            lower_committed_version=11,
            upper_commit_version=10,
            complete_through_upper=True,
        )
