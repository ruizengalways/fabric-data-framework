import pytest

from fabric_data_framework.capture.api import (
    APICaptureError,
    APIPageEvidence,
    APIPaginationPolicy,
    assert_same_api_window,
    freeze_api_window,
    validate_api_capture,
)
from fabric_data_framework.config import canonical_hash


def _page(
    number: int,
    request_cursor: str | None,
    next_cursor: str | None,
    count: int,
) -> APIPageEvidence:
    return APIPageEvidence(
        page_number=number,
        request_cursor=request_cursor,
        next_cursor=next_cursor,
        records_count=count,
        response_fingerprint=canonical_hash(
            {"page": number, "request": request_cursor, "next": next_cursor, "count": count}
        ),
    )


def _window():
    return freeze_api_window(
        window_id="orders-2026-08-29T00:00Z",
        lower_bound="2026-08-28T00:00:00Z",
        upper_bound="2026-08-29T00:00:00Z",
        predicate={"status": ["OPEN", "CLOSED"], "sort": ["updated_at", "id"]},
    )


def test_api_window_fingerprint_is_stable_for_same_bounds_and_predicate():
    first = _window()
    second = freeze_api_window(
        window_id="orders-2026-08-29T00:00Z",
        lower_bound="2026-08-28T00:00:00Z",
        upper_bound="2026-08-29T00:00:00Z",
        predicate={"sort": ["updated_at", "id"], "status": ["OPEN", "CLOSED"]},
    )
    assert first.window_fingerprint == second.window_fingerprint
    assert_same_api_window(first, second)


def test_api_window_drift_on_retry_is_rejected():
    original = _window()
    shifted = freeze_api_window(
        window_id="orders-2026-08-29T00:00Z",
        lower_bound="2026-08-28T00:00:00Z",
        upper_bound="2026-08-29T01:00:00Z",
        predicate={"status": ["OPEN", "CLOSED"], "sort": ["updated_at", "id"]},
    )
    with pytest.raises(APICaptureError, match="window changed"):
        assert_same_api_window(original, shifted)


def test_api_cursor_chain_and_row_accounting_succeed():
    evidence = validate_api_capture(
        window=_window(),
        pages=(
            _page(1, None, "c1", 2),
            _page(2, "c1", "c2", 2),
            _page(3, "c2", None, 1),
        ),
        complete=True,
        total_records=5,
    )
    assert evidence.total_records == 5
    assert evidence.complete is True
    assert len(evidence.pages) == 3


def test_api_capture_requires_explicit_completeness():
    with pytest.raises(APICaptureError, match="not proven complete"):
        validate_api_capture(
            window=_window(),
            pages=(_page(1, None, None, 1),),
            complete=False,
            total_records=1,
        )


def test_api_page_numbers_must_be_contiguous():
    with pytest.raises(APICaptureError, match="contiguous"):
        validate_api_capture(
            window=_window(),
            pages=(
                _page(1, None, "c1", 1),
                _page(3, "c1", None, 1),
            ),
            complete=True,
            total_records=2,
        )


def test_api_cursor_chain_mismatch_fails_closed():
    with pytest.raises(APICaptureError, match="cursor chain broke"):
        validate_api_capture(
            window=_window(),
            pages=(
                _page(1, None, "c1", 1),
                _page(2, "wrong", None, 1),
            ),
            complete=True,
            total_records=2,
        )


def test_api_cursor_cycle_is_detected():
    with pytest.raises(APICaptureError, match="cycle"):
        validate_api_capture(
            window=_window(),
            pages=(
                _page(1, None, "c1", 1),
                _page(2, "c1", "c1", 1),
            ),
            complete=True,
            total_records=2,
        )


def test_api_complete_capture_requires_terminal_cursor():
    with pytest.raises(APICaptureError, match="final page still has a next cursor"):
        validate_api_capture(
            window=_window(),
            pages=(_page(1, None, "c1", 1),),
            complete=True,
            total_records=1,
        )


def test_api_page_and_record_limits_are_guarded():
    with pytest.raises(APICaptureError, match="max_pages=1"):
        validate_api_capture(
            window=_window(),
            pages=(
                _page(1, None, "c1", 1),
                _page(2, "c1", None, 1),
            ),
            complete=True,
            total_records=2,
            policy=APIPaginationPolicy(max_pages=1),
        )

    with pytest.raises(APICaptureError, match="max_records=1"):
        validate_api_capture(
            window=_window(),
            pages=(_page(1, None, None, 2),),
            complete=True,
            total_records=2,
            policy=APIPaginationPolicy(max_records=1),
        )


def test_api_declared_total_must_match_page_counts():
    with pytest.raises(APICaptureError, match="row accounting mismatch"):
        validate_api_capture(
            window=_window(),
            pages=(_page(1, None, None, 2),),
            complete=True,
            total_records=3,
        )


def test_api_empty_result_is_explicitly_policy_controlled():
    evidence = validate_api_capture(
        window=_window(),
        pages=(),
        complete=True,
        total_records=0,
    )
    assert evidence.pages == ()

    with pytest.raises(APICaptureError, match="empty API result"):
        validate_api_capture(
            window=_window(),
            pages=(),
            complete=True,
            total_records=0,
            policy=APIPaginationPolicy(allow_empty_result=False),
        )


def test_api_initial_cursor_is_part_of_chain_evidence():
    evidence = validate_api_capture(
        window=_window(),
        initial_cursor="resume-42",
        pages=(_page(1, "resume-42", None, 1),),
        complete=True,
        total_records=1,
    )
    assert evidence.initial_cursor == "resume-42"
