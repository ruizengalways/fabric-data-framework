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
  pull_request: 87
  merge_sha: 5a2edffe5930e9b8a2a79f66f4580ca4d9df2b4e
  milestone: exact-candidate non-integration release-proof producer
  pr_ci_actions: 33343182775
  main_ci_actions: 33343223496
  tests: 670
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  release_proof_merge_contract: success
  candidate_release_proofs_workflow_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  candidate_capable_main_artifact:
    selected_as_frozen_candidate: false
    workflow_run_id: 33343223496
    workflow_run_attempt: 1
    candidate_git_sha: 5a2edffe5930e9b8a2a79f66f4580ca4d9df2b4e
    wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    wheel_inner_sha256: e6c0cda41ebdb3c356c087a79a3e6b0fe8b353867b8c06c0e89d4381fb23db35
    artifact_id: 9741187950
    artifact_archive_digest: sha256:b2461b7336bc4097fe37e30d1d23bffe98d564b6fc4f3bdcb791ee1d970149ba
    artifact_expires_at: 2026-11-28T23:59:09Z
feature_branch:
  branch: codex/business-path-evidence
  capability: representative live business-path evidence contract and producer workflow
  state: implemented_ci_pending
  live_gate_scope:
    - full.replace
    - watermark.scd1
    - watermark.scd2
    - retry.idempotency
    - reconciliation.fail_closed
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

PR #87 is now the exact merged engineering baseline. Main run `33343223496` produced a candidate-capable wheel for source SHA `5a2edffe5930e9b8a2a79f66f4580ca4d9df2b4e` with inner SHA256:

```text
e6c0cda41ebdb3c356c087a79a3e6b0fe8b353867b8c06c0e89d4381fb23db35
```

That wheel is **not frozen** and has no live Fabric certification attached. GitHub's artifact archive digest is transport metadata and is never interchangeable with the inner wheel SHA256.

## Merged release system through PR #87

Merged/proven portable contracts now include:

```text
main CI exact wheel candidate identity
strict partial ReleaseReadinessProofBundle merge
candidate-release-proofs exact static/customer producer
candidate-certification retained-evidence aggregation
exact-byte release promotion without rebuild
```

`candidate-release-proofs.yml` directly creates PASS only for evidence it re-verifies itself:

```text
source.tests
wheel.integrity
customer.compatibility
```

It cannot directly create PASS for the five representative live business-path gates. Those must come from `candidate-business-path-evidence.yml` and survive strict merge.

## Current business-path feature branch

`codex/business-path-evidence` is implementing the missing live business-path producer. Until its PR CI/merge succeeds, the highest claim is **IMPLEMENTED / CI PENDING**, not CI proven and not Fabric proven.

Current branch surfaces:

```text
src/fabric_data_framework/evidence/business_path_evidence.py
  typed five-gate evaluator; sole readiness PASS authority

src/fabric_data_framework/evidence/business_path_driver.py
  bounded mutating fixture/fault driver contract; no PASS/status field

src/fabric_data_framework/evidence/business_path_plan.py
  exact five-gate source-controlled certification plan

src/fabric_data_framework/evidence/approved_business_path_runner.py
  driver -> read-only observation -> approved Pipeline -> framework evaluator -> cleanup

src/fabric_data_framework/evidence/integration_evidence_rerun.py
  explicit Pipeline rerun projection from separately retained certified integration evidence

src/fabric_data_framework/cli/business_path.py
  removable presentation leaf: candidate-business-path-run

.github/workflows/candidate-business-path-evidence.yml
  exact-candidate live producer; cannot author readiness PASS JSON directly
```

The runner reuses `execute_approved_pipeline`; it does not create a second Fabric execution truth path. Provider/native state and durable framework `DatasetDispatchOutcome` are retained separately, so `Fabric Completed` can still result in framework `FAILED`.

## Critical exact-identity invariant

A release-significant bug was found while wiring real producer inputs: one hash had previously been used for two different identities. The current branch separates them explicitly.

```text
framework candidate source identity
  candidate_git_sha

framework candidate binary identity
  candidate wheel SHA256
  = IntegrationEvidenceSpec.release_hash
  = IntegrationEvidenceManifest.release_hash
  = ApprovedIntegrationRunnerConfig.framework_artifact_sha256 in candidate mode

customer/domain release identity
  ReleaseManifest.bundle.release_hash
  = IntegrationEvidenceSpec.domain_release_hash
  = IntegrationEvidenceManifest.domain_release_hash
  = ApprovedIntegrationRunnerConfig.release_hash
```

These two SHA256 values are independent and must never be assumed equal. Existing development/reference runner configs remain compatible with the historical single-hash form only when `domain_release_hash` is absent. Exact 0.4 candidate evidence must supply both identities.

## Business-path PASS boundary

The five readiness gates are evaluated only from independently sourced facts:

```text
exact source-controlled scenario expectation
+ exact fingerprinted mutating driver receipt
+ read-only target/progress semantic observation
+ framework-owned Pipeline native/provider report
+ durable framework outcome
-> framework evaluator
-> one ReleaseReadinessProofResult
```

Rules include:

```text
FULL / SCD1 / SCD2:
  Fabric Completed
  framework SUCCEEDED
  final target/progress equals expected source-controlled semantic digest
  state must actually change

SCD2 additionally:
  history digest equals expectation
  exactly one current row per business key

retry.idempotency:
  first attempt framework FAILED + retryable + expected failure code
  target/progress unchanged after failed attempt
  second attempt Fabric Completed + framework SUCCEEDED
  same execution-plan hash, distinct dataset_run_id
  expected final state reached

reconciliation.fail_closed:
  Fabric Completed
  framework FAILED with expected reconciliation error
  target/progress unchanged
```

Cleanup failure blocks publication even if the evaluator had already computed PASS.

## Explicit rerun rule

Business-path evidence is a deliberate Pipeline rerun, but existing approved Pipeline evidence correctly rejects automatic reruns of a check that already has a substantive result. Therefore the business-path command requires a **fully certified exact integration manifest first** and creates a new non-certified prerequisite where only the selected Pipeline check is explicitly reset to `NOT_RUN`. Other certified prerequisites remain unchanged; the original manifest is immutable.

This establishes the release-system ordering:

```text
exact main candidate
  -> certified candidate integration evidence
  -> representative business-path reruns
  -> candidate-release-proofs static + business-path merge
  -> candidate-certification over release proofs + same certified integration evidence
  -> exact-byte promotion
```

## Current blockers

The branch cannot create live business-path evidence today because required upstream/downstream domain artifacts do not yet exist:

```text
.github/workflows/candidate-integration-evidence.yml        NOT YET IMPLEMENTED
fabric-customer candidate-business-path-inputs.yml          NOT YET IMPLEMENTED
fabric-customer exact five-gate certification plan          NOT YET RETAINED
fabric-customer driver/observer extension artifacts         NOT YET RETAINED
enterprise Fabric credentials/environment evidence          NOT YET RETAINED
```

Real evidence still missing includes Fabric identity/authorization, production control-plane certification, approved Pipeline/Copy/Spark, representative FULL/SCD1/SCD2, retry and reconciliation drills, Warehouse target+marker, real ambiguous COMMIT recovery, and capacity/IAM/network/DR/monitoring/governance evidence. Debezium/Kafka remains out of 0.4 required scope unless explicitly promoted.

## Next engineering order

```text
1. PR + full CI for codex/business-path-evidence
2. merge only if identity split, runner, workflow and docs contracts are green
3. implement candidate-integration-evidence producer around existing approved runners
4. implement fabric-customer candidate-business-path-inputs and exact driver/observer/plan artifacts
5. only then select/freeze an exact 0.4 candidate
6. collect certified integration evidence for exact framework wheel + exact domain release
7. run five representative live business-path gates
8. run candidate-release-proofs
9. candidate-certification must reach blockers=[]
10. release workflow promotes exact certified bytes
11. only then publish immutable v0.4.0
12. then migrate fabric-customer from v0.3.0/exact-SHA-next to immutable 0.4.0
```

## Evidence vocabulary boundary

Current merged-main claim is **IMPLEMENTED + CI PROVEN** through PR #87 for portable release contracts. Current business-path branch is **IMPLEMENTED / CI PENDING**. Do not use `FABRIC PROVEN`, `FABRIC WAREHOUSE PROVEN`, `PRODUCTION DB PROVEN`, or `RELEASE PROVEN` for 0.4 until retained real-service evidence and immutable release artifacts exist.
