from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from fabric_data_framework.deployment.contracts import ReleaseBundleIdentity, ReleaseManifest
from fabric_data_framework.evidence.business_path_driver import (
    ApprovedBusinessPathDriverConfig,
    BusinessPathDriverPhase,
    BusinessPathDriverReceipt,
    BusinessPathDriverRequest,
    load_approved_business_path_driver_config,
    validate_driver_receipt,
)
from fabric_data_framework.evidence.business_path_evidence import BusinessPathGate


NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)
SCENARIO_HASH = "a" * 64


def _config() -> ApprovedBusinessPathDriverConfig:
    return ApprovedBusinessPathDriverConfig(
        scenario_hash=SCENARIO_HASH,
        driver_extension="health.business_path_driver_v1",
        extension_artifact_name="health-business-path-driver.whl",
        driver_config_artifact_name="full-replace-driver.json",
        parameters={"fixture": "full_replace"},
    )


def _release(*, config_digest: str, include_driver: bool = True) -> ReleaseManifest:
    artifacts = {"full-replace-driver.json": config_digest}
    if include_driver:
        artifacts["health-business-path-driver.whl"] = "c" * 64
    return ReleaseManifest(
        domain="customer",
        bundle=ReleaseBundleIdentity(
            domain_release_version="0.4.0-dev",
            domain_git_sha="1" * 40,
            framework_version="0.4.0",
            config_bundle_hash="2" * 64,
            config_schema_version=1,
            control_plane_schema_version=1,
            fabric_item_manifest_version="v1",
            build_id="driver-contract-test",
        ),
        generated_at=NOW,
        artifact_sha256=artifacts,
    )


def test_driver_config_requires_exact_file_and_extension_fingerprints(tmp_path):
    config = _config()
    path = tmp_path / config.driver_config_artifact_name
    raw = (config.model_dump_json(indent=2) + "\n").encode("utf-8")
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()

    loaded = load_approved_business_path_driver_config(
        path,
        release_manifest=_release(config_digest=digest),
        expected_scenario_hash=SCENARIO_HASH,
    )
    assert loaded == config

    with pytest.raises(ValueError, match="scenario hash mismatch"):
        load_approved_business_path_driver_config(
            path,
            release_manifest=_release(config_digest=digest),
            expected_scenario_hash="b" * 64,
        )

    with pytest.raises(ValueError, match="SHA256 mismatch"):
        load_approved_business_path_driver_config(
            path,
            release_manifest=_release(config_digest="d" * 64),
            expected_scenario_hash=SCENARIO_HASH,
        )

    with pytest.raises(ValueError, match="not fingerprinted"):
        load_approved_business_path_driver_config(
            path,
            release_manifest=_release(config_digest=digest, include_driver=False),
            expected_scenario_hash=SCENARIO_HASH,
        )


def test_driver_receipt_has_no_pass_field_and_must_match_exact_request():
    request = BusinessPathDriverRequest(
        gate_id=BusinessPathGate.RETRY_IDEMPOTENCY,
        dataset_id="health.patient",
        scenario_hash=SCENARIO_HASH,
        phase=BusinessPathDriverPhase.PREPARE_ATTEMPT_1,
        parameters={"failure": "transient"},
    )
    receipt = BusinessPathDriverReceipt(
        gate_id=request.gate_id,
        dataset_id=request.dataset_id,
        scenario_hash=request.scenario_hash,
        phase=request.phase,
        evidence_references=("fabric-fixture://retry/attempt-1",),
    )

    validate_driver_receipt(request, receipt)
    assert "status" not in receipt.model_fields
    assert "passed" not in receipt.model_fields

    for changed, message in (
        ({"gate_id": BusinessPathGate.FULL_REPLACE}, "gate mismatch"),
        ({"dataset_id": "other.dataset"}, "dataset mismatch"),
        ({"scenario_hash": "b" * 64}, "scenario hash mismatch"),
        ({"phase": BusinessPathDriverPhase.PREPARE_ATTEMPT_2}, "phase mismatch"),
    ):
        with pytest.raises(ValueError, match=message):
            validate_driver_receipt(request, receipt.model_copy(update=changed))


def test_driver_config_and_receipt_reject_credential_like_retained_text():
    with pytest.raises(ValueError):
        ApprovedBusinessPathDriverConfig(
            scenario_hash=SCENARIO_HASH,
            driver_extension="health.driver",
            extension_artifact_name="driver.whl",
            driver_config_artifact_name="driver.json",
            parameters={"authorization": "Bearer abcdefghijklmnopqrstuvwxyz"},
        )

    with pytest.raises(ValueError):
        BusinessPathDriverReceipt(
            gate_id=BusinessPathGate.FULL_REPLACE,
            dataset_id="health.patient",
            scenario_hash=SCENARIO_HASH,
            phase=BusinessPathDriverPhase.CLEANUP,
            evidence_references=("password=supersecret",),
        )
