# BUSINESS-PATH EVIDENCE CONTRACT

This file defines what can satisfy the five representative live non-integration readiness gates for `0.4.0`. Reference/in-memory apply tests are executable specifications only; they cannot satisfy live release gates.

Portable business-path semantics were merged in PR #88. The exact candidate integration-evidence producer was merged in PR #90. Customer certification-input packaging is merged in `fabric-customer` PR #10 with checkpoint PR #11. Exact business-path/domain proof binding is merged and main-CI proven in framework PR #92. No successful exact-candidate live Fabric business-path evidence has been retained yet.

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

Regression provenance:

```text
PR #88:
  merge SHA   1632aefe8c1fd71098200c434a1648d0385f4967
  PR CI       33346419772
  main CI     33346470401
  tests       717

PR #90:
  merge SHA   7e12a320e73aa06f3e80f57e3deed14a6cc7add0
  final PR CI 33349005817
  main CI     33349064335
  tests       728

PR #92:
  merge SHA   d5eed17f2ec2f869b4e3a448597e6d8d600568ea
  final PR CI 33356959856
  main CI     33357032461
  tests       734
```

## Independent fact sources

A valid proof combines independently bounded inputs:

```text
1. ApprovedBusinessPathScenario
   source-controlled expected semantic result

2. BusinessPathDriverReceipt
   mutating fixture/fault preparation receipt
   no PASS/status field

3. BusinessPathStateObservation
   read-only target/history/progress semantic facts

4. ApprovedPipelineEvidenceReport
   provider/native status + durable framework DatasetDispatchOutcome

5. exact customer ReleaseManifest
   binds DatasetConfig/config/plugin/plan/scenario bytes and customer/domain release identity
```

The framework evaluates those facts and only then projects one readiness result.

Forbidden shortcuts remain:

```text
Fabric Completed -> PASS
customer observer says pass -> PASS
driver setup succeeded -> PASS
in-memory apply unit test -> live readiness PASS
workflow writes PASS JSON directly
```

## Exact release identity

There are two independent SHA256 identities plus framework source SHA:

```text
framework source:
  candidate_git_sha

framework binary:
  exact inner candidate wheel SHA256
  = IntegrationEvidence.release_hash
  = ReleaseReadinessProofBundle.artifact_sha256
  = ApprovedIntegrationRunnerConfig.framework_artifact_sha256

customer/domain release:
  ReleaseManifest.bundle.release_hash
  = IntegrationEvidence.domain_release_hash
  = ReleaseReadinessProofBundle.domain_release_hash
  = ReleaseReadinessReport.domain_release_hash
  = ApprovedIntegrationRunnerConfig.release_hash
```

Framework wheel SHA256 and customer/domain release hash must never be assumed equal.

Every business-path run also binds exact customer git SHA, DatasetConfig bundle hash, business-path plan bytes, scenario bytes, driver-config bytes and driver/observer extension wheel bytes through the customer `ReleaseManifest`.

## Source-controlled certification plan

Canonical contract:

```text
src/fabric_data_framework/evidence/business_path_plan.py
```

A customer/domain plan contains exactly one entry per required gate. Paths use canonical POSIX project-relative syntax and remain inside the exact project root. Absolute paths, traversal and noncanonical aliases fail closed.

Each entry selects:

```text
gate_id
scenario_path
driver_config_path
pipeline_check_id
```

The plan contains no secrets or environment-local connection values.

## Driver / observer boundary

Driver owner:

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

A driver may prepare deterministic source fixtures or controlled failure conditions. It cannot return readiness PASS/FAIL or claim provider/framework/target truth. `BusinessPathDriverReceipt` has no PASS/status field.

Observer extension group:

```text
fabric_data_framework.business_path_observers
```

The observer returns bounded read-only target/history/progress facts and safe retained references. It cannot return PASS or provider/framework status.

## Pipeline evidence boundary

Canonical owner:

```text
src/fabric_data_framework/evidence/approved_pipeline_runner.py
```

`ApprovedPipelineEvidenceReport` keeps Fabric-native terminal status separate from durable framework `DatasetDispatchOutcome`. A valid reconciliation-failure path may therefore be:

```text
remote_status    = Completed
framework_status = FAILED
error_code       = RECONCILIATION_FAILED
```

Provider success is intentionally insufficient for framework semantic success.

## Explicit Pipeline rerun

Business-path certification reruns a previously certified Pipeline path without mutating the original integration artifact.

Canonical projection:

```text
src/fabric_data_framework/evidence/integration_evidence_rerun.py
```

Input is a fully certified exact integration manifest. Projection preserves framework wheel identity, customer/domain release identity and all other results, changes only the selected Pipeline check from PASS to NOT_RUN, creates a new evidence identity and remains intentionally non-certified until the rerun completes.

## Gate rules

### FULL -> REPLACE / WATERMARK -> SCD1

PASS requires one successful Pipeline attempt, provider terminal `Completed`, durable framework `SUCCEEDED`, exact target row count/digest, exact progress digest and semantic state change from baseline.

### WATERMARK -> SCD2

Additionally, final history digest must match expectation and exactly one current row per business key must hold. SCD2 cannot manufacture history the capture path did not observe.

### retry.idempotency

PASS requires two distinct real Pipeline attempts with the same execution-plan hash:

```text
attempt 1:
  framework FAILED
  retryable = true
  exact expected error_code
  target/history/progress unchanged

attempt 2:
  Fabric Completed
  framework SUCCEEDED
  exact expected final semantic state
```

### reconciliation.fail_closed

PASS requires:

```text
Fabric remote status = Completed
framework outcome = FAILED
exact reconciliation error_code
target/history/progress unchanged
scenario hypothetical successful state differs from baseline
```

The point is to prove provider success cannot override semantic reconciliation failure.

## Approved runner order

Canonical runner:

```text
src/fabric_data_framework/evidence/approved_business_path_runner.py
```

Before driver mutation it verifies explicit authorization, exact candidate source/wheel identity, exact customer/domain release identity, exact DatasetConfig bundle, exact certified integration prerequisites, selected Pipeline NOT_RUN projection, item/control prerequisites, customer-owned Pipeline binding, runtime env presence and fingerprinted scenario/driver/extension artifacts.

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
publish proof only after cleanup succeeds
```

Cleanup failure prevents proof publication.

## Domain-bound proof packaging — merged PR #92

Canonical owner:

```text
src/fabric_data_framework/evidence/business_path_release_proof.py
```

The evaluator report cannot choose customer release identity. The packaging function requires both the already-evaluated report and the exact customer `ReleaseManifest`, verifies domain/framework agreement and creates:

```text
ReleaseReadinessProofBundle(
  candidate_git_sha = exact framework candidate SHA,
  artifact_sha256 = exact framework wheel SHA256,
  domain_release_hash = ReleaseManifest.bundle.release_hash,
  results = (already_evaluated_proof,)
)
```

It does not evaluate or alter PASS/FAIL.

State: **MERGED + MAIN CI PROVEN** from PR #92 (`d5eed17f2ec2f869b4e3a448597e6d8d600568ea`, main CI `33357032461`, 734 tests).

## Candidate business-path workflow

Workflow:

```text
.github/workflows/candidate-business-path-evidence.yml
```

State: **MERGED + MAIN CI PROVEN** as an exact-candidate executor/aggregator contract. It requires trusted upstream evidence from the framework main candidate artifact, `candidate-integration-evidence`, and customer `candidate-business-path-inputs` producer.

It authenticates framework source/wheel provenance, customer git/release provenance, exact plan/scenario/driver/plugin bytes and both SHA256 identity domains before running five approved paths. It strict-merges exactly five one-gate proof bundles.

The retained artifact includes:

```text
business-path-release-proofs.json
customer-release-manifest.json
certified-integration-evidence.json
per-gate reports/receipts
```

Retaining `customer-release-manifest.json` is intentional: `candidate-release-proofs.yml` re-authenticates this manifest and requires `business-path-release-proofs.json.domain_release_hash == ReleaseManifest.bundle.release_hash` before creating any static PASS bundle.

No live business-path artifact has yet been retained.

## Customer producer boundary

Customer producer contract is merged:

```text
fabric-customer/.github/workflows/candidate-business-path-inputs.yml
PR #10 merge      cda90f1c02fc9606aa64d2d1bd13f2ab89628aab
PR #11 checkpoint 31f3f506bc1c16a445652de2ad48fe512cfec10a
customer main CI  33353960915 SUCCESS
cert contract CI   33353960906 SUCCESS
```

This does not mean a selected-candidate input artifact exists. Customer production runtime remains `fabric-data-framework==0.3.0`, and real enterprise prerequisites are still intentionally fail-closed.

## Current evidence boundary

```text
typed evaluator / driver / plan / runner / business-path workflow = MERGED + MAIN CI PROVEN (#88)
candidate-integration-evidence producer                            = MERGED + MAIN CI PROVEN (#90); NO LIVE RUN
customer candidate-business-path-inputs contract                   = MERGED + CUSTOMER MAIN CI PROVEN (#10/#11)
business-path exact domain proof packaging                         = MERGED + MAIN CI PROVEN (#92)
actual selected-candidate customer input artifact                  = NOT RETAINED
actual Fabric business-path PASS artifacts                         = NOT RETAINED
exact framework candidate                                          = NOT FROZEN
release readiness                                                  = 15 REQUIRED BLOCKERS
```

No implementation in this file upgrades `0.4.0` to Fabric-proven or release-ready by itself.
