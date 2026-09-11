import pytest
from pydantic import ValidationError

from fabric_data_framework.metadata.config import ApplyStrategy, CaptureStrategy, LoadPolicy


def test_scd2_accepts_matching_business_and_merge_keys():
    policy = LoadPolicy(
        capture_strategy=CaptureStrategy.FULL,
        apply_strategy=ApplyStrategy.SCD2,
        business_key=("customer_id",),
        merge_key=("customer_id",),
        tracked_columns=("email",),
    )

    assert policy.business_key == ("customer_id",)
    assert policy.merge_key == policy.business_key


def test_scd2_rejects_divergent_business_and_merge_keys():
    with pytest.raises(ValidationError, match="SCD2 merge_key must equal business_key"):
        LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.SCD2,
            business_key=("customer_id",),
            merge_key=("email",),
            tracked_columns=("email",),
        )


def test_scd2_still_requires_both_declared_keys():
    with pytest.raises(ValidationError, match="SCD2 apply requires merge_key"):
        LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.SCD2,
            business_key=("customer_id",),
            tracked_columns=("email",),
        )

    with pytest.raises(ValidationError, match="SCD2 apply requires business_key"):
        LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.SCD2,
            merge_key=("customer_id",),
            tracked_columns=("email",),
        )
