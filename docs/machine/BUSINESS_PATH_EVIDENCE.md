# BUSINESS-PATH EVIDENCE CONTRACT

This file defines what can satisfy the five representative live non-integration readiness gates for `0.4.0`. Reference/in-memory apply tests are useful executable specifications, but they cannot satisfy these live release gates.

## Gate ownership

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

Canonical evaluator:

```text
src/fabric_data_framework/evidence/business_path_evidence.py
```

Only the framework evaluator returns `ReleaseReadinessProofResult(PASS)`. Customer extensions cannot return readiness status.

## Independent fact sources

A valid proof combines four independently bounded inputs:

```text
1. ApprovedBusinessPathScenario
   source-controlled expected semantic result

2. BusinessPathDriverReceipt
   mutating fixture/fault preparation receipt
   no PASS/status field

3. BusinessPathStateObservation
   read-only target/history/progress semantic facts

4. ApprovedPipelineEvidenceReport
   framework-owned provider/native status
   + exact durable DatasetDispatchOutcome
```

The framework evaluates those facts and only then projects one readiness proof result.

This separation prevents these invalid shortcuts:

```text
Fabric Completed -> PASS                         FORBIDDEN
customer observer says pass -> PASS             FORBIDDEN
driver says fixture succeeded -> PASS           FORBIDDEN
in-memory apply unit test -> live readiness PASS FORBIDDEN
workflow writes PASS JSON directly               FORBIDDEN
```

## Exact release identity

There are two independent SHA256 identities plus the source SHA:

```text
framework source:
  candidate_git_sha

framework binary:
  exact inner candidate wheel SHA256
  = IntegrationEvidence.release_hash
  = candidate proof artifact_sha256
  = ApprovedIntegrationRunnerConfig.framework_artifact_sha256 in candidate mode

customer/domain release:
  ReleaseManifest.bundle.release_hash
  = IntegrationEvidence.domain_release_hash
  = ApprovedIntegrationRunnerConfig.release_hash
```

The framework binary SHA256 and domain release hash must never be assumed equal.

Every business-path run also binds:

```text
customer/domain git SHA through ReleaseManifest.bundle.domain_git_sha
exact DatasetConfig bundle hash through ReleaseManifest.bundle.config_bundle_hash
scenario bytes through ReleaseManifest.artifact_sha256
business-path plan bytes through ReleaseManifest.artifact_sha256
driver-config bytes through ReleaseManifest.artifact_sha256
driver/observer extension wheel bytes through ReleaseManifest.artifact_sha256
```

## Source-controlled certification plan

Canonical contract:

```text
src/fabric_data_framework/evidence/business_path_plan.py
```

A customer/domain certification plan must contain exactly one entry for each of the five gates. Every path must be project-relative and remain inside the exact project root.

Each entry selects:

```text
gate_id
scenario_path
driver_config_path
pipeline_check_id
```

The plan does not contain secrets or environment-local connection values.

## Driver boundary

Canonical contract:

```text
src/fabric_data_framework/evidence/business_path_driver.py
```

Driver phases:

```text
PREPARE_BASELINE
PREPARE_ATTEMPT_1
PREPARE_ATTEMPT_2   retry only
CLEANUP
```

A driver may prepare deterministic source fixtures or controlled failure conditions. It may not:

```text
return PASS/FAIL readiness status
read or modify framework proof JSON
replace framework Pipeline outcome truth
skip cleanup silently
claim target/progress state
```

`BusinessPathDriverReceipt` contains only exact scenario/gate/dataset/phase identity and safe retained references.

Driver execution requires a separate explicit `--allow-scenario-mutation` authorization.

## Observer boundary

Controlled extension group:

```text
fabric_data_framework.business_path_observers
```

The observer is read-only from the readiness system's perspective. It returns bounded semantic facts:

```text
target semantic SHA256
target row count
progress semantic SHA256
optional SCD2 history semantic SHA256
optional one-current-row-per-business-key invariant
retained safe evidence references
```

It cannot return PASS or framework/provider status.

## Pipeline evidence boundary

Canonical provider/framework execution remains:

```text
src/fabric_data_framework/evidence/approved_pipeline_runner.py
```

`ApprovedPipelineEvidenceReport` keeps these facts separate:

```text
remote_status          Fabric-native terminal status
framework_status       durable DatasetDispatchOutcome status
retryable              framework durable outcome fact
error_code             framework durable outcome fact
execution_plan_hash    exact plan identity
framework/native run IDs and retained evidence references
```

Therefore this is valid evidence:

```text
remote_status    = Completed
framework_status = FAILED
error_code       = RECONCILIATION_FAILED
```

Provider success is necessary for the reconciliation fail-closed drill but intentionally insufficient for framework success.

## Explicit Pipeline rerun

Business-path certification reruns a previously certified Pipeline path. Approved provider runners correctly reject silent reruns when a substantive result already exists.

Canonical explicit projection:

```text
src/fabric_data_framework/evidence/integration_evidence_rerun.py
```

Input must be a fully certified exact `IntegrationEvidenceManifest`. The projection:

```text
preserves all exact identity fields
preserves all other integration results
changes only the selected Pipeline check from PASS to NOT_RUN
creates a new evidence_id/manifest hash
references the original certified manifest hash
never mutates the original certified artifact
is intentionally no longer certified
```

The business-path runner still independently requires PASS item-read and control-plane prerequisites and explicit Pipeline mutation authorization.

## Gate rules

### FULL -> REPLACE

PASS requires:

```text
one Pipeline attempt
Fabric remote status = Completed
framework outcome = SUCCEEDED
final target semantic SHA256 = scenario expectation
final row count = scenario expectation
final progress semantic SHA256 = scenario expectation
final semantic state differs from baseline
```

### WATERMARK -> SCD1

Same success boundary as FULL/REPLACE, with the source-controlled scenario defining the expected current-state result and expected progress/checkpoint identity.

### WATERMARK -> SCD2

PASS additionally requires:

```text
final history semantic SHA256 = scenario expectation
one_current_row_per_business_key = true
```

SCD2 apply cannot manufacture history that the source/capture path did not observe; scenario design must remain truthful to capture fidelity.

### retry.idempotency

PASS requires two distinct real Pipeline attempts using the same execution-plan hash:

```text
attempt 1:
  framework FAILED
  retryable = true
  error_code = exact scenario failure code
  target/history/progress state unchanged from baseline

attempt 2:
  Fabric Completed
  framework SUCCEEDED
  expected final semantic state reached
```

The failed first attempt may not advance target/progress state.

### reconciliation.fail_closed

PASS proves the provider/framework distinction directly:

```text
Fabric remote status = Completed
framework outcome = FAILED
error_code = exact reconciliation failure code
target/history/progress state unchanged from baseline
scenario's hypothetical successful target differs from baseline
```

A provider failure does not prove this gate because the point is to demonstrate that provider success cannot override semantic reconciliation failure.

## Approved runner order

Canonical runner:

```text
src/fabric_data_framework/evidence/approved_business_path_runner.py
```

Before any driver mutation it verifies:

```text
explicit scenario + Pipeline authorization
exact candidate SHA/wheel SHA shape
runner/domain/framework identities
framework wheel SHA identity
customer domain release hash identity
exact DatasetConfig bundle hash
exact integration prerequisite manifest
selected Pipeline check = NOT_RUN
retained PASS item-read prerequisite
retained PASS control-plane prerequisite
Pipeline physical binding
required runtime env-variable presence
fingerprinted scenario/driver/extension artifacts
```

Execution order:

```text
prepare baseline
observe BEFORE
prepare attempt 1
approved Pipeline attempt 1
[retry only] observe failed attempt -> prepare attempt 2 -> approved Pipeline attempt 2
observe AFTER_FINAL_ATTEMPT
framework evaluator
CLEANUP in finally
return report/proof only after cleanup succeeds
```

Cleanup failure prevents a PASS artifact from being returned.

## Candidate business-path workflow

Workflow owner:

```text
.github/workflows/candidate-business-path-evidence.yml
```

It is an exact-candidate aggregator/executor, not a PASS author. It requires trusted upstream evidence from:

```text
framework candidate main CI artifact
candidate-integration-evidence workflow
fabric-customer candidate-business-path-inputs workflow
```

The workflow verifies framework source/wheel provenance, customer git/release provenance, exact plan/scenario/driver/plugin bytes, and both SHA256 identity domains before running the five approved paths.

It then requires exactly five one-gate partial proof bundles, strict-merges them with `release-proofs-merge`, verifies exact gate membership and all PASS, and only then retains:

```text
business-path-release-proofs-<candidate SHA>
```

## Current evidence boundary

As of this feature branch:

```text
typed evaluator / driver / plan / runner / workflow = IMPLEMENTED / CI PENDING
actual Fabric business-path PASS artifacts           = NOT RETAINED
candidate-integration-evidence producer              = NOT YET IMPLEMENTED
customer business-path-input producer                = NOT YET IMPLEMENTED
customer live driver/observer artifacts              = NOT YET RETAINED
```

No implementation in this file upgrades `0.4.0` to Fabric-proven or release-ready by itself.
