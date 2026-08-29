"""Frozen API capture-window and pagination guardrails."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ..config import FrozenModel, canonical_hash


class APICaptureError(ValueError):
    pass


class APICaptureWindow(FrozenModel):
    """Immutable logical source window reused across retries/replays."""

    window_id: str = Field(min_length=1)
    lower_bound: Any | None = None
    upper_bound: Any | None = None
    predicate_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def window_fingerprint(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class APIPageEvidence(FrozenModel):
    page_number: int = Field(ge=1)
    request_cursor: str | None = None
    next_cursor: str | None = None
    records_count: int = Field(ge=0)
    response_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class APIPaginationPolicy(FrozenModel):
    max_pages: int = Field(default=10_000, gt=0)
    max_records: int = Field(default=10_000_000, gt=0)
    allow_empty_result: bool = True
    require_terminal_cursor: bool = True


class APICaptureEvidence(FrozenModel):
    window: APICaptureWindow
    initial_cursor: str | None = None
    pages: tuple[APIPageEvidence, ...]
    complete: bool
    total_records: int = Field(ge=0)

    @property
    def evidence_fingerprint(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


def freeze_api_window(
    *,
    window_id: str,
    lower_bound: Any | None,
    upper_bound: Any | None,
    predicate: Any,
) -> APICaptureWindow:
    """Freeze source bounds plus query/filter semantics before the first request."""

    return APICaptureWindow(
        window_id=window_id,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        predicate_hash=canonical_hash(predicate),
    )


def validate_api_capture(
    *,
    window: APICaptureWindow,
    pages: tuple[APIPageEvidence, ...],
    complete: bool,
    total_records: int,
    initial_cursor: str | None = None,
    policy: APIPaginationPolicy | None = None,
) -> APICaptureEvidence:
    """Validate a complete replay-stable cursor chain within explicit safety bounds."""

    effective = policy or APIPaginationPolicy()
    if not complete:
        raise APICaptureError("API capture is not proven complete through the frozen window")
    if len(pages) > effective.max_pages:
        raise APICaptureError(
            f"API capture used {len(pages)} pages; max_pages={effective.max_pages}"
        )
    if total_records > effective.max_records:
        raise APICaptureError(
            f"API capture returned {total_records} records; max_records={effective.max_records}"
        )
    if not pages:
        if total_records != 0:
            raise APICaptureError("API total_records must be zero when no pages were captured")
        if not effective.allow_empty_result:
            raise APICaptureError("empty API result is not authorized")
        return APICaptureEvidence(
            window=window,
            initial_cursor=initial_cursor,
            pages=(),
            complete=True,
            total_records=0,
        )

    expected_page = 1
    expected_cursor = initial_cursor
    seen_request_cursors: set[str] = set()
    seen_next_cursors: set[str] = set()
    counted = 0

    for page in pages:
        if page.page_number != expected_page:
            raise APICaptureError(
                f"API page numbers must be contiguous from 1; expected {expected_page}, "
                f"observed {page.page_number}"
            )
        if page.request_cursor != expected_cursor:
            raise APICaptureError(
                f"API cursor chain broke at page {page.page_number}: expected request cursor "
                f"{expected_cursor!r}, observed {page.request_cursor!r}"
            )
        if page.request_cursor is not None:
            if page.request_cursor in seen_request_cursors:
                raise APICaptureError(
                    f"API request cursor cycle detected: {page.request_cursor!r}"
                )
            seen_request_cursors.add(page.request_cursor)
        if page.next_cursor is not None:
            if page.next_cursor == page.request_cursor or page.next_cursor in seen_request_cursors:
                raise APICaptureError(
                    f"API pagination cursor cycle detected at page {page.page_number}: "
                    f"{page.next_cursor!r}"
                )
            if page.next_cursor in seen_next_cursors:
                raise APICaptureError(
                    f"API next cursor repeated before completion: {page.next_cursor!r}"
                )
            seen_next_cursors.add(page.next_cursor)
        counted += page.records_count
        if counted > effective.max_records:
            raise APICaptureError(
                f"API capture exceeded max_records={effective.max_records} while paginating"
            )
        expected_cursor = page.next_cursor
        expected_page += 1

    if counted != total_records:
        raise APICaptureError(
            f"API row accounting mismatch: page total={counted}, declared total={total_records}"
        )
    if effective.require_terminal_cursor and pages[-1].next_cursor is not None:
        raise APICaptureError(
            "API capture marked complete but final page still has a next cursor"
        )

    return APICaptureEvidence(
        window=window,
        initial_cursor=initial_cursor,
        pages=pages,
        complete=True,
        total_records=total_records,
    )


def assert_same_api_window(expected: APICaptureWindow, observed: APICaptureWindow) -> None:
    if expected.window_fingerprint != observed.window_fingerprint:
        raise APICaptureError(
            "API retry/replay window changed; reuse the original frozen bounds/predicate"
        )


__all__ = [
    "APICaptureError",
    "APICaptureEvidence",
    "APICaptureWindow",
    "APIPageEvidence",
    "APIPaginationPolicy",
    "assert_same_api_window",
    "freeze_api_window",
    "validate_api_capture",
]
