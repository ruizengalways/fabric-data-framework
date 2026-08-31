# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-08-31
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
feature_freeze: true
candidate_status: not_frozen
code_baseline:
  pull_request: 88
  merge_sha: 1632aefe8c1fd71098200c434a1648d0385f4967
  milestone: exact-candidate representative business-path evidence contract and producer
  pr_ci_actions: 33346419772
  main_ci_actions: 33346470401
  tests: 717
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  business_path_contract: success
  candidate_business_path_workflow_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  candidate_capable_main_artifact:
    selected_as_frozen_candidate: false
    workflow_run_id: 33346470401
    workflow_run_attempt: 1
    candidate_git_sha: 1632aefe8c1fd71098200c434a1648d0385f4967
    wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    wheel_inner_sha256: 9c813a2c23344c55409ac5f4f7e879d4515196987835bee6473d54ff3a1e027f
    artifact_id: 9742145456
    artifact_archive_digest: sha256:ab394a89fb9a5873b7f2969635bbc03e72715027be3279fdc07267cdaac87c37
    artifact_expires_at: 2026-11-29T01:04:50Z
release_readiness_artifact:
  artifact_id: 9742148687
  artifact_archive_digest: sha256:7489241d2cb14b008b4d6a6e2f644764f2eb0f4e3431bc70fdec6a0d48cada37
  artifact_expires_at: 2026-09-14T01:05:12Z
external_producer_gaps:
  framework_integration_evidence: .github/workflows/candidate-integration-evidence.yml
  customer_business_path_inputs: .github/workflows/candidate-business-path-inputs.yml
documentation_model:
  human: docs/human
  machine: docs/machine
  examples: examples
```

## Release decision

`0.4.0` remains **UNRELEASED**, feature-frozen, not release-allowed, and without a selected/frozen exact candidate. Ordinary CI deliberately provides no complete release proof and no certified live integration manifest, so the readiness contract still reports 15 required blockers and `release_ready=false`.

PR #88 is the current merged engineering baseline. Main run `33346470401` independently re-proved Python 3.11/3.13, exact wheel build and fail-closed readiness with **717 tests**. It produced a candidate-capable wheel for source SHA:

```text
1632aefe8c1fd71098200c434a1648d0385f4967
```

with exact inner wheel SHA256:

```text
9c813a2c23344c55409ac5f4f7e879d4515196987835bee6473d54ff3a1e027f
```

That wheel is **not frozen** and has no live Fabric certification attached. GitHub's artifact archive digest remains transport metadata and is never interchangeable with the exact inner wheel SHA256.

## Merged release system through PR #88

Merged + main-CI-proven portable contracts now include:

```text
main CI exact wheel candidate identity
strict partial ReleaseReadinessProofBundle merge
candidate-release-proofs exact static/customer producer
representative five-gate business-path evaluator + approved runner
explicit Pipeline rerun projection from certified integration evidence
candidate-business-path-evidence exact-candidate producer workflow
separate framework-wheel and customer/domain release identities
candidate-certification retained-evidence aggregation
exact-byte release promotion without rebuild
```

The highest claim for these surfaces is **IMPLEMENTED + CI PROVEN**. This is not a claim that any live Fabric evidence has been collected.

## Business-path evidence contract

The five required non-integration live gates are now owned by merged framework code:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

Canonical surfaces:

```text
src/fabric_data_framework/evidence/business_path_evidence.py
  typed five-gate evaluator; sole readiness PASS authority

src/fabric_data_framework/evidence/business_path_driver.py
  bounded mutating fixture/fault driver; receipt has no PASS/status field

src/fabric_data_framework/evidence/business_path_plan.py
  exact five-gate certification plan; canonical project-relative paths only

src/fabric_data_framework/evidence/approved_business_path_runner.py
  preflight -> driver -> read-only observation -> approved Pipeline -> evaluator -> cleanup

src/fabric_data_framework/evidence/integration_evidence_rerun.py
  explicit Pipeline rerun projection from separately retained certified integration evidence

src/fabric_data_framework/cli/business_path.py
  removable CLI leaf: candidate-business-path-run

.github/workflows/candidate-business-path-evidence.yml
  exact-candidate live producer; cannot author readiness PASS JSON directly
```

The runner reuses `execute_approved_pipeline`; it does not create a second Fabric execution truth path. Provider/native state and durable framework `DatasetDispatchOutcome` remain distinct, so a provider-reported `Completed` result can still correspond to framework `FAILED`.

## Critical exact-identity invariant

PR #88 permanently separates two SHA256 identities that must never be conflated:

```text
framework candidate source identity
  candidate_git_sha

framework candidate binary identity
  exact inner candidate wheel SHA256
  = IntegrationEvidenceSpec.release_hash
  = IntegrationEvidenceManifest.release_hash
  = ApprovedIntegrationRunnerConfig.framework_artifact_sha256 in exact-candidate mode

customer/domain release identity
  ReleaseManifest.bundle.release_hash
  = IntegrationEvidenceSpec.domain_release_hash
  = IntegrationEvidenceManifest.domain_release_hash
  = ApprovedIntegrationRunnerConfig.release_hash
```

The framework wheel SHA256 and customer/domain release hash are independent and must never be assumed equal. Historical development/reference runner configs may use the old single-hash form only where `domain_release_hash` is absent; exact 0.4 candidate evidence must bind both identities.

## Business-path PASS boundary

The framework evaluator may return PASS only from independently sourced retained facts:

```text
exact source-controlled scenario expectation
+ exact fingerprinted mutating driver receipt
+ read-only target/progress/history semantic observation
+ framework-owned Pipeline provider/native report
+ durable framework DatasetDispatchOutcome
-> framework evaluator
-> one ReleaseReadinessProofResult
```

Invalid shortcuts remain forbidden:

```text
Fabric Completed -> PASS
observer says pass -> PASS
driver setup succeeded -> PASS
workflow writes PASS JSON -> PASS
in-memory apply test -> live PASS
```

Gate requirements include:

```text
FULL / SCD1 / SCD2:
  Fabric Completed
  framework SUCCEEDED
  final target/progress equals source-controlled semantic expectation
  state actually changed

SCD2 additionally:
  expected history digest
  exactly one current row per business key

retry.idempotency:
  first attempt framework FAILED + retryable + expected error code
  target/progress unchanged after failed attempt
  second attempt Fabric Completed + framework SUCCEEDED
  same execution-plan hash, distinct dataset_run_id
  expected final state

reconciliation.fail_closed:
  Fabric Completed
  framework FAILED with expected reconciliation error
  target/progress unchanged
```

Cleanup is part of the evidence transaction: cleanup failure prevents publication even if semantic evaluation had already computed PASS.

## Explicit rerun rule

Business-path proof deliberately reruns the approved Pipeline. Automatic reuse/rerun of a substantive integration result remains forbidden. The business-path command first requires a **fully certified exact integration manifest**, then creates a new non-certified prerequisite where only the selected `FABRIC_PIPELINE_RUN` check is explicitly projected from PASS back to `NOT_RUN`. All other retained prerequisite results and both release identities remain unchanged; the original certified manifest is immutable.

Release-system ordering is therefore:

```text
exact main candidate
  -> certified candidate integration evidence
  -> representative business-path explicit Pipeline reruns
  -> candidate-release-proofs static + business-path merge
  -> candidate-certification over release proofs + same certified integration evidence
  -> exact-byte promotion
```

## Current release blockers

The merged business-path producer is intentionally unable to generate a successful live artifact until trusted upstream/domain producers and real environment inputs exist:

```text
.github/workflows/candidate-integration-evidence.yml        NOT YET IMPLEMENTED
fabric-customer candidate-business-path-inputs.yml          NOT YET IMPLEMENTED
fabric-customer exact five-gate certification plan          NOT YET RETAINED
fabric-customer driver/observer extension artifacts         NOT YET RETAINED
enterprise Fabric credentials/environment evidence          NOT YET RETAINED
exact candidate freeze                                      NOT YET
certified readiness artifact                                NOT YET PRODUCED
ordinary release-readiness blockers                         15
```

Real evidence still missing includes Fabric identity/authorization, production control-plane certification, approved Pipeline/Copy/Spark, representative FULL/SCD1/SCD2, retry and reconciliation drills, Warehouse target+marker, real ambiguous COMMIT recovery, and capacity/IAM/network/DR/monitoring/governance evidence. Debezium/Kafka remains optional unless explicitly promoted into 0.4 GA scope.

## Next engineering order

```text
1. implement candidate-integration-evidence producer around existing approved runners
2. implement fabric-customer candidate-business-path-inputs + exact plan/driver/observer artifacts
3. validate both producer paths without fabricating live PASS
4. only then select/freeze one exact 0.4 main candidate
5. collect certified integration evidence for exact framework wheel + exact domain release
6. run five representative live business-path gates
7. run candidate-release-proofs
8. candidate-certification must reach blockers=[]
9. release workflow promotes the same certified wheel bytes
10. only then publish immutable v0.4.0
11. then migrate fabric-customer from v0.3.0/exact-SHA-next to immutable 0.4.0
```

## Evidence vocabulary boundary

Current merged-main claim is **IMPLEMENTED + CI PROVEN** through PR #88 for portable release/certification contracts. Do not use `FABRIC PROVEN`, `FABRIC WAREHOUSE PROVEN`, `PRODUCTION DB PROVEN`, or `RELEASE PROVEN` for 0.4 until retained approved real-service evidence and immutable release artifacts exist.
