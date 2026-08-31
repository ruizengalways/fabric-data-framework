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
feature_branch_release_blocker:
  branch: codex/candidate-integration-evidence
  pull_request: 90
  capability: exact-candidate approved integration-evidence producer
  state: implemented_ci_pending
  output_if_real_checks_pass: integration-evidence-<candidate SHA>
  direct_pass_construction: forbidden
  required_live_checks:
    - fabric.item.read
    - control.cert
    - fabric.pipeline
    - fabric.copy
    - fabric.spark
    - warehouse.commit
    - warehouse.ambiguous_commit
remaining_external_gap:
  customer_business_path_inputs: fabric-customer/.github/workflows/candidate-business-path-inputs.yml
```

## Release decision

`0.4.0` remains **UNRELEASED**, feature-frozen, not release-allowed, and without a selected/frozen candidate. Ordinary CI still has 15 required readiness blockers. No live Fabric proof or certified 0.4 evidence has been retained.

The merged baseline remains PR #88 / main SHA `1632aefe8c1fd71098200c434a1648d0385f4967`, independently verified by main CI `33346470401` with 717 tests. Its wheel SHA256 is `9c813a2c23344c55409ac5f4f7e879d4515196987835bee6473d54ff3a1e027f`; that artifact is candidate-capable only, not frozen/certified.

## PR #90 feature-branch boundary

`.github/workflows/candidate-integration-evidence.yml` is implemented on `codex/candidate-integration-evidence` and is **CI PENDING** until PR #90 reaches a final green run and merge/main checkpoint.

The producer is orchestration only. It reuses existing approved commands rather than creating a second provider truth path:

```text
integration-item-smoke-run
integration-control-plane-certify-run
integration-pipeline-run
integration-capture-run              # Copy
integration-capture-run              # Spark
integration-warehouse-run
integration-warehouse-fault-drill-run
integration-evidence-merge --require-certified
integration-evidence-validate --require-certified
```

It cannot create a successful artifact unless real protected-environment credentials and exact customer-owned certification inputs exist. It contains no code that constructs `IntegrationEvidenceCheckResult(PASS)`.

## Exact producer identity and provenance

The workflow must authenticate all of:

```text
exact candidate source SHA
successful exact main framework CI run
exact candidate wheel bytes / CANDIDATE.json / SHA256SUMS
exact fabric-customer git SHA
successful fixed-path customer input producer run
exact customer ReleaseManifest + DatasetConfig bundle
exact source-controlled Copy/Spark/Warehouse/fault recipes
exact fingerprinted customer extension wheels
```

It preserves the PR #88 dual identity invariant:

```text
IntegrationEvidence.release_hash
  = exact framework candidate wheel SHA256

IntegrationEvidence.domain_release_hash
  = exact customer/domain ReleaseManifest.bundle.release_hash

ApprovedIntegrationRunnerConfig.framework_artifact_sha256
  = framework wheel SHA256

ApprovedIntegrationRunnerConfig.release_hash
  = customer/domain release hash
```

These hashes are independent and must never be assumed equal.

## Customer-owned representative Pipeline binding

PR #90 adds optional `dataset_id` to `IntegrationCheckPhysicalBinding`. Exact candidate integration certification requires it for the `fabric.pipeline` binding so the customer/domain repo owns the representative business dataset. The framework workflow must not accept the business dataset as an ad hoc dispatch input.

Existing non-Pipeline and legacy/reference bindings remain valid without `dataset_id`.

## Staged fail-closed integration order

The candidate integration producer runs in this order:

```text
1. authenticate candidate/customer inputs + extension bytes
2. materialize exact integration spec with framework + domain hashes
3. full credential-name/preflight validation
4. real Fabric item read
5. real production control-plane certification
6. strict merge -> base prerequisites
7. real approved Pipeline
8. real approved Copy
9. real approved Spark
10. real Warehouse target+marker commit
11. strict merge Warehouse PASS into fault prerequisites
12. real ambiguous-COMMIT fault/recovery drill
13. strict final merge --require-certified
14. exact identity + safe-retained-output verification
15. upload only the certified artifact
```

The workflow requires explicit `authorize_live_mutations=true`. Admin-level Warehouse session termination is separately controlled by `authorize_warehouse_session_termination`; it never follows implicitly from general live-mutation authorization.

## Current blockers

```text
candidate-integration-evidence workflow       FEATURE BRANCH IMPLEMENTED / CI PENDING (#90)
fabric-customer candidate-business-path-inputs NOT YET IMPLEMENTED
real protected Fabric/control/Warehouse inputs NOT YET RETAINED
exact candidate freeze                         NOT YET
certified integration evidence                 NOT YET PRODUCED
five business-path live proofs                 NOT YET RETAINED
complete release proof                         NOT YET RETAINED
certified readiness artifact                   NOT YET PRODUCED
ordinary readiness blockers                    15
```

One additional hardening item is tracked before candidate freeze: the final non-integration `ReleaseReadinessProofBundle` currently binds candidate source/wheel but does not yet carry a machine `domain_release_hash`; the release-proof and certified integration domain identity must be tied together before the candidate can be frozen/promoted.

## Next engineering order

```text
1. finish PR #90 CI/docs/merge/main verification
2. implement fabric-customer candidate-business-path-inputs with exact integration recipes, plan and bounded extensions
3. hard-bind domain_release_hash across final release proof/candidate certification
4. only then select/freeze one exact main candidate
5. produce real certified integration evidence
6. run five representative business-path drills
7. run candidate-release-proofs
8. candidate-certification must reach blockers=[]
9. exact-byte release promotion
10. only then publish immutable v0.4.0
```

## Evidence vocabulary boundary

Merged-main claims remain **IMPLEMENTED + CI PROVEN** only through PR #88/#89. PR #90 is feature-branch implementation until final CI and merge/main verification. Do not use `FABRIC PROVEN`, `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, or `RELEASE PROVEN` for 0.4 yet.
