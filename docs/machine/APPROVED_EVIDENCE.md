# MACHINE APPROVED EVIDENCE CONTRACT

This file consolidates exact approved-run behavior that used to be spread across multiple stage-specific runbooks.

## Evidence check kinds

Current important kinds:

```text
FABRIC_ITEM_READ
FABRIC_PIPELINE_RUN
FABRIC_COPY_JOB_CAPTURE
FABRIC_SPARK_CAPTURE
FABRIC_WAREHOUSE_TARGET_COMMIT
FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL
CONTROL_PLANE_CERTIFICATION
KAFKA_PROVIDER
DELTA_CDF_PROVIDER
```

Statuses:

```text
PASS
FAIL
NOT_RUN
EXTERNAL_REQUIRED
```

Required checks certify only on `PASS`.

## Exact identity

Every approved evidence stage is bound to:

```text
environment
domain
framework_version
release_hash
check list
exact release/config bundle where applicable
```

A partial manifest for another exact spec must not be merged.

## Credential model

Source-controlled runner configuration stores only env-var **names**.

Runtime-only values include:

```text
Fabric access token
control-plane database URL
ordinary Warehouse database URL
Admin Warehouse database URL
```

Secret-bearing values must not enter retained plan/report/manifest artifacts.

## Preflight

`integration-run-preflight` validates exact config/spec identity, physical bindings, runtime env-var presence, and mutating-check authorization without copying secret values into retained output.

The first real provider stage should be read-only.

## Item smoke

Command surface:

```text
integration-item-smoke-run
```

Purpose:

```text
Fabric token path
workspace/item authorization
returned item identity
```

HTTP success with mismatched item identity is not PASS.

## Control-plane certification

Command surface:

```text
integration-control-plane-certify-run
```

Requires:

```text
selected production-eligible control-plane profile
runtime DB URL
explicit conformance-write authorization
complete external refs for enterprise controls expected by certification contract
no silent schema migration
```

External areas such as IAM/network/restore/HA/monitoring/retention/governance remain separately evidenced.

## Pipeline approved run

Command surface:

```text
integration-pipeline-run
```

Prerequisite manifest must contain:

```text
FABRIC_ITEM_READ PASS
CONTROL_PLANE_CERTIFICATION PASS
selected FABRIC_PIPELINE_RUN NOT_RUN
```

Before remote execution the runner verifies exact release/config/dataset identity and production control-plane eligibility.

PASS requires:

```text
provider terminal success
+ exact durable framework DatasetDispatchOutcome for generated child dataset_run_id
+ outcome status SUCCEEDED
```

Provider `Completed` + missing child outcome = FAIL.

## Copy Job / Spark approved capture

Command surface:

```text
integration-capture-run
```

Prerequisites:

```text
FABRIC_ITEM_READ PASS
CONTROL_PLANE_CERTIFICATION PASS
selected Copy/Spark check NOT_RUN
exact release/config/dataset identity
fingerprinted customer extension artifact
explicit capture authorization
```

### Copy Job

```text
engine = FABRIC_COPY_JOB
progress authority = FABRIC_NATIVE
framework source bounds/runtime parameters rejected
```

Provider success is insufficient; post-run item-specific observation must yield verified native evidence and `CaptureReceipt`.

### Spark Job Definition

```text
progress authority = FRAMEWORK
WATERMARK/CDC approved capture requires frozen upper bound
runtime source bounds/parameters require bounded spark_execution_data extension
```

The compiled unit used for capture proof must be capture-only; a combined Spark unit that also applies/publishes/finalizes cannot masquerade as capture-only evidence.

### Capture PASS

Requires:

```text
provider terminal success
+ approved post-run observation
+ FabricNativeRunEvidence
+ verified CaptureReceipt
+ exact workspace/item/job/root correlation
```

## Normal Warehouse approved run

Command surface:

```text
integration-warehouse-run
```

Prerequisites:

```text
FABRIC_ITEM_READ PASS
CONTROL_PLANE_CERTIFICATION PASS
selected FABRIC_WAREHOUSE_TARGET_COMMIT NOT_RUN
exact release/config/dataset identity
fingerprinted bounded warehouse mutation extension
production-eligible control plane
runtime control + Warehouse DB URLs
pre-existing framework marker table
explicit Warehouse execution authorization
```

Framework owns:

```text
target-operation identity/journal
SQL transaction
framework target-side marker
commit probe
reconciliation
PASS/FAIL
```

Customer mutation extension receives the existing SQLAlchemy `Connection` and must not commit/write marker/mutate journal/decide PASS.

Normal deterministic success path may simulate framework ACK loss after successful target transaction return:

```text
EXECUTE
-> target mutation + marker commit
-> UNKNOWN
-> marker COMMITTED
-> SUCCEEDED
-> later SKIP_SUCCEEDED
```

This is recovery-contract evidence, not a real network/driver disconnect claim.

## Ambiguous-COMMIT fault drill

Command surface:

```text
integration-warehouse-fault-drill-run
```

Separate check kind:

```text
FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL
```

Prerequisite manifest must contain:

```text
FABRIC_ITEM_READ PASS
CONTROL_PLANE_CERTIFICATION PASS
FABRIC_WAREHOUSE_TARGET_COMMIT PASS
selected fault-drill check NOT_RUN
```

Both mutation-extension and fault-injector artifacts must be exact-release fingerprinted.

Fault injection has separate explicit authorization.

Committed-ambiguity PASS requires all:

```text
fault armed with durable identity
execute_atomic actually raises provider/driver exception
fault disarmed before recovery probe
fault verify says triggered
arm/verify fault identity matches
marker probe = COMMITTED
journal = SUCCEEDED
later claim = SKIP_SUCCEEDED
safe retained report exists
```

False-positive guards:

```text
normal transaction return -> FAIL
injector triggered=true but no observed execution exception -> FAIL
fault identity mismatch -> FAIL
exception + absent marker -> UNRESOLVED / UNKNOWN unless independent absence proof runs
```

## Optional exact-session termination recovery

This path is integrated into the approved fault runner but is **not** a second way to PASS the committed-fault check.

Configuration requires:

```text
warehouse_admin_database_url_env_var
```

with an env-var name distinct from the ordinary Warehouse DB URL env-var name.

Run recipe must explicitly enable:

```text
enable_session_termination_recovery=true
```

Runtime/CLI must separately authorize:

```text
--allow-warehouse-session-termination
```

Fault injection permission does not grant Admin/KILL permission.

Admin URL value may only be read after:

```text
actual execution exception
exact target session binding captured
fault disarmed
fault verified
fault identity matched
initial marker probe UNRESOLVED
journal UNKNOWN
```

The certifier then requires exact session identity, live open transaction, Admin KILL, exact session disappearance, and post-KILL marker reread.

If safe absence is proven:

```text
UNKNOWN -> NOT_COMMITTED
retry_eligible = true
no automatic retry in same runner
fault-drill result remains FAIL because COMMITTED was not proven
```

If certifier remains unresolved, one final plain marker probe may recognize a marker that appeared during the race; absence itself is not inferred.

## Strict merge

Command surface:

```text
integration-evidence-merge
```

Rules:

```text
NOT_RUN = absence
one substantive result + NOT_RUNs -> retain substantive result
identical substantive duplicates -> allowed
different substantive reruns -> conflict
no latest/PASS/FAIL precedence
no output clobber on conflict/failed certification requirement
```

Final gate:

```text
integration-evidence-validate --require-certified
```

## Release evidence discipline

A green approved-runner CI test proves runner/fail-closed behavior only.

Live evidence labels require retained exact-candidate provider/database execution.
