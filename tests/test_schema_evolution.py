from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select

from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.control_plane.schema import dataset_contract, schema_change
from fabric_data_framework.control_plane.schema_evidence import record_schema_change
from fabric_data_framework.deployment.delivery import materialize_semantic_metadata
from fabric_data_framework.quality import (
    SchemaChangeKind,
    SchemaEvolutionClassification,
    classify_schema_evolution,
    require_compatible_schema,
)
from fabric_data_framework.contracts.schema import (
    LogicalType,
    SchemaCompatibilityPolicy,
    SchemaContract,
    SchemaField,
    SchemaShape,
)


def _field(
    name: str,
    logical_type: LogicalType,
    *,
    nullable: bool = True,
    precision: int | None = None,
    scale: int | None = None,
    max_length: int | None = None,
) -> SchemaField:
    return SchemaField(
        name=name,
        logical_type=logical_type,
        nullable=nullable,
        precision=precision,
        scale=scale,
        max_length=max_length,
    )


def _contract(
    policy: SchemaCompatibilityPolicy,
    *fields: SchemaField,
    version: int = 1,
) -> SchemaContract:
    return SchemaContract(
        contract_version=version,
        compatibility_policy=policy,
        fields=fields,
    )


def test_schema_field_type_parameters_are_strict():
    with pytest.raises(ValidationError, match="DECIMAL requires"):
        _field("amount", LogicalType.DECIMAL)
    with pytest.raises(ValidationError, match="scale cannot exceed"):
        _field("amount", LogicalType.DECIMAL, precision=5, scale=6)
    with pytest.raises(ValidationError, match="only valid for DECIMAL"):
        _field("id", LogicalType.INT64, precision=10)
    with pytest.raises(ValidationError, match="only valid for STRING"):
        _field("id", LogicalType.INT64, max_length=10)


def test_schema_fingerprint_is_independent_of_field_order():
    a = SchemaShape(
        fields=(
            _field("id", LogicalType.INT64, nullable=False),
            _field("name", LogicalType.STRING, max_length=100),
        )
    )
    b = SchemaShape(fields=tuple(reversed(a.fields)))
    assert a.fingerprint == b.fingerprint


def test_exact_policy_allows_only_no_change():
    expected = _contract(
        SchemaCompatibilityPolicy.EXACT,
        _field("id", LogicalType.INT64, nullable=False),
    )
    same = SchemaShape(fields=expected.fields)
    changed = SchemaShape(
        fields=expected.fields + (_field("note", LogicalType.STRING),)
    )

    assert classify_schema_evolution(expected, same).classification is (
        SchemaEvolutionClassification.NO_CHANGE
    )
    decision = classify_schema_evolution(expected, changed)
    assert decision.classification is SchemaEvolutionClassification.BREAKING


def test_additive_only_allows_nullable_addition_but_not_required_addition():
    expected = _contract(
        SchemaCompatibilityPolicy.ADDITIVE_ONLY,
        _field("id", LogicalType.INT64, nullable=False),
    )
    nullable_add = SchemaShape(
        fields=expected.fields + (_field("note", LogicalType.STRING),)
    )
    required_add = SchemaShape(
        fields=expected.fields + (_field("code", LogicalType.STRING, nullable=False),)
    )

    allowed = classify_schema_evolution(expected, nullable_add)
    blocked = classify_schema_evolution(expected, required_add)
    assert allowed.classification is SchemaEvolutionClassification.COMPATIBLE
    assert allowed.changes[0].kind is SchemaChangeKind.FIELD_ADDED
    assert blocked.classification is SchemaEvolutionClassification.BREAKING


def test_additive_only_does_not_silently_allow_type_widening():
    expected = _contract(
        SchemaCompatibilityPolicy.ADDITIVE_ONLY,
        _field("count", LogicalType.INT32),
    )
    observed = SchemaShape(fields=(_field("count", LogicalType.INT64),))
    assert classify_schema_evolution(expected, observed).classification is (
        SchemaEvolutionClassification.BREAKING
    )


def test_safe_evolution_allows_int_and_float_widening():
    expected = _contract(
        SchemaCompatibilityPolicy.SAFE_EVOLUTION,
        _field("count", LogicalType.INT32),
        _field("ratio", LogicalType.FLOAT32),
    )
    observed = SchemaShape(
        fields=(
            _field("count", LogicalType.INT64),
            _field("ratio", LogicalType.FLOAT64),
        )
    )
    decision = classify_schema_evolution(expected, observed)
    assert decision.classification is SchemaEvolutionClassification.COMPATIBLE
    assert {change.kind for change in decision.changes} == {SchemaChangeKind.TYPE_WIDENED}


def test_safe_evolution_rejects_numeric_narrowing_and_cross_family_cast():
    int_narrow = _contract(
        SchemaCompatibilityPolicy.SAFE_EVOLUTION,
        _field("count", LogicalType.INT64),
    )
    assert classify_schema_evolution(
        int_narrow,
        SchemaShape(fields=(_field("count", LogicalType.INT32),)),
    ).classification is SchemaEvolutionClassification.BREAKING

    cross_family = _contract(
        SchemaCompatibilityPolicy.SAFE_EVOLUTION,
        _field("count", LogicalType.INT64),
    )
    assert classify_schema_evolution(
        cross_family,
        SchemaShape(fields=(_field("count", LogicalType.STRING),)),
    ).classification is SchemaEvolutionClassification.BREAKING


def test_safe_string_widening_and_narrowing_are_distinguished():
    expected = _contract(
        SchemaCompatibilityPolicy.SAFE_EVOLUTION,
        _field("code", LogicalType.STRING, max_length=20),
    )
    wider = SchemaShape(fields=(_field("code", LogicalType.STRING, max_length=100),))
    unbounded = SchemaShape(fields=(_field("code", LogicalType.STRING),))
    narrower = SchemaShape(fields=(_field("code", LogicalType.STRING, max_length=10),))

    assert classify_schema_evolution(expected, wider).compatible
    assert classify_schema_evolution(expected, unbounded).compatible
    assert not classify_schema_evolution(expected, narrower).compatible


def test_unbounded_string_to_bounded_is_breaking():
    expected = _contract(
        SchemaCompatibilityPolicy.SAFE_EVOLUTION,
        _field("description", LogicalType.STRING),
    )
    observed = SchemaShape(
        fields=(_field("description", LogicalType.STRING, max_length=1000),)
    )
    assert not classify_schema_evolution(expected, observed).compatible


def test_decimal_precision_widening_requires_same_scale():
    expected = _contract(
        SchemaCompatibilityPolicy.SAFE_EVOLUTION,
        _field("amount", LogicalType.DECIMAL, precision=12, scale=2),
    )
    wider = SchemaShape(
        fields=(_field("amount", LogicalType.DECIMAL, precision=18, scale=2),)
    )
    changed_scale = SchemaShape(
        fields=(_field("amount", LogicalType.DECIMAL, precision=18, scale=4),)
    )
    narrower = SchemaShape(
        fields=(_field("amount", LogicalType.DECIMAL, precision=10, scale=2),)
    )

    assert classify_schema_evolution(expected, wider).compatible
    assert not classify_schema_evolution(expected, changed_scale).compatible
    assert not classify_schema_evolution(expected, narrower).compatible


def test_nullability_relaxation_is_safe_but_tightening_breaks():
    relaxed_contract = _contract(
        SchemaCompatibilityPolicy.SAFE_EVOLUTION,
        _field("code", LogicalType.STRING, nullable=False),
    )
    relaxed = SchemaShape(fields=(_field("code", LogicalType.STRING, nullable=True),))
    relaxed_decision = classify_schema_evolution(relaxed_contract, relaxed)
    assert relaxed_decision.compatible
    assert relaxed_decision.changes[0].kind is SchemaChangeKind.NULLABILITY_RELAXED

    tight_contract = _contract(
        SchemaCompatibilityPolicy.SAFE_EVOLUTION,
        _field("code", LogicalType.STRING, nullable=True),
    )
    tightened = SchemaShape(fields=(_field("code", LogicalType.STRING, nullable=False),))
    tight_decision = classify_schema_evolution(tight_contract, tightened)
    assert not tight_decision.compatible
    assert tight_decision.changes[0].kind is SchemaChangeKind.NULLABILITY_TIGHTENED


def test_field_removal_is_breaking_under_all_policies():
    for policy in SchemaCompatibilityPolicy:
        expected = _contract(
            policy,
            _field("id", LogicalType.INT64, nullable=False),
            _field("note", LogicalType.STRING),
        )
        observed = SchemaShape(fields=(_field("id", LogicalType.INT64, nullable=False),))
        decision = classify_schema_evolution(expected, observed)
        assert decision.classification is SchemaEvolutionClassification.BREAKING
        assert decision.changes[0].kind is SchemaChangeKind.FIELD_REMOVED


def test_require_compatible_schema_fails_closed_with_actionable_reason():
    expected = _contract(
        SchemaCompatibilityPolicy.SAFE_EVOLUTION,
        _field("id", LogicalType.INT64, nullable=False),
    )
    observed = SchemaShape(fields=(_field("id", LogicalType.INT32, nullable=False),))

    with pytest.raises(ValueError, match="TYPE_CHANGED"):
        require_compatible_schema(expected, observed)


def _dataset(contract: SchemaContract) -> DatasetConfig:
    return DatasetConfig(
        dataset_id="erp.customer",
        source=SourceConfig(system="erp", object="dbo.Customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(execution_group="erp_daily"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
        schema_contract=contract,
    )


def test_schema_contract_is_materialized_and_old_versions_are_preserved():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    v1 = _contract(
        SchemaCompatibilityPolicy.ADDITIVE_ONLY,
        _field("customer_id", LogicalType.INT64, nullable=False),
        version=1,
    )
    v2 = _contract(
        SchemaCompatibilityPolicy.SAFE_EVOLUTION,
        _field("customer_id", LogicalType.INT64, nullable=False),
        _field("email", LogicalType.STRING),
        version=2,
    )

    materialize_semantic_metadata(
        engine,
        configs=(_dataset(v1),),
        domain="customer",
        domain_git_sha="a" * 40,
        framework_version="0.4.0",
    )
    materialize_semantic_metadata(
        engine,
        configs=(_dataset(v2),),
        domain="customer",
        domain_git_sha="b" * 40,
        framework_version="0.4.0",
    )

    with engine.connect() as connection:
        rows = connection.execute(
            select(dataset_contract).order_by(dataset_contract.c.contract_version)
        ).mappings().all()

    assert [row["contract_version"] for row in rows] == [1, 2]
    assert rows[0]["schema_fingerprint"] == v1.fingerprint
    assert rows[1]["schema_fingerprint"] == v2.fingerprint
    assert rows[1]["compatibility_policy"] == "SAFE_EVOLUTION"
    assert rows[1]["definition"]["fields"][0]["name"] == "customer_id"


def test_schema_change_evidence_is_append_only_and_retains_decision_detail():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    expected = _contract(
        SchemaCompatibilityPolicy.SAFE_EVOLUTION,
        _field("customer_id", LogicalType.INT64, nullable=False),
    )
    config = _dataset(expected)
    materialize_semantic_metadata(
        engine,
        configs=(config,),
        domain="customer",
        domain_git_sha="c" * 40,
        framework_version="0.4.0",
    )
    observed = SchemaShape(
        fields=expected.fields + (_field("email", LogicalType.STRING),)
    )
    decision = classify_schema_evolution(expected, observed)
    evidence_id = uuid4()
    dataset_run_id = uuid4()
    observed_at = datetime(2026, 8, 29, 1, 2, tzinfo=timezone.utc)

    record_schema_change(
        engine,
        dataset_id=config.dataset_id,
        dataset_run_id=dataset_run_id,
        decision=decision,
        schema_change_id=evidence_id,
        observed_at=observed_at,
    )

    with engine.connect() as connection:
        row = connection.execute(select(schema_change)).mappings().one()
    assert row["schema_change_id"] == str(evidence_id)
    assert row["dataset_run_id"] == str(dataset_run_id)
    assert row["classification"] == "COMPATIBLE"
    assert row["expected_fingerprint"] == expected.fingerprint
    assert row["observed_fingerprint"] == observed.fingerprint
    assert row["details"]["policy"] == "SAFE_EVOLUTION"
    assert row["details"]["changes"][0]["kind"] == "FIELD_ADDED"

    with pytest.raises(ValueError, match="already recorded"):
        record_schema_change(
            engine,
            dataset_id=config.dataset_id,
            dataset_run_id=dataset_run_id,
            decision=decision,
            schema_change_id=evidence_id,
            observed_at=observed_at,
        )


def test_schema_change_observed_at_must_be_timezone_aware():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    expected = _contract(
        SchemaCompatibilityPolicy.EXACT,
        _field("id", LogicalType.INT64),
    )
    config = _dataset(expected)
    materialize_semantic_metadata(
        engine,
        configs=(config,),
        domain="customer",
        domain_git_sha="d" * 40,
        framework_version="0.4.0",
    )
    decision = classify_schema_evolution(expected, SchemaShape(fields=expected.fields))

    with pytest.raises(ValueError, match="timezone-aware"):
        record_schema_change(
            engine,
            dataset_id=config.dataset_id,
            decision=decision,
            observed_at=datetime(2026, 8, 29, 1, 2),
        )
