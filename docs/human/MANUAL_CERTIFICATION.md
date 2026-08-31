# Manual / Notebook Certification

Use this path when the company Fabric tenant cannot or should not be reached directly from GitHub Actions.

This document explains how to **record** a manual certification decision. For the first real company-Fabric test, execute [`FIRST_FABRIC_NOTEBOOK_TEST.md`](FIRST_FABRIC_NOTEBOOK_TEST.md) first. The form in this document does not run Lakehouse/SCD/Warehouse tests by itself.

## Two certification transports

The framework supports two separate operating models:

```text
A. evidence-based automation
   GitHub/approved runner -> real Fabric + databases -> retained machine evidence

B. manual/Notebook transport
   exact wheel -> company Fabric Notebook -> operator runs allowed checks
   -> manual-certification.json
```

The manual path exists for enterprises where identities, evidence, or credentials cannot conveniently leave the corporate Fabric boundary.

## Preferred company-Fabric flow

```text
successful framework-ci push run on main
  -> framework-wheel-<candidate SHA>
  -> wheel + CANDIDATE.json + SHA256SUMS
  -> isolated company Fabric DEV workspace
  -> attach disposable Lakehouse
  -> install exact wheel
  -> verify wheel bytes against CANDIDATE.json
  -> execute FIRST_FABRIC_NOTEBOOK_TEST.md
  -> open certification form
  -> record PASS / FAIL / NOT_RUN
  -> optional explicit Admin Override
  -> manual-certification.json
```

A green CI artifact is candidate-capable only. This flow does not automatically freeze/select a candidate and does not publish a release.

## Candidate identity without copying long hashes

`CANDIDATE.json` is the preferred identity source. Pass it directly to the API/form:

```python
from fabric_data_framework.evidence.manual_certification import (
    display_notebook_certification_form,
)

display_notebook_certification_form(
    candidate_manifest_path="/path/to/CANDIDATE.json",
    wheel_path="/path/to/fabric_data_framework-0.4.0-py3-none-any.whl",
    output_path="/path/to/manual-certification.json",
)
```

The framework then resolves:

```text
framework_version
candidate_git_sha
wheel SHA256
```

If `wheel_path` is supplied, the actual bytes are hashed and must match the candidate manifest. This is the recommended mode because it proves the Notebook is recording the identity of the wheel it actually received.

## Fabric Notebook widget compatibility

The form deliberately uses only Fabric-supported IPython widget types. In particular:

```text
Text / Textarea
Dropdown
Checkbox
Button
HTML
VBox
```

It does **not** use `ipywidgets.Output`, because Fabric currently documents Output widgets as unsupported. Callback results are shown in a supported disabled `Textarea`.

The form also uses a Dropdown for every certification check:

```text
NOT RUN
PASS
FAIL
```

This matters for auditability. A real failed check must be retainable as `FAIL`; it must not disappear merely because an old checkbox UI represented only positive results.

## The dropdowns do not execute tests

The following entries are observations only:

```text
Lakehouse smoke
FULL -> REPLACE
WATERMARK -> SCD1
WATERMARK -> SCD2
Retry / idempotency
Reconciliation fail-closed
Warehouse commit
Ambiguous COMMIT recovery
```

Set a value only after you ran the corresponding test or approved runner.

For the first bounded company test:

```text
Lakehouse + FULL/SCD1/SCD2/retry/reconciliation
  -> follow FIRST_FABRIC_NOTEBOOK_TEST.md

Warehouse commit / ambiguous COMMIT
  -> leave NOT RUN unless a real approved Warehouse test was performed
```

`NOT RUN` selections are not written as fake PASS evidence. PASS and FAIL are retained explicitly in the record.

## Normal non-override semantics

Without Admin Override:

```text
exact candidate identity missing
  -> PARTIAL

no supplied executed checks
  -> PARTIAL

any supplied executed check = FAIL
  -> PARTIAL

exact identity present + at least one supplied check + every supplied check PASS
  -> CERTIFIED
```

Normal `CERTIFIED` therefore means only that the checks actually supplied to this manual record passed. It is not equivalent to the full automated release-evidence chain unless all required release checks were actually run and retained through that separate path.

## Explicit Admin Override

Admin Override is intended for a real governance decision when some environment metadata or test coverage cannot be obtained/exported because of enterprise constraints.

It may produce:

```text
status = CERTIFIED
admin_override = true
override_reason = required
missing_fields = retained
```

Optional fields such as environment or notebook reference may remain absent. Missing evidence is not rewritten as evidence.

A recorded `FAIL` also remains a `FAIL` inside the record even if an administrator overrides the overall status to `CERTIFIED`. The recommended policy is to investigate known functional failures first; override should not be used to erase a product defect.

Never place secrets in:

```text
operator
notebook_reference
notes
override_reason
evidence_reference
check detail
```

The record safety validators reject common credential-like material.

## Release authorization checkbox

The Notebook form contains:

```text
Authorize exact-candidate release
```

This is a separate governance flag. It can become true only when:

```text
admin_override = true
candidate_git_sha is exact
artifact_sha256 is exact
request_release_authorization = true
```

For the first company smoke test, leave this checkbox **OFF** unless release governance explicitly asks for it.

Even when the manual record contains `release_authorized=true`, the existing strict framework `release.yml` does not consume this record as a substitute for evidence-based release readiness. That release-policy boundary is intentional.

## Programmatic record creation

For environments where widgets are disabled, use the API directly:

```python
from fabric_data_framework.evidence.manual_certification import (
    ManualCertificationCheck,
    ManualCertificationCheckStatus,
    create_manual_certification_record,
    write_manual_certification_record,
)

checks = (
    ManualCertificationCheck(
        check_id="lakehouse.smoke",
        status=ManualCertificationCheckStatus.PASS,
        detail="operator observed PASS in isolated DEV notebook",
    ),
    ManualCertificationCheck(
        check_id="warehouse.commit",
        status=ManualCertificationCheckStatus.NOT_RUN,
        detail="Warehouse permission not available",
    ),
)

record = create_manual_certification_record(
    checks=checks,
    candidate_manifest_path="/path/to/CANDIDATE.json",
    wheel_path="/path/to/framework.whl",
    environment="DEV",
)
write_manual_certification_record(record, "/path/to/manual-certification.json")
```

The UI normally omits `NOT_RUN` entries from the retained check tuple; a programmatic caller may retain an explicit NOT_RUN check when there is a reason to preserve that detail.

## GitHub-side Admin certification without GitHub-to-Fabric connectivity

The repository also has:

```text
.github/workflows/candidate-admin-certification.yml
```

This workflow does not authenticate to company Fabric. It takes the Framework main CI `candidate_run_id` plus explicit administrator confirmation/reason, downloads the exact GitHub candidate artifact, and independently verifies:

```text
candidate Git SHA
workflow run attempt
framework version
CANDIDATE.json
SHA256SUMS
wheel SHA256
exact wheel bytes
```

Therefore a corporate operator does not need to copy a 40-character Git SHA or 64-character wheel hash out of Fabric merely to create a GitHub-side administrator record.

This GitHub record is useful when the corporate boundary allows the decision/short run ID to be communicated but not the complete Notebook artifact/evidence bundle.

## What this path does not prove

A manual record, a checkbox/dropdown, green ordinary CI, or an Admin Override must not be described as proof for an unexecuted check.

Keep these claims separate:

```text
manual CERTIFIED
administrator accepted this candidate under manual governance

FABRIC PROVEN / WAREHOUSE PROVEN / evidence-based RELEASE PROVEN
requires the corresponding real retained evidence
```

The full automated path remains:

```text
exact frozen candidate
  -> exact Customer inputs
  -> candidate-integration-evidence
  -> five business-path proofs
  -> release proofs
  -> candidate-certification blockers=[] / release_ready=true
  -> exact-byte immutable release
```
