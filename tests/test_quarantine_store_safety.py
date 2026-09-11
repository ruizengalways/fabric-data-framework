from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import json
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from fabric_data_framework.contracts.replay import QuarantineBatchEvidence
from fabric_data_framework.data_plane.bronze import BronzeRecord
from fabric_data_framework.quality.quarantine_store import (
    JsonFileQuarantineStore,
    QuarantinePayloadError,
)
from fabric_data_framework.quality.rules import QuarantinedRecord


NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


def _quarantined(dataset_run_id, *, marker: str = "first") -> QuarantinedRecord:
    return QuarantinedRecord(
        record=BronzeRecord(
            data={
                "marker": marker,
                "when": NOW,
                "amount": Decimal("1.25"),
                "identifier": UUID("12345678-1234-5678-1234-567812345678"),
                "nested": {"values": (1, True, None)},
            },
            ingested_at=NOW,
            run_id=uuid4(),
            dataset_run_id=dataset_run_id,
            source_system="crm",
            source_object="customer",
            source_commit_ts=NOW,
        ),
        reason_codes=("BAD_ROW",),
        reason_messages=("bad row",),
    )


def _evidence(quarantine_id, dataset_run_id, source_reference) -> QuarantineBatchEvidence:
    return QuarantineBatchEvidence(
        quarantine_id=quarantine_id,
        dataset_run_id=dataset_run_id,
        dataset_id="crm.customer",
        scope="ROW",
        row_count=1,
        reason_code="BAD_ROW",
        source_reference=source_reference,
        created_at=NOW,
    )


def test_quarantine_payload_round_trip_preserves_business_types_and_identity(tmp_path):
    store = JsonFileQuarantineStore(tmp_path)
    quarantine_id = uuid4()
    dataset_run_id = uuid4()
    reference = store.write_payload(
        quarantine_id=quarantine_id,
        dataset_run_id=dataset_run_id,
        dataset_id="crm.customer",
        rows=(_quarantined(dataset_run_id),),
    )

    replay = store.load_payload(_evidence(quarantine_id, dataset_run_id, reference))
    row = replay.rows[0]

    assert replay.payload_version == "2"
    assert row["when"] == NOW
    assert isinstance(row["when"], datetime)
    assert row["amount"] == Decimal("1.25")
    assert isinstance(row["amount"], Decimal)
    assert row["identifier"] == UUID("12345678-1234-5678-1234-567812345678")
    assert isinstance(row["identifier"], UUID)
    assert row["nested"]["values"] == (1, True, None)


def test_quarantine_payload_hash_and_dataset_run_identity_fail_closed(tmp_path):
    store = JsonFileQuarantineStore(tmp_path)
    quarantine_id = uuid4()
    dataset_run_id = uuid4()
    reference = store.write_payload(
        quarantine_id=quarantine_id,
        dataset_run_id=dataset_run_id,
        dataset_id="crm.customer",
        rows=(_quarantined(dataset_run_id),),
    )
    path = store._path(quarantine_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["dataset_id"] = "tampered.dataset"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(QuarantinePayloadError, match="content hash mismatch"):
        store.load_payload(_evidence(quarantine_id, dataset_run_id, reference))


def test_concurrent_quarantine_writers_cannot_overwrite_existing_payload(tmp_path):
    store = JsonFileQuarantineStore(tmp_path)
    quarantine_id = uuid4()
    dataset_run_id = uuid4()
    barrier = Barrier(2)

    def writer(marker: str):
        barrier.wait()
        try:
            reference = store.write_payload(
                quarantine_id=quarantine_id,
                dataset_run_id=dataset_run_id,
                dataset_id="crm.customer",
                rows=(_quarantined(dataset_run_id, marker=marker),),
            )
            return ("ok", marker, reference)
        except QuarantinePayloadError as exc:
            return ("error", marker, str(exc))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(writer, ("first", "second")))

    assert [item[0] for item in results].count("ok") == 1
    assert [item[0] for item in results].count("error") == 1
    winner = next(item for item in results if item[0] == "ok")
    replay = store.load_payload(_evidence(quarantine_id, dataset_run_id, winner[2]))
    assert replay.rows[0]["marker"] == winner[1]
    assert not list(tmp_path.glob("*.tmp"))


def test_quarantine_store_rejects_unsupported_business_value_type(tmp_path):
    store = JsonFileQuarantineStore(tmp_path)
    quarantine_id = uuid4()
    dataset_run_id = uuid4()
    record = _quarantined(dataset_run_id)
    bad = record.model_copy(
        update={"record": record.record.model_copy(update={"data": {"bad": object()}})}
    )

    with pytest.raises(QuarantinePayloadError, match="unsupported business value type"):
        store.write_payload(
            quarantine_id=quarantine_id,
            dataset_run_id=dataset_run_id,
            dataset_id="crm.customer",
            rows=(bad,),
        )
