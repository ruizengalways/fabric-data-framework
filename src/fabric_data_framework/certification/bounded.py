"""One-call bounded certification for a real Fabric notebook runtime.

The bounded suite deliberately reuses framework primitives that are already heavily
covered by CI, but executes their environment-facing contracts again against the
installed exact wheel and an attached Fabric Lakehouse.  It never authorizes release
and it never substitutes for approved integration/warehouse evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
from uuid import uuid4

from fabric_data_framework.apply.replace import (
    InMemoryReplaceTarget,
    ReplaceGuardError,
    ReplaceGuardPolicy,
    plan_replace,
)
from fabric_data_framework.apply.scd1 import apply_scd1
from fabric_data_framework.apply.scd2 import (
    IS_CURRENT,
    VALID_FROM,
    VALID_TO,
    apply_scd2,
)
from fabric_data_framework.capture.full import FullSnapshotEvidence, capture_full_snapshot
from fabric_data_framework.contracts.audit import RowAccounting
from fabric_data_framework.data_plane.staging import stage_rows
from fabric_data_framework.deployment.candidate_artifact import (
    load_candidate_artifact_manifest,
    sha256_file,
)
from fabric_data_framework.quality.reconciliation import reconcile_scd2_batch

from .models import (
    CertificationCheckResult,
    CertificationCheckStatus,
    UnifiedCertificationReport,
    utcnow,
)


def _safe_check(check_id: str, operation) -> CertificationCheckResult:
    try:
        detail = operation()
    except Exception as exc:
        return CertificationCheckResult(
            check_id=check_id,
            status=CertificationCheckStatus.FAIL,
            detail=f"{check_id} failed ({type(exc).__name__})",
        )
    return CertificationCheckResult(
        check_id=check_id,
        status=CertificationCheckStatus.PASS,
        detail=detail,
    )


def _full_replace_probe() -> str:
    current_rows = [
        {"customer_id": 1, "name": "Old Alice"},
        {"customer_id": 2, "name": "Remove Me"},
    ]
    full_rows = [
        {"customer_id": 1, "name": "Alice"},
        {"customer_id": 3, "name": "New Customer"},
    ]
    run_id = uuid4()
    evidence = FullSnapshotEvidence(
        snapshot_id="bounded-cert-full",
        complete=True,
        source_row_count=len(full_rows),
        boundary_ref="framework:bounded-certification",
    )
    batch = capture_full_snapshot(full_rows, evidence=evidence)
    staged = stage_rows(batch.rows, dataset_run_id=run_id)
    plan = plan_replace(
        current_rows,
        staged,
        evidence=batch.evidence,
        policy=ReplaceGuardPolicy(),
    )
    target = InMemoryReplaceTarget(current_rows)
    target.publish(plan.rows)
    if list(target.read()) != full_rows:
        raise AssertionError("FULL replace result mismatch")

    incomplete = FullSnapshotEvidence(
        snapshot_id="bounded-cert-incomplete",
        complete=False,
        source_row_count=len(full_rows),
    )
    try:
        plan_replace(
            current_rows,
            staged,
            evidence=incomplete,
            policy=ReplaceGuardPolicy(),
        )
    except ReplaceGuardError:
        pass
    else:
        raise AssertionError("incomplete FULL snapshot was not rejected")
    return "FULL replace and incomplete-snapshot destructive guard passed"


def _ts(hour: int) -> datetime:
    return datetime(2026, 8, 31, hour, tzinfo=timezone.utc)


def _scd1_probe() -> str:
    existing = ({"customer_id": 1, "name": "Old", "modified_at": _ts(9)},)
    incoming = (
        {"customer_id": 1, "name": "New", "modified_at": _ts(10)},
        {"customer_id": 2, "name": "Second", "modified_at": _ts(10)},
    )
    result = apply_scd1(
        existing,
        incoming,
        merge_key=("customer_id",),
        ordering_columns=("modified_at",),
    )
    if result.mutations.inserted != 1 or result.mutations.updated != 1:
        raise AssertionError("SCD1 mutation counts mismatch")
    if {row["customer_id"]: row["name"] for row in result.rows} != {
        1: "New",
        2: "Second",
    }:
        raise AssertionError("SCD1 final state mismatch")
    return "WATERMARK to SCD1 semantics passed"


def _dt(day: int) -> datetime:
    return datetime(2026, 8, day, 10, tzinfo=timezone.utc)


def _customer(customer_id: str, name: str, day: int) -> dict[str, object]:
    return {
        "customer_id": customer_id,
        "name": name,
        "modified_at": _dt(day),
    }


def _scd2_state():
    run1 = apply_scd2(
        [],
        [_customer("C001", "Alice", 1)],
        business_key=("customer_id",),
        tracked_columns=("name",),
        effective_time_column="modified_at",
        dataset_run_id=uuid4(),
    )
    run2 = apply_scd2(
        run1.rows,
        [
            _customer("C001", "Alice", 2),
            _customer("C001", "Alice Smith", 3),
        ],
        business_key=("customer_id",),
        tracked_columns=("name",),
        effective_time_column="modified_at",
        dataset_run_id=uuid4(),
    )
    return run2


def _scd2_probe() -> str:
    result = _scd2_state()
    if len(result.rows) != 2:
        raise AssertionError("SCD2 row count mismatch")
    if result.rows[0][VALID_TO] != _dt(3) or result.rows[0][IS_CURRENT] is not False:
        raise AssertionError("SCD2 previous row was not closed")
    if result.rows[1][VALID_FROM] != _dt(3) or result.rows[1][IS_CURRENT] is not True:
        raise AssertionError("SCD2 current row bounds mismatch")
    if result.rows[1]["name"] != "Alice Smith":
        raise AssertionError("SCD2 current value mismatch")
    return "WATERMARK to SCD2 history semantics passed"


def _retry_probe() -> str:
    baseline = _scd2_state()
    rerun = apply_scd2(
        baseline.rows,
        [_customer("C001", "Alice Smith", 3)],
        business_key=("customer_id",),
        tracked_columns=("name",),
        effective_time_column="modified_at",
        dataset_run_id=uuid4(),
    )
    if rerun.rows != baseline.rows:
        raise AssertionError("retry changed SCD2 final state")
    if rerun.mutations.inserted != 0 or rerun.mutations.updated != 0:
        raise AssertionError("retry produced duplicate mutations")
    return "retry/rerun remained idempotent"


def _reconciliation_probe() -> str:
    state = _scd2_state()
    reconciliation = reconcile_scd2_batch(
        dataset_run_id=uuid4(),
        dataset_id="bounded-cert.scd2",
        policy_name="bounded-certification",
        accounting=RowAccounting(rows_read=1, rows_accepted=1),
        proposed_rows=state.rows,
        business_key=("customer_id",),
        force_fail=True,
    )
    if reconciliation.status.value != "FAIL":
        raise AssertionError("forced reconciliation did not FAIL")
    if reconciliation.blocks_state_advance is not True:
        raise AssertionError("failed reconciliation did not block state advance")
    return "forced reconciliation FAIL correctly blocked state advance"


def _lakehouse_probe(spark, base_path: str) -> str:
    smoke_path = f"{base_path.rstrip('/')}/lakehouse_smoke_{uuid4().hex[:8]}"
    source_df = spark.createDataFrame(
        [(1, "alpha"), (2, "beta")],
        ["id", "value"],
    )
    source_df.write.format("delta").mode("overwrite").save(smoke_path)
    observed = spark.read.format("delta").load(smoke_path).orderBy("id").collect()
    if [(row["id"], row["value"]) for row in observed] != [
        (1, "alpha"),
        (2, "beta"),
    ]:
        raise AssertionError("Lakehouse write/read roundtrip mismatch")
    return "real Delta write/read roundtrip passed"


def _write_report(report: UnifiedCertificationReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_bounded_certification(
    *,
    spark,
    candidate_manifest_path: str | Path,
    wheel_path: str | Path,
    environment: str = "DEV",
    lakehouse_base_path: str = "Files/framework_cert",
    output_path: str | Path | None = None,
    expected_git_sha: str | None = None,
    expected_wheel_sha256: str | None = None,
    expected_run_id: int | None = None,
) -> UnifiedCertificationReport:
    """Execute the bounded real-Fabric suite and optionally retain one JSON report."""

    started_at = utcnow()
    candidate = load_candidate_artifact_manifest(candidate_manifest_path)
    actual_wheel_sha = sha256_file(wheel_path)

    def identity_probe() -> str:
        if not Path(wheel_path).is_file():
            raise FileNotFoundError("candidate wheel is absent")
        if actual_wheel_sha != candidate.wheel_sha256:
            raise ValueError("wheel SHA256 does not match candidate manifest")
        if version("fabric-data-framework") != candidate.framework_version:
            raise ValueError("installed framework version does not match candidate manifest")
        if expected_git_sha is not None and candidate.candidate_git_sha != expected_git_sha:
            raise ValueError("candidate git SHA does not match expected identity")
        if expected_wheel_sha256 is not None and actual_wheel_sha != expected_wheel_sha256:
            raise ValueError("wheel SHA256 does not match expected identity")
        if expected_run_id is not None and candidate.workflow_run_id != expected_run_id:
            raise ValueError("candidate workflow run ID does not match expected identity")
        return "installed framework, candidate manifest and wheel bytes are exactly bound"

    identity = _safe_check("identity.exact", identity_probe)
    checks: list[CertificationCheckResult] = [identity]
    if identity.status is not CertificationCheckStatus.PASS:
        for check_id in (
            "lakehouse.smoke",
            "full.replace",
            "watermark.scd1",
            "watermark.scd2",
            "retry.idempotency",
            "reconciliation.fail_closed",
        ):
            checks.append(
                CertificationCheckResult(
                    check_id=check_id,
                    status=CertificationCheckStatus.NOT_RUN,
                    detail="not run because exact candidate identity failed",
                )
            )
    else:
        checks.extend(
            (
                _safe_check(
                    "lakehouse.smoke",
                    lambda: _lakehouse_probe(spark, lakehouse_base_path),
                ),
                _safe_check("full.replace", _full_replace_probe),
                _safe_check("watermark.scd1", _scd1_probe),
                _safe_check("watermark.scd2", _scd2_probe),
                _safe_check("retry.idempotency", _retry_probe),
                _safe_check("reconciliation.fail_closed", _reconciliation_probe),
            )
        )

    report = UnifiedCertificationReport(
        framework_version=candidate.framework_version,
        candidate_git_sha=candidate.candidate_git_sha,
        artifact_sha256=actual_wheel_sha,
        environment=environment,
        started_at=started_at,
        completed_at=utcnow(),
        checks=tuple(checks),
        blockers=(),
        release_authorized=False,
    )
    if output_path is not None:
        _write_report(report, output_path)
    return report


__all__ = ["run_bounded_certification"]
