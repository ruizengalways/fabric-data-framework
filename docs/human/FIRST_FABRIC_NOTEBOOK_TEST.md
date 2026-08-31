# First Company Fabric Notebook Test

Status: bounded first-test runbook for the manual/Notebook certification lane.

Use this runbook before attempting the full evidence-based release chain. It is designed for a corporate Fabric tenant where GitHub Actions may not authenticate into Fabric and where Warehouse/control-plane privileges may be unavailable.

This is a **real Fabric smoke + framework semantic test**, but it is intentionally not the same thing as full release certification. It must never be described as proof for a check that was not actually run.

## 1. What this first test proves

The recommended first pass covers only the capabilities that can usually be exercised in an isolated DEV workspace without privileged infrastructure:

```text
package exact-byte identity
framework import/version
Lakehouse write/read smoke
FULL -> REPLACE guards and publication semantics
WATERMARK -> SCD1 semantics
WATERMARK -> SCD2 history semantics
retry/idempotency semantics
reconciliation fail-closed semantics
manual certification record generation
```

The following stay `NOT_RUN` unless you really have the required permissions/resources:

```text
Warehouse commit
Warehouse ambiguous-COMMIT recovery
production-eligible control-plane checks
full automated candidate integration/business-path evidence
```

An administrator may later use explicit Admin Override to accept missing items. That decision is retained as an override; it does not fabricate the missing evidence.

## 2. Required isolation

Use a disposable or explicitly approved company Fabric **DEV** workspace. Do not use production data for this first run.

Prepare:

```text
[ ] a Fabric Notebook using a supported Spark runtime
[ ] one disposable/default Lakehouse attached to the Notebook
[ ] permission to upload files into the Lakehouse Files area
[ ] permission to create/delete small test data under Files/framework_cert/
[ ] the exact framework candidate artifact from one successful main framework-ci run
```

The framework supports Python >=3.11. Fabric Runtime 1.3 uses Python 3.11 and Runtime 2.0 uses Python 3.13; both Python lanes are exercised by Framework CI. Use a GA runtime allowed by your organization.

## 3. Download one exact candidate artifact

In `fabric-data-framework`:

```text
Actions
  -> framework-ci
  -> choose one successful push run on main
  -> build-wheel
  -> download framework-wheel-<40-char-main-SHA>
```

The artifact must contain all three files:

```text
fabric_data_framework-0.4.0-py3-none-any.whl
CANDIDATE.json
SHA256SUMS
```

Do not download only the wheel if you can avoid it. `CANDIDATE.json` is what removes the need to manually type long Git/SHA256 identifiers in Fabric.

A green main CI artifact is **candidate-capable**. Downloading it does not freeze/select it and does not change `release_allowed`.

## 4. Put the files in the isolated Lakehouse

In the attached default Lakehouse, create:

```text
Files/framework_cert/
```

Upload:

```text
fabric_data_framework-0.4.0-py3-none-any.whl
CANDIDATE.json
SHA256SUMS
```

The default Lakehouse is mounted inside a Fabric Notebook at:

```text
/lakehouse/default/
```

Therefore the expected local paths are normally:

```text
/lakehouse/default/Files/framework_cert/fabric_data_framework-0.4.0-py3-none-any.whl
/lakehouse/default/Files/framework_cert/CANDIDATE.json
/lakehouse/default/Files/framework_cert/SHA256SUMS
```

If your organization uses a different file placement, use the exact File API path shown by Fabric and verify it with `Path(...).is_file()` before continuing.

## 5. Install the exact wheel

Notebook cell:

```python
WHEEL_PATH = "/lakehouse/default/Files/framework_cert/fabric_data_framework-0.4.0-py3-none-any.whl"
CANDIDATE_PATH = "/lakehouse/default/Files/framework_cert/CANDIDATE.json"
```

Then install the local wheel in a notebook cell:

```text
%pip install /lakehouse/default/Files/framework_cert/fabric_data_framework-0.4.0-py3-none-any.whl
```

If the workspace blocks outbound access and pip reports a missing dependency, do not temporarily open production network access just for this test. Prepare Linux wheels for the matching Fabric Python runtime outside the tenant, upload the required dependency wheels, then install locally. Framework runtime dependencies are bounded by `pyproject.toml`.

After an inline install, restart the Python session if Fabric tells you the new package is not visible:

```python
notebookutils.session.restartPython()
```

A restart clears Python variables, so rerun the path-variable cell afterward.

## 6. Verify exact candidate identity before testing

Run:

```python
from importlib.metadata import version
from pathlib import Path

from fabric_data_framework.deployment.candidate_artifact import (
    load_candidate_artifact_manifest,
    sha256_file,
)

WHEEL_PATH = "/lakehouse/default/Files/framework_cert/fabric_data_framework-0.4.0-py3-none-any.whl"
CANDIDATE_PATH = "/lakehouse/default/Files/framework_cert/CANDIDATE.json"

assert Path(WHEEL_PATH).is_file(), WHEEL_PATH
assert Path(CANDIDATE_PATH).is_file(), CANDIDATE_PATH

candidate = load_candidate_artifact_manifest(CANDIDATE_PATH)
actual_wheel_sha = sha256_file(WHEEL_PATH)

assert actual_wheel_sha == candidate.wheel_sha256
assert version("fabric-data-framework") == candidate.framework_version

print("framework_version=", candidate.framework_version)
print("candidate_git_sha=", candidate.candidate_git_sha)
print("wheel_sha256=", candidate.wheel_sha256)
print("candidate_run_id=", candidate.workflow_run_id)
print("IDENTITY PASS")
```

Do not manually retype the printed SHA values into the certification form. Pass `CANDIDATE_PATH` and `WHEEL_PATH` to the Framework UI later.

## 7. Lakehouse smoke

This check proves that the Notebook session can really write/read Delta data in the attached isolated Lakehouse.

Run:

```python
from uuid import uuid4

SMOKE_PATH = f"Files/framework_cert/lakehouse_smoke_{uuid4().hex[:8]}"

source_df = spark.createDataFrame(
    [(1, "alpha"), (2, "beta")],
    ["id", "value"],
)
source_df.write.format("delta").mode("overwrite").save(SMOKE_PATH)

observed = spark.read.format("delta").load(SMOKE_PATH).orderBy("id").collect()
assert [(row["id"], row["value"]) for row in observed] == [
    (1, "alpha"),
    (2, "beta"),
]

print("lakehouse.smoke = PASS")
print("test_path=", SMOKE_PATH)
```

If this cell fails, record `lakehouse.smoke = FAIL`; do not mark it PASS merely because the Notebook itself started successfully.

## 8. FULL -> REPLACE

Run:

```python
from uuid import uuid4

from fabric_data_framework.apply.replace import (
    InMemoryReplaceTarget,
    ReplaceGuardError,
    ReplaceGuardPolicy,
    plan_replace,
)
from fabric_data_framework.capture.full import (
    FullSnapshotEvidence,
    capture_full_snapshot,
)
from fabric_data_framework.data_plane.staging import stage_rows

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
    snapshot_id="first-fabric-test-full",
    complete=True,
    source_row_count=len(full_rows),
    boundary_ref="notebook:first-fabric-test",
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
assert list(target.read()) == full_rows

# Also prove that an incomplete FULL snapshot is rejected.
incomplete = FullSnapshotEvidence(
    snapshot_id="first-fabric-test-incomplete",
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

print("full.replace = PASS")
```

PASS means both the expected replacement result and the destructive guard behaved correctly.

## 9. WATERMARK -> SCD1

Run:

```python
from datetime import datetime, timezone

from fabric_data_framework.apply.scd1 import apply_scd1


def ts(hour: int):
    return datetime(2026, 8, 31, hour, tzinfo=timezone.utc)

existing_scd1 = (
    {"customer_id": 1, "name": "Old", "modified_at": ts(9)},
)
incoming_scd1 = (
    {"customer_id": 1, "name": "New", "modified_at": ts(10)},
    {"customer_id": 2, "name": "Second", "modified_at": ts(10)},
)

scd1_result = apply_scd1(
    existing_scd1,
    incoming_scd1,
    merge_key=("customer_id",),
    ordering_columns=("modified_at",),
)

assert scd1_result.mutations.inserted == 1
assert scd1_result.mutations.updated == 1
assert {row["customer_id"]: row["name"] for row in scd1_result.rows} == {
    1: "New",
    2: "Second",
}

print("watermark.scd1 = PASS")
```

## 10. WATERMARK -> SCD2

Run:

```python
from datetime import datetime, timezone
from uuid import uuid4

from fabric_data_framework.apply.scd2 import (
    IS_CURRENT,
    VALID_FROM,
    VALID_TO,
    apply_scd2,
)


def dt(day: int):
    return datetime(2026, 8, day, 10, tzinfo=timezone.utc)


def customer(customer_id: str, name: str, day: int):
    return {
        "customer_id": customer_id,
        "name": name,
        "modified_at": dt(day),
    }

scd2_run1 = apply_scd2(
    [],
    [customer("C001", "Alice", 1)],
    business_key=("customer_id",),
    tracked_columns=("name",),
    effective_time_column="modified_at",
    dataset_run_id=uuid4(),
)

scd2_run2 = apply_scd2(
    scd2_run1.rows,
    [
        customer("C001", "Alice", 2),
        customer("C001", "Alice Smith", 3),
    ],
    business_key=("customer_id",),
    tracked_columns=("name",),
    effective_time_column="modified_at",
    dataset_run_id=uuid4(),
)

assert len(scd2_run2.rows) == 2
assert scd2_run2.rows[0][VALID_TO] == dt(3)
assert scd2_run2.rows[0][IS_CURRENT] is False
assert scd2_run2.rows[1][VALID_FROM] == dt(3)
assert scd2_run2.rows[1][IS_CURRENT] is True
assert scd2_run2.rows[1]["name"] == "Alice Smith"

print("watermark.scd2 = PASS")
```

## 11. Retry / idempotency

Use the exact SCD2 change a second time and prove it produces no new history row or mutation:

```python
from uuid import uuid4

scd2_rerun = apply_scd2(
    scd2_run2.rows,
    [customer("C001", "Alice Smith", 3)],
    business_key=("customer_id",),
    tracked_columns=("name",),
    effective_time_column="modified_at",
    dataset_run_id=uuid4(),
)

assert scd2_rerun.rows == scd2_run2.rows
assert scd2_rerun.mutations.inserted == 0
assert scd2_rerun.mutations.updated == 0

print("retry.idempotency = PASS")
```

## 12. Reconciliation fail-closed

Run a deliberately forced reconciliation failure. PASS for this certification check means the Framework itself returned a reconciliation FAIL and explicitly marked state advancement as blocked.

```python
from fabric_data_framework.contracts.audit import RowAccounting
from fabric_data_framework.quality.reconciliation import reconcile_scd2_batch

reconciliation = reconcile_scd2_batch(
    dataset_run_id=uuid4(),
    dataset_id="first-fabric-test.scd2",
    policy_name="first-fabric-test",
    accounting=RowAccounting(rows_read=1, rows_accepted=1),
    proposed_rows=scd2_run2.rows,
    business_key=("customer_id",),
    force_fail=True,
)

assert reconciliation.status.value == "FAIL"
assert reconciliation.blocks_state_advance is True

print("reconciliation.fail_closed = PASS")
```

Do not invert the meaning: the underlying reconciliation result must be `FAIL`; the certification check is PASS because the fail-closed behavior worked correctly.

## 13. Optional: persist semantic output to the real Lakehouse

This is not required to prove the pure semantic functions above, but it is useful during the first company Fabric run to show that the resulting data can be serialized into the attached Lakehouse.

```python
RESULT_PATH = f"Files/framework_cert/scd2_result_{uuid4().hex[:8]}"

spark.createDataFrame([dict(row) for row in scd2_run2.rows]).write \
    .format("delta") \
    .mode("overwrite") \
    .save(RESULT_PATH)

assert spark.read.format("delta").load(RESULT_PATH).count() == len(scd2_run2.rows)
print("semantic result persisted to", RESULT_PATH)
```

If your runtime cannot infer a schema for a field, this optional persistence step may be skipped; do not convert a skipped optional persistence step into a failed SCD2 semantic check.

## 14. Warehouse checks

For the first run, if you do not have the approved Warehouse resources/permissions, record:

```text
warehouse.commit = NOT_RUN
warehouse.ambiguous_commit = NOT_RUN
```

Do not run destructive session termination or ambiguous-COMMIT fault injection against a shared/production Warehouse merely to complete the form.

If those permissions/resources are later approved, use the dedicated Framework approved Warehouse runners and the full certification runbook instead of inventing a local substitute.

## 15. Create the manual certification record

After the real test cells have run, open the Fabric-compatible form:

```python
from fabric_data_framework.evidence.manual_certification import (
    display_notebook_certification_form,
)

display_notebook_certification_form(
    candidate_manifest_path=CANDIDATE_PATH,
    wheel_path=WHEEL_PATH,
    output_path="/lakehouse/default/Files/framework_cert/manual-certification.json",
)
```

Important: the dropdowns **record** what you observed; they do not execute the tests.

Set each dropdown from the actual cells above:

```text
Lakehouse smoke                 PASS or FAIL
FULL -> REPLACE                 PASS or FAIL
WATERMARK -> SCD1              PASS or FAIL
WATERMARK -> SCD2              PASS or FAIL
Retry / idempotency            PASS or FAIL
Reconciliation fail-closed     PASS or FAIL
Warehouse commit               NOT RUN unless actually tested
Ambiguous COMMIT recovery      NOT RUN unless actually tested
```

Context fields such as `Environment` and `Notebook ref` are optional. Do not copy secrets into any field.

## 16. Normal vs Admin Override result

Recommended behavior:

```text
all executed first-test checks PASS + exact CANDIDATE identity
  -> normal Notebook CERTIFIED is acceptable

some checks unavailable because of corporate permissions
  -> leave them NOT_RUN
  -> Admin Override may be used if an authorized administrator accepts the missing coverage

any executed functional check FAILS
  -> retain FAIL explicitly
  -> normally investigate/fix before certifying
  -> Admin Override can still retain an explicit governance acceptance, but must not hide the FAIL
```

For Admin Override:

```text
[ ] Admin override          -> select only when intended
Override reason             -> required, non-secret
Authorize exact-candidate release -> leave OFF for the first smoke test unless release governance explicitly requires it
```

The current strict framework release workflow does not consume this manual release-authorization flag as a substitute for evidence-based release readiness.

## 17. Inspect the generated JSON

Run:

```python
import json
from pathlib import Path

CERT_PATH = Path("/lakehouse/default/Files/framework_cert/manual-certification.json")
record = json.loads(CERT_PATH.read_text())
print(json.dumps(record, indent=2))

assert record["status"] in {"PARTIAL", "CERTIFIED"}
assert record["candidate_git_sha"] == candidate.candidate_git_sha
assert record["artifact_sha256"] == candidate.wheel_sha256
```

Verify that:

```text
[ ] actual PASS/FAIL checks are represented correctly
[ ] checks you did not run are not falsely represented as PASS
[ ] admin_override is correct
[ ] override_reason is present if admin_override=true
[ ] missing_fields is honest
[ ] no token/password/connection string is present
```

## 18. Optional GitHub-side Admin certification

If corporate policy allows only the *decision* to be copied out, you do not need to copy long SHA values from Fabric.

Back in GitHub:

```text
fabric-data-framework
  -> Actions
  -> candidate-admin-certification
  -> Run workflow
```

Supply the same `candidate_run_id` that produced the tested artifact plus:

```text
override_reason
confirm_admin_override = true
```

Environment/notebook reference/notes are optional. GitHub independently re-resolves the exact candidate identity from that run.

This GitHub-side workflow still does not connect into company Fabric and it does not make missing Fabric evidence magically exist.

## 19. Cleanup

Delete only the disposable first-test paths you created. Example:

```python
for path in [SMOKE_PATH]:
    try:
        notebookutils.fs.rm(path, True)
        print("removed", path)
    except Exception as exc:
        print("cleanup warning", path, exc)
```

Keep `manual-certification.json` if company policy allows retention. Keep the original exact wheel + `CANDIDATE.json` together until the test decision is recorded.

## 20. Stop conditions

Stop the first test and investigate rather than clicking through when:

```text
wheel SHA does not match CANDIDATE.json
installed framework version differs from CANDIDATE.json
Lakehouse smoke cannot write/read isolated data
FULL incomplete-snapshot guard does not fail closed
SCD1 result is incorrect
SCD2 history/current-row invariant is incorrect
idempotent rerun creates new mutations/history
forced reconciliation does not return FAIL + blocks_state_advance=true
```

Admin Override is intended for unavailable/export-restricted evidence and explicit governance decisions. It is not a mechanism for erasing a known product defect.
