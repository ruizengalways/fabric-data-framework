from __future__ import annotations

import json

import pytest

from fabric_data_framework.cli.main import main
from fabric_data_framework.evidence.release_readiness import (
    ReleaseReadinessGateKind,
    ReleaseReadinessGateSpec,
    ReleaseReadinessProofBundle,
    ReleaseReadinessProofResult,
    ReleaseReadinessSpec,
    ReleaseReadinessStatus,
)
from fabric_data_framework.evidence.release_readiness_merge import (
    ReleaseReadinessProofMergeConflict,
    merge_release_readiness_proof_bundles,
)


CANDIDATE = "a" * 40
WHEEL = "b" * 64


def _spec() -> ReleaseReadinessSpec:
    return ReleaseReadinessSpec(
        framework_version="0.4.0",
        gates=(
            ReleaseReadinessGateSpec(
                gate_id="source.tests",
                kind=ReleaseReadinessGateKind.SOURCE_VERIFICATION,
            ),
            ReleaseReadinessGateSpec(
                gate_id="full.replace",
                kind=ReleaseReadinessGateKind.FULL_REPLACE,
            ),
            ReleaseReadinessGateSpec(
                gate_id="fabric.pipeline",
                kind=ReleaseReadinessGateKind.FABRIC_PIPELINE,
                integration_check_id="fabric.pipeline",
            ),
        ),
    )


def _proof(
    gate_id: str,
    kind: ReleaseReadinessGateKind,
    *,
    status: ReleaseReadinessStatus = ReleaseReadinessStatus.PASS,
    reference: str = "artifact://proof",
    detail: str | None = None,
) -> ReleaseReadinessProofResult:
    refs = () if status is ReleaseReadinessStatus.NOT_RUN else (reference,)
    return ReleaseReadinessProofResult(
        gate_id=gate_id,
        kind=kind,
        status=status,
        evidence_references=refs,
        detail=detail,
    )


def _bundle(
    *results: ReleaseReadinessProofResult,
    candidate: str = CANDIDATE,
    wheel: str | None = WHEEL,
    schema: int = 1,
) -> ReleaseReadinessProofBundle:
    return ReleaseReadinessProofBundle(
        readiness_schema_version=schema,
        framework_version="0.4.0",
        candidate_git_sha=candidate,
        artifact_sha256=wheel,
        results=results,
    )


def test_merge_combines_disjoint_exact_candidate_partial_proofs():
    merged = merge_release_readiness_proof_bundles(
        _spec(),
        (
            _bundle(
                _proof(
                    "source.tests",
                    ReleaseReadinessGateKind.SOURCE_VERIFICATION,
                    reference="artifact://source-tests",
                )
            ),
            _bundle(
                _proof(
                    "full.replace",
                    ReleaseReadinessGateKind.FULL_REPLACE,
                    reference="fabric-run://full-replace",
                )
            ),
        ),
    )

    assert merged.candidate_git_sha == CANDIDATE
    assert merged.artifact_sha256 == WHEEL
    assert [item.gate_id for item in merged.results] == ["source.tests", "full.replace"]


def test_merge_treats_omitted_and_not_run_as_absence_of_proof():
    merged = merge_release_readiness_proof_bundles(
        _spec(),
        (
            _bundle(
                _proof(
                    "source.tests",
                    ReleaseReadinessGateKind.SOURCE_VERIFICATION,
                    status=ReleaseReadinessStatus.NOT_RUN,
                )
            ),
            _bundle(),
        ),
    )

    assert merged.results == ()


def test_merge_accepts_model_identical_duplicate_substantive_proof():
    result = _proof(
        "source.tests",
        ReleaseReadinessGateKind.SOURCE_VERIFICATION,
        reference="artifact://same",
    )

    merged = merge_release_readiness_proof_bundles(_spec(), (_bundle(result), _bundle(result)))

    assert merged.results == (result,)


def test_merge_rejects_different_pass_evidence_instead_of_using_precedence():
    with pytest.raises(ReleaseReadinessProofMergeConflict, match="conflicting substantive"):
        merge_release_readiness_proof_bundles(
            _spec(),
            (
                _bundle(
                    _proof(
                        "source.tests",
                        ReleaseReadinessGateKind.SOURCE_VERIFICATION,
                        reference="artifact://first",
                    )
                ),
                _bundle(
                    _proof(
                        "source.tests",
                        ReleaseReadinessGateKind.SOURCE_VERIFICATION,
                        reference="artifact://rerun",
                    )
                ),
            ),
        )


def test_merge_rejects_pass_fail_conflict():
    with pytest.raises(ReleaseReadinessProofMergeConflict):
        merge_release_readiness_proof_bundles(
            _spec(),
            (
                _bundle(
                    _proof(
                        "full.replace",
                        ReleaseReadinessGateKind.FULL_REPLACE,
                        reference="fabric-run://pass",
                    )
                ),
                _bundle(
                    _proof(
                        "full.replace",
                        ReleaseReadinessGateKind.FULL_REPLACE,
                        status=ReleaseReadinessStatus.FAIL,
                        reference="fabric-run://fail",
                    )
                ),
            ),
        )


def test_merge_requires_exact_wheel_binding_on_every_partial_bundle():
    with pytest.raises(ValueError, match="artifact_sha256"):
        merge_release_readiness_proof_bundles(_spec(), (_bundle(wheel=None),))

    with pytest.raises(ValueError, match="artifact SHA256 mismatch"):
        merge_release_readiness_proof_bundles(
            _spec(),
            (_bundle(), _bundle(wheel="c" * 64)),
        )


def test_merge_requires_same_schema_and_exact_candidate_sha():
    with pytest.raises(ValueError, match="schema version"):
        merge_release_readiness_proof_bundles(_spec(), (_bundle(schema=2),))

    with pytest.raises(ValueError, match="candidate git SHA mismatch"):
        merge_release_readiness_proof_bundles(
            _spec(),
            (_bundle(), _bundle(candidate="d" * 40)),
        )


def test_merge_rejects_unknown_kind_drift_and_integration_backed_gate():
    with pytest.raises(ValueError, match="unknown gate"):
        merge_release_readiness_proof_bundles(
            _spec(),
            (
                _bundle(
                    _proof(
                        "unknown.gate",
                        ReleaseReadinessGateKind.FULL_REPLACE,
                    )
                ),
            ),
        )

    with pytest.raises(ValueError, match="kind mismatch"):
        merge_release_readiness_proof_bundles(
            _spec(),
            (
                _bundle(
                    _proof(
                        "source.tests",
                        ReleaseReadinessGateKind.FULL_REPLACE,
                    )
                ),
            ),
        )

    with pytest.raises(ValueError, match="integration-backed"):
        merge_release_readiness_proof_bundles(
            _spec(),
            (
                _bundle(
                    _proof(
                        "fabric.pipeline",
                        ReleaseReadinessGateKind.FABRIC_PIPELINE,
                    )
                ),
            ),
        )


def test_merge_rejects_credential_like_retained_reference_and_detail():
    with pytest.raises(ValueError, match="credential material"):
        merge_release_readiness_proof_bundles(
            _spec(),
            (
                _bundle(
                    _proof(
                        "source.tests",
                        ReleaseReadinessGateKind.SOURCE_VERIFICATION,
                        reference="https://example.invalid/proof?access_token=secret",
                    )
                ),
            ),
        )

    with pytest.raises(ValueError, match="credential material"):
        merge_release_readiness_proof_bundles(
            _spec(),
            (
                _bundle(
                    _proof(
                        "source.tests",
                        ReleaseReadinessGateKind.SOURCE_VERIFICATION,
                        detail="authorization: bearer redacted",
                    )
                ),
            ),
        )


def test_release_proofs_merge_cli_writes_exact_merged_bundle(tmp_path):
    spec = tmp_path / "spec.json"
    first = tmp_path / "static.json"
    second = tmp_path / "live.json"
    output = tmp_path / "release-proofs.json"
    spec.write_text(json.dumps(_spec().model_dump(mode="json")), encoding="utf-8")
    first.write_text(
        json.dumps(
            _bundle(
                _proof(
                    "source.tests",
                    ReleaseReadinessGateKind.SOURCE_VERIFICATION,
                    reference="artifact://source-tests",
                )
            ).model_dump(mode="json")
        ),
        encoding="utf-8",
    )
    second.write_text(
        json.dumps(
            _bundle(
                _proof(
                    "full.replace",
                    ReleaseReadinessGateKind.FULL_REPLACE,
                    reference="fabric-run://full-replace",
                )
            ).model_dump(mode="json")
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "release-proofs-merge",
            "--spec",
            str(spec),
            "--input",
            str(first),
            "--input",
            str(second),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["candidate_git_sha"] == CANDIDATE
    assert payload["artifact_sha256"] == WHEEL
    assert [item["gate_id"] for item in payload["results"]] == [
        "source.tests",
        "full.replace",
    ]


def test_release_proofs_merge_cli_fails_closed_on_conflicting_reruns(tmp_path, capsys):
    spec = tmp_path / "spec.json"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    output = tmp_path / "release-proofs.json"
    spec.write_text(json.dumps(_spec().model_dump(mode="json")), encoding="utf-8")
    for path, reference in ((first, "artifact://one"), (second, "artifact://two")):
        path.write_text(
            json.dumps(
                _bundle(
                    _proof(
                        "source.tests",
                        ReleaseReadinessGateKind.SOURCE_VERIFICATION,
                        reference=reference,
                    )
                ).model_dump(mode="json")
            ),
            encoding="utf-8",
        )

    exit_code = main(
        [
            "release-proofs-merge",
            "--spec",
            str(spec),
            "--input",
            str(first),
            "--input",
            str(second),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 2
    assert not output.exists()
    assert "conflicting substantive release proof" in capsys.readouterr().err
