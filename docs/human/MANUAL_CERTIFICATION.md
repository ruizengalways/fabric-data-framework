# Manual / Notebook Certification

Status: supported alongside the existing evidence-based GitHub certification path.

This mode exists for enterprise environments where GitHub Actions is not allowed to connect directly to Microsoft Fabric, or where copying long identifiers and retained evidence out of a corporate Fabric tenant is impractical.

It does **not** silently pretend that manual/admin certification is evidence-based certification. Every generated record retains its execution mode, administrator override flag, override reason, missing fields, exact candidate identity when known, and whether exact-candidate release authorization was requested.

## 1. Two certification transports

The framework supports two distinct transports over the same candidate bytes:

```text
A. evidence-based automation
   GitHub Actions -> protected Fabric environment -> retained evidence -> candidate-certification

B. manual / notebook
   exact wheel + CANDIDATE.json -> Fabric Notebook -> operator-observed checks -> manual-certification.json
```

An administrator may also use the GitHub `candidate-admin-certification` workflow. That workflow does **not** connect to Fabric. It resolves the exact candidate SHA, framework version and wheel SHA256 from a successful main CI run, then creates an explicit administrator certification record.

## 2. Recommended company-Fabric flow

Download the framework candidate artifact from the selected successful `main` CI run. Keep these files together when practical:

```text
fabric_data_framework-0.4.0-py3-none-any.whl
CANDIDATE.json
SHA256SUMS
```

Upload the wheel and `CANDIDATE.json` into the isolated Fabric certification environment.

Install the wheel in a Fabric Notebook / Environment, then run:

```python
from fabric_data_framework.evidence.manual_certification import (
    display_notebook_certification_form,
)

display_notebook_certification_form(
    candidate_manifest_path="CANDIDATE.json",
    output_path="manual-certification.json",
)
```

The form displays checkboxes for the common certification paths and a button that writes a machine-readable record.

If `CANDIDATE.json` is present, the framework automatically fills:

```text
framework_version
candidate_git_sha
artifact_sha256
```

The operator does not need to manually type the 40-character git SHA or 64-character wheel SHA256.

If the original wheel file is also still available, pass `wheel_path=...` and the framework hashes the actual bytes and rejects a mismatch with `CANDIDATE.json`.

## 3. Normal notebook result

Without administrator override, a notebook record is `CERTIFIED` only when:

```text
exact candidate git SHA is known
exact wheel SHA256 is known
at least one check is supplied
all supplied checks are PASS
```

Otherwise the record is `PARTIAL`.

A normal notebook record never authorizes the release workflow by itself. Evidence-based release certification remains the default release path.

## 4. Administrator override

For environments where some details cannot be exported, select `Admin override` in the notebook form and provide a non-secret reason.

The record may then be:

```text
status = CERTIFIED
admin_override = true
```

while still explicitly retaining, for example:

```text
missing_fields = ["environment", "notebook_reference"]
```

An override is therefore visible and auditable; missing evidence is not rewritten as fabricated evidence.

If the exact candidate SHA or wheel SHA is unavailable in the notebook, the record can still be `CERTIFIED`, but `release_authorized` remains false.

## 5. Simplest GitHub admin action

When the selected candidate came from framework `main`, use:

```text
Actions
  -> candidate-admin-certification
  -> Run workflow
```

The only candidate identity that must be supplied is:

```text
candidate_run_id
```

The workflow automatically resolves and verifies:

```text
candidate_git_sha
workflow run attempt
framework_version
wheel filename
wheel SHA256
SHA256SUMS
```

Optional fields:

```text
environment
notebook_reference
notes
```

Required administrator fields:

```text
override_reason
confirm_admin_override = true
```

It then uploads:

```text
admin-certification-<candidate SHA>/
  manual-certification.json
  CANDIDATE.json
  SHA256SUMS
```

The record is created with:

```text
certification_mode = GITHUB_ADMIN_OVERRIDE
status = CERTIFIED
admin_override = true
release_authorized = true
```

because GitHub itself has re-resolved and verified the exact candidate identity. This workflow never logs into Fabric and requires no Fabric token, Service Principal, Warehouse connection string or company tenant access.

## 6. What administrator override means

Administrator override means:

> an authorized human accepts the candidate as certified despite an incomplete normal retained-evidence chain.

It does **not** mean:

```text
all live Fabric checks were automatically proven
all missing fields were present
Warehouse ambiguous-COMMIT was proven when it was not run
GitHub connected to the company Fabric tenant
```

The distinction is deliberately retained in the artifact so a later automated certification can coexist with the earlier manual decision.

## 7. Secrets

Never put passwords, tokens, connection strings, signed URLs or credentials into:

```text
override_reason
notes
notebook_reference
manual-certification.json
```

The framework applies the same retained-text credential screening used by other evidence records.

## 8. Future automated re-certification

A later personal or approved enterprise Fabric environment may run the existing automated path:

```text
candidate-integration-evidence
candidate-business-path-evidence
candidate-release-proofs
candidate-certification
```

That does not invalidate the historical manual record. The project can retain both:

```text
initial certification: GITHUB_ADMIN_OVERRIDE / NOTEBOOK
later certification:   evidence-based automated certification
```

This makes the operational history explicit rather than rewriting it.
