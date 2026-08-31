# BUSINESS-PATH EVIDENCE CONTRACT

This file defines what can satisfy the five representative live non-integration readiness gates for `0.4.0`. Reference/in-memory apply tests are useful executable specifications, but they cannot satisfy these live release gates.

The portable business-path contract was merged in PR #88 and is main-CI proven. The exact candidate integration-evidence producer was merged in PR #90 and is also main-CI proven. No successful exact-candidate live Fabric business-path evidence has been retained yet.

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

PR #88 business-path provenance:

```text
merge SHA   1632aefe8c1fd71098200c434a1648d0385f4967
PR CI       33346419772
main CI     33346470401
tests       717
```

PR #90 integration-producer provenance:

```text
merge SHA   7e12a320e73aa06f3e80f57e3deed14a6cc7add0
final PR CI 33349005817
main CI     33349064335
tests       728
```

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

Invalid shortcuts remain forbidden:

```text
Fabric Completed -> PASS
customer observer says pass -> PASS
driver setup succeeded -> PASS
in-memory apply unit test -> live readiness PASS
workflow writes PASS JSON directly
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

Every business-path run also binds customer/domain git SHA, exact DatasetConfig bundle hash, business-path plan bytes, scenario bytes, driver-config bytes, and driver/observer extension wheel bytes through the exact `ReleaseManifest`.

## Source-controlled certification plan

Canonical contract:

```text
src/fabric_data_framework/evidence/business_path_plan.py
```

A customer/domain certification plan contains exactly one entry for each of the five gates. Paths use canonical POSIX project-relative syntax and remain inside the exact project root. Absolute paths, traversal, `./` aliases and backslash/noncanonical forms fail closed.

Each entry selects:

```text
gate_id
scenario_path
driver_config_path
pipeline_check_id
```

The plan contains no secrets or environment-local connection values.

## Driver / observer boundary

Canonical driver contract:

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

A driver may prepare deterministic source fixtures or controlled failure conditions. It cannot return readiness PASS/FAIL, replace provider/framework outcome truth, claim target/progress observation, or skip cleanup silently. `BusinessPathDriverReceipt` has no PASS/status field.

Controlled observer extension group:

```text
fabric_data_framework.business_path_observers
```

The observer is read-only from the readiness system's perspective. It returns bounded target/history/progress semantic facts and safe retained references; it cannot return PASS or framework/provider status.

## Pipeline evidence boundary

Canonical execution owner:

```text
src/fabric_data_framework/evidence/approved_pipeline_runner.py
```

`ApprovedPipelineEvidenceReport` retains Fabric-native terminal status separately from durable framework `DatasetDispatchOutcome`. Thus a valid reconciliation-failure observation may be:

```text
remote_status    = Completed
framework_status = FAILED
error_code       = RECONCILIATION_FAILED
```

Provider success is intentionally insufficient for framework semantic success.

## Explicit Pipeline rerun

Business-path certification reruns a previously certified Pipeline path. Approved provider runners reject silent reruns when substantive evidence already exists.

Canonical projection:

```text
src/fabric_data_framework/evidence/integration_evidence_rerun.py
```

Input is a fully certified exact integration manifest. Projection preserves framework wheel identity, customer/domain release identity and all other retained results; changes only the selected Pipeline check from PASS to NOT_RUN; creates a new evidence ID/hash; and never mutates the original certified artifact.

## Gate rules

### FULL -> REPLACE / WATERMARK -> SCD1

PASS requires one successful Pipeline attempt, Fabric terminal `Completed`, durable framework `SUCCEEDED`, exact target row count/digest, exact progress digest, and a semantic state change from baseline.

### WATERMARK -> SCD2

In addition, final history digest must match the source-controlled expectation and exactly one current row per business key must hold. SCD2 cannot manufacture history the capture path did not observe.

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

A provider failure does not prove this gate; the point is to prove provider success cannot override semantic reconciliation failure.

## Approved runner order

Canonical runner:

```text
src/fabric_data_framework/evidence/approved_business_path_runner.py
```

Before driver mutation it verifies explicit scenario/Pipeline authorization, exact candidate source/wheel identities, exact domain release identity, exact DatasetConfig bundle, exact certified integration prerequisites, selected Pipeline NOT_RUN projection, retained item/control PASS prerequisites, customer-owned Pipeline physical binding, runtime env-var presence, and fingerprinted scenario/driver/extension artifacts.

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
return proof only after cleanup succeeds
```

Cleanup failure prevents proof publication.

## Candidate business-path workflow

Workflow:

```text
.github/workflows/candidate-business-path-evidence.yml
```

State is **MERGED + MAIN CI PROVEN** as an exact-candidate executor/aggregator contract. It requires trusted upstream evidence from the framework main candidate artifact, `candidate-integration-evidence`, and the customer `candidate-business-path-inputs` producer.

It authenticates framework source/wheel provenance, customer git/release provenance, exact plan/scenario/driver/plugin bytes, and both SHA256 identity domains before running the five approved paths. It strict-merges exactly five one-gate proof bundles and retains `business-path-release-proofs-<candidate SHA>` only when membership and PASS requirements hold.

No such live artifact has yet been retained.

## Current evidence boundary

```text
typed evaluator / driver / plan / runner / business-path workflow = MERGED + MAIN CI PROVEN (#88)
candidate-integration-evidence producer                            = MERGED + MAIN CI PROVEN (#90); NO LIVE RUN
actual Fabric business-path PASS artifacts                         = NOT RETAINED
customer candidate-business-path-inputs producer                   = NOT YET IMPLEMENTED
customer live driver/observer artifacts                            = NOT YET RETAINED
exact candidate                                                    = NOT FROZEN
release-proof/domain hash machine binding                          = REQUIRED BEFORE FREEZE
release readiness                                                  = 15 REQUIRED BLOCKERS
```

No implementation in this file upgrades `0.4.0` to Fabric-proven or release-ready by itself.
