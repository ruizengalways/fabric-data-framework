# MACHINE APPROVED EVIDENCE CONTRACT

This file consolidates exact approved-run behavior that used to be spread across multiple stage-specific runbooks.

## Evidence checks and certification

Important check kinds:

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

Every approved stage is bound to environment, domain, framework version, check list, exact physical binding, and exact release/config identity where applicable.

Exact 0.4 candidate mode uses two independent SHA256 identities:

```text
IntegrationEvidence.release_hash
  = exact framework candidate wheel SHA256

IntegrationEvidence.domain_release_hash
  = exact customer/domain ReleaseManifest.bundle.release_hash

ApprovedIntegrationRunnerConfig.framework_artifact_sha256
  = exact framework candidate wheel SHA256

ApprovedIntegrationRunnerConfig.release_hash
  = exact customer/domain release hash
```

A partial manifest from another exact framework artifact, domain release, environment, domain or check list must not be merged.

## Credential model

Source-controlled runner configuration stores only env-var **names**. Runtime-only values include Fabric access token, control-plane DB URL, ordinary Warehouse DB URL and Admin Warehouse DB URL.

Secret-bearing values must not enter retained plan/report/manifest artifacts.

## Preflight

`integration-run-preflight` validates exact config/spec identity, physical bindings, runtime env-var presence and mutating-check authorization without copying secret values into retained output.

The first real provider stage should be read-only.

`IntegrationCheckPhysicalBinding.dataset_id` is optional generally. Exact candidate integration certification requires it for the `fabric.pipeline` binding, so the customer/domain repo—not the framework workflow—selects the representative business dataset.

## Item smoke

Command:

```text
integration-item-smoke-run
```

PASS requires valid Fabric token/workspace/item access and exact returned item identity. HTTP success with a mismatched item is not PASS.

## Control-plane certification

Command:

```text
integration-control-plane-certify-run
```

Requires a production-eligible profile, runtime DB URL, explicit conformance-write authorization, complete external evidence references required by the certification contract, and no silent schema migration.

External IAM/network/restore/HA/monitoring/retention/governance evidence remains separate.

## Pipeline approved run

Command:

```text
integration-pipeline-run
```

Prerequisite manifest:

```text
FABRIC_ITEM_READ PASS
CONTROL_PLANE_CERTIFICATION PASS
selected FABRIC_PIPELINE_RUN NOT_RUN
```

Before execution the runner verifies exact release/config/dataset identity and production control-plane eligibility.

PASS requires:

```text
provider terminal success
+ exact durable framework DatasetDispatchOutcome for generated child dataset_run_id
+ outcome status SUCCEEDED
```

Provider `Completed` with missing/failed durable child outcome is not PASS.

## Copy / Spark approved capture

Command:

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

Copy uses Fabric-native progress authority. Spark framework-progress WATERMARK/CDC proof requires a frozen upper bound and bounded source data. Provider success alone is insufficient; approved post-run observation must yield verified native evidence and `CaptureReceipt` with exact correlation.

## Normal Warehouse approved run

Command:

```text
integration-warehouse-run
```

Requires item/control-plane PASS prerequisites, exact release/config/dataset identity, fingerprinted bounded mutation extension, runtime control + Warehouse DB URLs, pre-existing framework marker schema, and explicit Warehouse execution authorization.

Framework owns target-operation identity/journal, SQL transaction, target-side marker, commit probe, reconciliation and PASS/FAIL. Customer mutation extensions may use the existing connection but must not commit, write framework markers, mutate the journal or decide PASS.

The normal runner can prove deterministic ACK-loss recovery after transaction return; that is not evidence of a real COMMIT disconnect.

## Real ambiguous-COMMIT drill

Command:

```text
integration-warehouse-fault-drill-run
```

Prerequisites:

```text
FABRIC_ITEM_READ PASS
CONTROL_PLANE_CERTIFICATION PASS
FABRIC_WAREHOUSE_TARGET_COMMIT PASS
selected FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL NOT_RUN
```

Mutation and fault-injector artifacts must be fingerprinted. Fault injection has separate explicit authorization.

Committed-ambiguity PASS requires all of:

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

Normal transaction return, unobserved exception, fault identity mismatch or absent marker without independent no-late-commit proof cannot PASS.

## Optional exact-session termination recovery

Admin authority is separate from ordinary Warehouse execution. Runtime/CLI must separately authorize `--allow-warehouse-session-termination`; fault-injection permission does not imply Admin/KILL permission.

The Admin URL may be read only after actual execution exception, exact session binding, fault disarm/verification/identity match, initial marker `UNRESOLVED`, and journal `UNKNOWN`.

If exact-session termination independently proves safe absence:

```text
UNKNOWN -> NOT_COMMITTED
retry_eligible = true
```

The runner does not automatically retry, and absence proof does not PASS the committed-ambiguity check.

## Strict merge

Command:

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
exact framework + domain release identities must match
```

Final certification gate:

```text
integration-evidence-validate --require-certified
```

## Exact-candidate integration producer — merged PR #90

Workflow:

```text
.github/workflows/candidate-integration-evidence.yml
```

Merged-main provenance:

```text
merge SHA   7e12a320e73aa06f3e80f57e3deed14a6cc7add0
final PR CI 33349005817
main CI     33349064335
tests       728
```

State is **MERGED + MAIN CI PROVEN** as a portable fail-closed producer contract. There is no retained live Fabric integration artifact.

The producer authenticates exact framework candidate/main-CI/wheel bytes, exact fabric-customer SHA/fixed producer run, exact customer ReleaseManifest + DatasetConfig bundle, exact source-controlled Copy/Spark/Warehouse/fault recipes, and exact fingerprinted customer extension wheels.

Execution order:

```text
item read
-> control-plane certification
-> strict base prerequisite merge
-> Pipeline
-> Copy
-> Spark
-> Warehouse target+marker
-> strict fault prerequisite merge
-> real ambiguous-COMMIT drill
-> strict final merge --require-certified
-> validate --require-certified
-> exact identity + retained-secret safety check
-> upload
```

The workflow may validate PASS already produced by approved runners but must never instantiate `IntegrationEvidenceCheckResult(PASS)` or otherwise synthesize provider truth.

`authorize_live_mutations` gates mutating certification. `authorize_warehouse_session_termination` is a separate Admin-level control.

## Release evidence discipline

Green unit/contract CI proves implementation/fail-closed behavior only. Live labels require retained exact-candidate provider/database execution for the exact framework wheel and exact customer/domain release.
