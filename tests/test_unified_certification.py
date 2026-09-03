from __future__ import annotations

import json
from pathlib import Path

from fabric_data_framework.certification import (
    CertificationCheckResult,
    CertificationCheckStatus,
    CertificationOverallStatus,
    UnifiedCertificationReport,
)
from fabric_data_framework.certification import bounded as bounded_module
from fabric_data_framework.certification import unified as unified_module
from fabric_data_framework.certification.models import utcnow


REPO_ROOT = Path(__file__).parents[1]


class _FakeWriter:
    def __init__(self, spark, rows):
        self.spark = spark
        self.rows = rows

    def format(self, _value):
        return self

    def mode(self, _value):
        return self

    def save(self, path):
        self.spark.store[path] = list(self.rows)


class _FakeFrame:
    def __init__(self, spark, rows):
        self.spark = spark
        self.rows = rows

    @property
    def write(self):
        return _FakeWriter(self.spark, self.rows)

    def orderBy(self, key):
        return _FakeFrame(self.spark, sorted(self.rows, key=lambda row: row[key]))

    def collect(self):
        return list(self.rows)


class _FakeReader:
    def __init__(self, spark):
        self.spark = spark

    def format(self, _value):
        return self

    def load(self, path):
        return _FakeFrame(self.spark, self.spark.store[path])


class _FakeSpark:
    def __init__(self):
        self.store = {}
        self.read = _FakeReader(self)

    def createDataFrame(self, rows, columns):
        return _FakeFrame(
            self,
            [dict(zip(columns, row, strict=True)) for row in rows],
        )


def _pass(check_id: str) -> CertificationCheckResult:
    return CertificationCheckResult(
        check_id=check_id,
        status=CertificationCheckStatus.PASS,
        detail="pass",
    )


def test_bounded_semantic_probes_cover_the_manual_notebook_contracts():
    assert "destructive guard" in bounded_module._full_replace_probe()
    assert "SCD1" in bounded_module._scd1_probe()
    assert "SCD2" in bounded_module._scd2_probe()
    assert "idempotent" in bounded_module._retry_probe()
    assert "blocked state advance" in bounded_module._reconciliation_probe()
    assert "Delta write/read" in bounded_module._lakehouse_probe(
        _FakeSpark(),
        "Files/framework_cert",
    )


def test_packaged_certification_policies_match_release_canonical_json():
    pairs = (
        (
            REPO_ROOT / "release/0.4.0/integration-evidence-template.json",
            REPO_ROOT
            / "src/fabric_data_framework/certification/resources/integration-evidence-template.json",
        ),
        (
            REPO_ROOT / "release/0.4.0/readiness-spec.json",
            REPO_ROOT / "src/fabric_data_framework/certification/resources/readiness-spec.json",
        ),
    )
    for canonical, packaged in pairs:
        assert json.loads(packaged.read_text(encoding="utf-8")) == json.loads(
            canonical.read_text(encoding="utf-8")
        )


def test_unified_runner_is_partial_when_exact_customer_inputs_are_absent(
    monkeypatch,
    tmp_path,
):
    bounded = UnifiedCertificationReport(
        framework_version="0.4.0",
        candidate_git_sha="a" * 40,
        artifact_sha256="b" * 64,
        environment="DEV",
        started_at=utcnow(),
        completed_at=utcnow(),
        checks=tuple(
            _pass(check_id)
            for check_id in (
                "identity.exact",
                "lakehouse.smoke",
                "full.replace",
                "watermark.scd1",
                "watermark.scd2",
                "retry.idempotency",
                "reconciliation.fail_closed",
            )
        ),
    )
    monkeypatch.setattr(
        unified_module,
        "run_bounded_certification",
        lambda **_kwargs: bounded,
    )

    report = unified_module.certify(
        spark=object(),
        candidate_manifest_path="unused/CANDIDATE.json",
        wheel_path="unused/framework.whl",
        output_dir=tmp_path,
        environment="DEV",
    )

    by_id = {item.check_id: item for item in report.checks}
    assert by_id["fabric.item.read"].status is CertificationCheckStatus.NOT_RUN
    assert by_id["warehouse.ambiguous_commit"].status is CertificationCheckStatus.NOT_RUN
    assert by_id["business.full.replace"].status is CertificationCheckStatus.NOT_RUN
    assert report.overall_status is CertificationOverallStatus.PARTIAL
    assert report.release_authorized is False
    assert report.blockers == ("customer_inputs_not_supplied",)
    assert (tmp_path / "certification-report.json").is_file()


def test_unified_report_fails_when_any_check_fails():
    report = UnifiedCertificationReport(
        framework_version="0.4.0",
        candidate_git_sha="a" * 40,
        artifact_sha256="b" * 64,
        environment="DEV",
        started_at=utcnow(),
        completed_at=utcnow(),
        checks=(
            _pass("identity.exact"),
            CertificationCheckResult(
                check_id="lakehouse.smoke",
                status=CertificationCheckStatus.FAIL,
                detail="failed",
            ),
        ),
    )
    assert report.overall_status is CertificationOverallStatus.FAIL
    assert report.passed is False
