from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from fabric_data_framework.adapters.cdc import (
    DeltaCDFAdapterError,
    DeltaCDFRetentionGapError,
    KafkaCursorRelation,
    plan_debezium_kafka_cursor_coordination,
    plan_delta_cdf_resume,
)
from fabric_data_framework.capture.cdc import build_cdc_checkpoint
from fabric_data_framework.control_plane.schema import apply_baseline_schema, dataset
from fabric_data_framework.contracts.recovery import UnknownOutcomeResolution
from fabric_data_framework.recovery.target_probe import (
    TargetCommitProbeEvidence,
    probe_and_reconcile_target_operation,
)
from fabric_data_framework.control_plane.target_operation_journal import (
    claim_target_operation,
    mark_target_operation_unknown,
)
from fabric_data_framework.contracts.target_operation import (
    TargetOperationAction,
    TargetOperationIntent,
    TargetOperationStatus,
    fingerprint_semantic_payload,
)


TOPIC = "dbserver1.inventory.customers"


def test_kafka_cursor_is_rewound_or_advanced_to_framework_checkpoint_not_trusted():
    committed = build_cdc_checkpoint(
        {
            f"{TOPIC}:0": (100,),
            f"{TOPIC}:1": (50,),
            f"{TOPIC}:2": (7,),
        }
    )
    plan = plan_debezium_kafka_cursor_coordination(
        topic=TOPIC,
        committed_checkpoint=committed,
        earliest_offsets={0: 90, 1: 40, 2: 0},
        latest_offsets={0: 120, 1: 70, 2: 10},
        consumer_group_next_offsets={
            0: 110,
            1: 45,
            2: 8,
        },
    )

    assert [item.relation for item in plan.alignments] == [
        KafkaCursorRelation.AHEAD,
        KafkaCursorRelation.BEHIND,
        KafkaCursorRelation.ALIGNED,
    ]
    assert plan.seek_offsets == {0: 101, 1: 51}
    assert plan.commit_next_offsets_after_downstream_success == {
        0: 121,
        1: 71,
        2: 11,
    }
    assert plan.resume.upper_checkpoint.position_for(f"{TOPIC}:0") == (120,)


def test_kafka_missing_group_cursor_is_initialized_from_framework_semantics():
    committed = build_cdc_checkpoint({f"{TOPIC}:0": (100,)})
    plan = plan_debezium_kafka_cursor_coordination(
        topic=TOPIC,
        committed_checkpoint=committed,
        earliest_offsets={0: 90},
        latest_offsets={0: 105},
        consumer_group_next_offsets={},
    )

    assert plan.alignments[0].relation is KafkaCursorRelation.MISSING
    assert plan.seek_offsets == {0: 101}


def test_delta_cdf_resume_detects_retention_gap_before_reading():
    with pytest.raises(DeltaCDFRetentionGapError, match="next_required=101"):
        plan_delta_cdf_resume(
            table_reference="lakehouse.customer",
            lower_committed_version=100,
            earliest_available_version=102,
            latest_available_version=120,
        )


def test_delta_cdf_resume_allows_exact_next_version_and_freezes_upper():
    plan = plan_delta_cdf_resume(
        table_reference="lakehouse.customer",
        lower_committed_version=100,
        earliest_available_version=101,
        latest_available_version=120,
        requested_upper_version=110,
    )

    assert plan.start_version == 101
    assert plan.upper_version == 110
    assert plan.has_work is True
    assert plan.lower_checkpoint.position_for("delta-cdf:lakehouse.customer")[0] == 100
    assert plan.upper_checkpoint.position_for("delta-cdf:lakehouse.customer")[0] == 110

    with pytest.raises(DeltaCDFAdapterError, match="exceeds provider latest"):
        plan_delta_cdf_resume(
            table_reference="lakehouse.customer",
            lower_committed_version=100,
            earliest_available_version=101,
            latest_available_version=120,
            requested_upper_version=121,
        )


def _operation_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    apply_baseline_schema(engine)
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            dataset.insert().values(
                dataset_id="crm.customer",
                domain="crm",
                source_system="dynamics",
                source_object="account",
                target_layer="silver",
                target_object="customer",
                enabled_default=True,
                criticality="HIGH",
                execution_group="crm",
                config_schema_version=1,
                config_hash="a" * 64,
                domain_git_sha="b" * 40,
                framework_version="0.4.0",
                created_at=now,
                updated_at=None,
            )
        )
    return engine


def _claim_ambiguous_operation(engine):
    intent = TargetOperationIntent(
        dataset_id="crm.customer",
        operation_kind="SCD2",
        target_reference="silver.customer",
        effective_config_hash="c" * 64,
        input_fingerprint=fingerprint_semantic_payload(
            {"capture_receipt": "receipt-99", "upper": 120}
        ),
    )
    run_id = uuid4()
    claim = claim_target_operation(
        engine,
        intent=intent,
        dataset_run_id=run_id,
        attempt=1,
    )
    assert claim.action is TargetOperationAction.EXECUTE
    unknown = mark_target_operation_unknown(
        engine,
        operation_key=intent.operation_key,
        expected_version=claim.record.version,
        dataset_run_id=run_id,
        attempt=1,
        error_message="target request timed out",
    )
    return intent, unknown


class _CommittedProbe:
    def probe(self, request):
        assert request.current_status is TargetOperationStatus.UNKNOWN
        return TargetCommitProbeEvidence(
            provider="fabric_warehouse",
            resolution=UnknownOutcomeResolution.COMMITTED,
            native_operation_id="statement-123",
            evidence_reference="warehouse-history:statement-123:committed",
        )


class _NotCommittedProbe:
    def probe(self, request):
        return TargetCommitProbeEvidence(
            provider="fabric_warehouse",
            resolution=UnknownOutcomeResolution.NOT_COMMITTED,
            evidence_reference="warehouse-history:statement-123:not-found",
        )


class _BrokenProbe:
    def probe(self, request):
        raise TimeoutError("provider history API unavailable password=should-not-persist")


def test_target_native_probe_committed_converges_operation_to_success():
    engine = _operation_engine()
    intent, unknown = _claim_ambiguous_operation(engine)
    retry_run = uuid4()

    result = probe_and_reconcile_target_operation(
        engine,
        operation_key=intent.operation_key,
        dataset_run_id=retry_run,
        attempt=2,
        probe=_CommittedProbe(),
    )

    assert unknown.status is TargetOperationStatus.UNKNOWN
    assert result.evidence.resolution is UnknownOutcomeResolution.COMMITTED
    assert result.record.status is TargetOperationStatus.SUCCEEDED
    assert result.record.outcome_reference == "warehouse-history:statement-123:committed"


def test_target_native_probe_not_committed_reopens_only_next_claim():
    engine = _operation_engine()
    intent, _ = _claim_ambiguous_operation(engine)
    retry_run = uuid4()

    result = probe_and_reconcile_target_operation(
        engine,
        operation_key=intent.operation_key,
        dataset_run_id=retry_run,
        attempt=2,
        probe=_NotCommittedProbe(),
    )
    assert result.record.status is TargetOperationStatus.NOT_COMMITTED

    next_claim = claim_target_operation(
        engine,
        intent=intent,
        dataset_run_id=retry_run,
        attempt=2,
    )
    assert next_claim.action is TargetOperationAction.EXECUTE
    assert next_claim.record.status is TargetOperationStatus.IN_PROGRESS


def test_target_native_probe_exception_is_secret_safe_unresolved_and_blocks_retry():
    engine = _operation_engine()
    intent, _ = _claim_ambiguous_operation(engine)
    retry_run = uuid4()

    result = probe_and_reconcile_target_operation(
        engine,
        operation_key=intent.operation_key,
        dataset_run_id=retry_run,
        attempt=2,
        probe=_BrokenProbe(),
    )

    assert result.evidence.resolution is UnknownOutcomeResolution.UNRESOLVED
    assert result.record.status is TargetOperationStatus.UNKNOWN
    message = result.record.error_message or ""
    assert message == "target commit probe raised TimeoutError"
    assert "provider history API unavailable" not in message
    assert "should-not-persist" not in message
    assert "password=" not in message.lower()

    blocked = claim_target_operation(
        engine,
        intent=intent,
        dataset_run_id=uuid4(),
        attempt=3,
    )
    assert blocked.action is TargetOperationAction.RECONCILE_REQUIRED
