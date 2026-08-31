"""Notebook/manual certification records with explicit administrator override provenance.

This module is intentionally separate from evidence-based candidate certification.
A manual record may describe what an operator observed in a Fabric notebook, while an
administrator override may mark an exact candidate CERTIFIED even when some optional
context or live evidence was not retained. The record never disguises the override:
``admin_override``, ``override_reason``, ``missing_fields`` and execution mode are
always retained.

The normal evidence-based ``candidate-certification`` path remains unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from importlib.metadata import PackageNotFoundError, version as package_version
import json
from pathlib import Path
from typing import Iterable

from pydantic import Field, field_validator, model_validator

from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.deployment.candidate_artifact import (
    load_candidate_artifact_manifest,
    sha256_file,
)
from fabric_data_framework.evidence.safety import assert_safe_retained_text


MANUAL_CERTIFICATION_SCHEMA_VERSION = 1


class ManualCertificationMode(str, Enum):
    NOTEBOOK = "NOTEBOOK"
    GITHUB_ADMIN_OVERRIDE = "GITHUB_ADMIN_OVERRIDE"


class ManualCertificationStatus(str, Enum):
    PARTIAL = "PARTIAL"
    CERTIFIED = "CERTIFIED"


class ManualCertificationCheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"


class ManualCertificationCheck(FrozenModel):
    check_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    status: ManualCertificationCheckStatus
    evidence_reference: str | None = Field(default=None, max_length=2048)
    detail: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_safe_text(self) -> "ManualCertificationCheck":
        if self.evidence_reference:
            assert_safe_retained_text(
                self.evidence_reference, "manual certification evidence reference"
            )
        if self.detail:
            assert_safe_retained_text(self.detail, "manual certification check detail")
        return self


class ManualCertificationRecord(FrozenModel):
    certification_schema_version: int = Field(
        default=MANUAL_CERTIFICATION_SCHEMA_VERSION, ge=1
    )
    framework_version: str = Field(min_length=1, max_length=64)
    certification_mode: ManualCertificationMode
    status: ManualCertificationStatus
    generated_at: datetime
    candidate_git_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    artifact_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    environment: str | None = Field(
        default=None, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
    )
    operator: str | None = Field(default=None, max_length=256)
    notebook_reference: str | None = Field(default=None, max_length=2048)
    notes: str | None = Field(default=None, max_length=4000)
    checks: tuple[ManualCertificationCheck, ...] = ()
    missing_fields: tuple[str, ...] = ()
    admin_override: bool = False
    override_reason: str | None = Field(default=None, max_length=4000)
    release_authorized: bool = False

    @field_validator("missing_fields")
    @classmethod
    def validate_missing_fields(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("missing_fields must be unique")
        return value

    @model_validator(mode="after")
    def validate_record(self) -> "ManualCertificationRecord":
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        for field_name, value in (
            ("operator", self.operator),
            ("notebook_reference", self.notebook_reference),
            ("notes", self.notes),
            ("override_reason", self.override_reason),
        ):
            if value:
                assert_safe_retained_text(value, f"manual certification {field_name}")

        ids = [check.check_id for check in self.checks]
        if len(ids) != len(set(ids)):
            raise ValueError("manual certification check_id values must be unique")

        if self.admin_override:
            if self.status is not ManualCertificationStatus.CERTIFIED:
                raise ValueError("administrator override must produce CERTIFIED status")
            if not self.override_reason:
                raise ValueError("administrator override requires override_reason")
        elif self.status is ManualCertificationStatus.CERTIFIED:
            if self.candidate_git_sha is None or self.artifact_sha256 is None:
                raise ValueError(
                    "non-override manual CERTIFIED status requires exact candidate identity"
                )
            if not self.checks or any(
                check.status is not ManualCertificationCheckStatus.PASS
                for check in self.checks
            ):
                raise ValueError(
                    "non-override manual CERTIFIED status requires all supplied checks PASS"
                )

        if self.release_authorized:
            if not self.admin_override:
                raise ValueError(
                    "manual release authorization is available only through explicit admin override"
                )
            if self.candidate_git_sha is None or self.artifact_sha256 is None:
                raise ValueError(
                    "release authorization requires exact candidate git SHA and wheel SHA256"
                )
        return self


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _installed_framework_version() -> str:
    try:
        return package_version("fabric-data-framework")
    except PackageNotFoundError:
        return "0.4.0"


def _missing_fields(
    *,
    candidate_git_sha: str | None,
    artifact_sha256: str | None,
    environment: str | None,
    notebook_reference: str | None,
) -> tuple[str, ...]:
    values = {
        "candidate_git_sha": candidate_git_sha,
        "artifact_sha256": artifact_sha256,
        "environment": environment,
        "notebook_reference": notebook_reference,
    }
    return tuple(name for name, value in values.items() if not value)


def _normalize_checks(
    checks: Iterable[ManualCertificationCheck] | None,
) -> tuple[ManualCertificationCheck, ...]:
    return tuple(checks or ())


def create_manual_certification_record(
    *,
    checks: Iterable[ManualCertificationCheck] | None = None,
    framework_version: str | None = None,
    candidate_git_sha: str | None = None,
    artifact_sha256: str | None = None,
    environment: str | None = None,
    operator: str | None = None,
    notebook_reference: str | None = None,
    notes: str | None = None,
    candidate_manifest_path: str | Path | None = None,
    wheel_path: str | Path | None = None,
    admin_override: bool = False,
    override_reason: str | None = None,
    request_release_authorization: bool = False,
    mode: ManualCertificationMode = ManualCertificationMode.NOTEBOOK,
    now=_utcnow,
) -> ManualCertificationRecord:
    """Create a traceable notebook/manual certification record.

    ``CANDIDATE.json`` is the preferred identity source. When supplied it auto-fills
    framework version, git SHA and wheel SHA256. If ``wheel_path`` is also supplied,
    its bytes are hashed and must match the candidate manifest. This avoids manually
    copying long hashes into Fabric notebooks.

    With ``admin_override=True`` the record is CERTIFIED even if optional context or
    checks are absent. Missing values remain explicit in ``missing_fields``. Release
    authorization is a separate opt-in and still requires exact candidate identities.
    """

    if candidate_manifest_path is not None:
        manifest = load_candidate_artifact_manifest(candidate_manifest_path)
        if framework_version is not None and framework_version != manifest.framework_version:
            raise ValueError("framework_version does not match CANDIDATE.json")
        if candidate_git_sha is not None and candidate_git_sha != manifest.candidate_git_sha:
            raise ValueError("candidate_git_sha does not match CANDIDATE.json")
        if artifact_sha256 is not None and artifact_sha256 != manifest.wheel_sha256:
            raise ValueError("artifact_sha256 does not match CANDIDATE.json")
        framework_version = manifest.framework_version
        candidate_git_sha = manifest.candidate_git_sha
        artifact_sha256 = manifest.wheel_sha256

    if wheel_path is not None:
        actual_wheel_sha = sha256_file(wheel_path)
        if artifact_sha256 is not None and actual_wheel_sha != artifact_sha256:
            raise ValueError("wheel bytes do not match expected artifact_sha256")
        artifact_sha256 = actual_wheel_sha

    framework_version = framework_version or _installed_framework_version()
    normalized_checks = _normalize_checks(checks)
    exact_identity = candidate_git_sha is not None and artifact_sha256 is not None
    all_checks_pass = bool(normalized_checks) and all(
        check.status is ManualCertificationCheckStatus.PASS
        for check in normalized_checks
    )
    status = (
        ManualCertificationStatus.CERTIFIED
        if admin_override or (exact_identity and all_checks_pass)
        else ManualCertificationStatus.PARTIAL
    )
    release_authorized = bool(
        request_release_authorization and admin_override and exact_identity
    )

    return ManualCertificationRecord(
        framework_version=framework_version,
        certification_mode=mode,
        status=status,
        generated_at=now(),
        candidate_git_sha=candidate_git_sha,
        artifact_sha256=artifact_sha256,
        environment=environment,
        operator=operator,
        notebook_reference=notebook_reference,
        notes=notes,
        checks=normalized_checks,
        missing_fields=_missing_fields(
            candidate_git_sha=candidate_git_sha,
            artifact_sha256=artifact_sha256,
            environment=environment,
            notebook_reference=notebook_reference,
        ),
        admin_override=admin_override,
        override_reason=override_reason,
        release_authorized=release_authorized,
    )


def create_admin_override_record(**kwargs: object) -> ManualCertificationRecord:
    """Create an explicit administrator override record.

    The caller may omit optional notebook/environment context. Exact candidate identity
    is required only when ``request_release_authorization=True``.
    """

    return create_manual_certification_record(
        **kwargs,
        admin_override=True,
        mode=ManualCertificationMode.GITHUB_ADMIN_OVERRIDE,
    )


def load_manual_certification_record(path: str | Path) -> ManualCertificationRecord:
    return ManualCertificationRecord.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def write_manual_certification_record(
    record: ManualCertificationRecord, path: str | Path
) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def display_notebook_certification_form(
    *,
    candidate_manifest_path: str = "CANDIDATE.json",
    wheel_path: str = "",
    output_path: str = "manual-certification.json",
) -> object:
    """Render a compact ipywidgets form for Fabric/Jupyter notebooks.

    The UI deliberately keeps all fields editable and optional. If CANDIDATE.json is
    available, long candidate identities are auto-filled by the framework rather than
    typed by the operator. The admin-override checkbox allows a one-button CERTIFIED
    record while retaining missing-field and override provenance.
    """

    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Notebook certification UI requires ipywidgets and IPython; "
            "use create_manual_certification_record() programmatically instead"
        ) from exc

    environment = widgets.Text(description="Environment", placeholder="DEV / UAT / PROD")
    operator = widgets.Text(description="Operator")
    notebook_reference = widgets.Text(description="Notebook ref")
    notes = widgets.Textarea(description="Notes")
    override = widgets.Checkbox(value=False, description="Admin override")
    override_reason = widgets.Textarea(description="Override reason")
    release_authorize = widgets.Checkbox(
        value=False, description="Authorize exact-candidate release"
    )
    checks = {
        check_id: widgets.Checkbox(value=False, description=label)
        for check_id, label in (
            ("lakehouse.smoke", "Lakehouse smoke"),
            ("full.replace", "FULL → REPLACE"),
            ("watermark.scd1", "WATERMARK → SCD1"),
            ("watermark.scd2", "WATERMARK → SCD2"),
            ("retry.idempotency", "Retry / idempotency"),
            ("reconciliation.fail_closed", "Reconciliation fail-closed"),
            ("warehouse.commit", "Warehouse commit"),
            ("warehouse.ambiguous_commit", "Ambiguous COMMIT recovery"),
        )
    }
    button = widgets.Button(description="Create certification record")
    output = widgets.Output()

    def on_click(_: object) -> None:
        with output:
            output.clear_output()
            try:
                manifest = Path(candidate_manifest_path)
                selected_checks = tuple(
                    ManualCertificationCheck(
                        check_id=check_id,
                        status=ManualCertificationCheckStatus.PASS,
                        detail="operator observed PASS in notebook",
                    )
                    for check_id, checkbox in checks.items()
                    if checkbox.value
                )
                record = create_manual_certification_record(
                    checks=selected_checks,
                    environment=environment.value or None,
                    operator=operator.value or None,
                    notebook_reference=notebook_reference.value or None,
                    notes=notes.value or None,
                    candidate_manifest_path=manifest if manifest.is_file() else None,
                    wheel_path=wheel_path or None,
                    admin_override=override.value,
                    override_reason=override_reason.value or None,
                    request_release_authorization=release_authorize.value,
                )
                write_manual_certification_record(record, output_path)
                print(f"status={record.status.value}")
                print(f"mode={record.certification_mode.value}")
                print(f"missing_fields={list(record.missing_fields)}")
                print(f"release_authorized={record.release_authorized}")
                print(f"written={output_path}")
            except Exception as exc:  # pragma: no cover - UI surface
                print(f"ERROR: {exc}")

    button.on_click(on_click)
    display(
        widgets.VBox(
            [
                widgets.HTML("<b>Fabric Framework Manual Certification</b>"),
                environment,
                operator,
                notebook_reference,
                notes,
                widgets.HTML("<b>Observed PASS checks</b>"),
                *checks.values(),
                override,
                override_reason,
                release_authorize,
                button,
                output,
            ]
        )
    )
    return button


__all__ = [
    "MANUAL_CERTIFICATION_SCHEMA_VERSION",
    "ManualCertificationCheck",
    "ManualCertificationCheckStatus",
    "ManualCertificationMode",
    "ManualCertificationRecord",
    "ManualCertificationStatus",
    "create_admin_override_record",
    "create_manual_certification_record",
    "display_notebook_certification_form",
    "load_manual_certification_record",
    "write_manual_certification_record",
]
