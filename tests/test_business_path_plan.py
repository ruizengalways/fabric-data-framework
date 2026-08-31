from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from fabric_data_framework.deployment.contracts import ReleaseBundleIdentity, ReleaseManifest
from fabric_data_framework.evidence.business_path_evidence import BusinessPathGate
from fabric_data_framework.evidence.business_path_plan import (
    ApprovedBusinessPathCertificationPlan,
    BusinessPathCertificationPlanEntry,
    load_approved_business_path_certification_plan,
    resolve_business_path_plan_file,
)


NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)


def _entries():
    return tuple(
        BusinessPathCertificationPlanEntry(
            gate_id=gate,
            scenario_path=f"config/certification/{gate.value}.scenario.json",
            driver_config_path=f"config/certification/{gate.value}.driver.json",
        )
        for gate in BusinessPathGate
    )


def _release(digest: str) -> ReleaseManifest:
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
            build_id="business-path-plan-test",
        ),
        generated_at=NOW,
        artifact_sha256={"business-path-plan.json": digest},
    )


def test_plan_requires_exact_five_gate_set():
    plan = ApprovedBusinessPathCertificationPlan(
        plan_artifact_name="business-path-plan.json",
        entries=_entries(),
    )
    assert {entry.gate_id for entry in plan.entries} == set(BusinessPathGate)

    with pytest.raises(ValueError, match="exactly all required gates"):
        ApprovedBusinessPathCertificationPlan(
            plan_artifact_name="business-path-plan.json",
            entries=_entries()[:-1],
        )

    duplicate = _entries()[:-1] + (_entries()[0],)
    with pytest.raises(ValueError, match="must be unique"):
        ApprovedBusinessPathCertificationPlan(
            plan_artifact_name="business-path-plan.json",
            entries=duplicate,
        )


def test_plan_paths_are_project_relative_and_cannot_escape(tmp_path):
    for path in ("../secret.json", "/tmp/secret.json", "./scenario.json"):
        with pytest.raises(ValueError):
            BusinessPathCertificationPlanEntry(
                gate_id=BusinessPathGate.FULL_REPLACE,
                scenario_path=path,
                driver_config_path="config/certification/driver.json",
            )

    root = tmp_path / "project"
    root.mkdir()
    resolved = resolve_business_path_plan_file(
        root,
        "config/certification/full.replace.scenario.json",
    )
    assert str(resolved).startswith(str(root.resolve()))


def test_plan_file_bytes_must_match_exact_release_fingerprint(tmp_path):
    plan = ApprovedBusinessPathCertificationPlan(
        plan_artifact_name="business-path-plan.json",
        entries=_entries(),
    )
    path = tmp_path / "business-path-plan.json"
    raw = (plan.model_dump_json(indent=2) + "\n").encode("utf-8")
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()

    loaded = load_approved_business_path_certification_plan(
        path,
        release_manifest=_release(digest),
    )
    assert loaded == plan

    with pytest.raises(ValueError, match="SHA256 mismatch"):
        load_approved_business_path_certification_plan(
            path,
            release_manifest=_release("f" * 64),
        )

    missing = _release(digest).model_copy(update={"artifact_sha256": {}})
    with pytest.raises(ValueError, match="absent from release manifest"):
        load_approved_business_path_certification_plan(path, release_manifest=missing)
