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
  pull_request: 90
  merge_sha: 7e12a320e73aa06f3e80f57e3deed14a6cc7add0
  milestone: exact-candidate approved integration-evidence producer
  final_pr_ci_actions: 33349005817
  main_ci_actions: 33349064335
  tests: 728
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  integration_producer_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  live_fabric_evidence_retained: false
  candidate_capable_main_artifact:
    selected_as_frozen_candidate: false
    workflow_run_id: 33349064335
    workflow_run_attempt: 1
    candidate_git_sha: 7e12a320e73aa06f3e80f57e3deed14a6cc7add0
    wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    wheel_inner_sha256: dbc9b0cbcc73598c94ae67c4798ba9eefdf6ba203a6169ff61088a9d1757c3b8
    artifact_id: 9742969993
    artifact_archive_digest: sha256:5a5a2351394bc30b6aa4908477401ac226d0fd35d3eb32f0ab4b4823eed22562
    artifact_expires_at: 2026-11-29T01:55:47Z
release_readiness_artifact:
  artifact_id: 9742972694
  artifact_archive_digest: sha256:08204da444f3920cbfb08df60a4d6b0c8b903d5c460419849ccfd3d158abc822
  artifact_expires_at: 2026-09-14T01:56:06Z
external_producer_gap:
  customer_business_path_inputs: fabric-customer/.github/workflows/candidate-business-path-inputs.yml
release_hardening_gap:
  domain_release_hash_binding: required_before_candidate_freeze
```

## Release decision

`0.4.0` remains **UNRELEASED**, feature-frozen, not release-allowed, and without a selected/frozen exact candidate. Ordinary CI deliberately has no complete release proof or live certified integration manifest, so the readiness contract remains `release_ready=false` with 15 required blockers.

PR #90 is the current merged engineering baseline. Final PR CI `33349005817` and independent main push CI `33349064335` both succeeded. Main re-proved Python 3.11/3.13, exact wheel build, fail-closed readiness and the integration-producer contract with **728 tests**.

The latest candidate-capable main wheel is bound to source SHA:

```text
7e12a320e73aa06f3e80f57e3deed14a6cc7add0
```

and exact inner wheel SHA256:

```text
dbc9b0cbcc73598c94ae67c4798ba9eefdf6ba203a6169ff61088a9d1757c3b8
```

Artifact ID `9742969993` is retained through `2026-11-29T01:55:47Z`. It is **candidate-capable only**. It is not selected/frozen, certified, or release-proven. GitHub's artifact archive digest is transport metadata and is never interchangeable with the inner wheel SHA256.

## Merged integration producer — PR #90

`.github/workflows/candidate-integration-evidence.yml` is now **MERGED + MAIN CI PROVEN** as a portable fail-closed workflow contract. This does not mean a live Fabric run has happened.

The producer reuses the existing approved commands rather than creating a second provider truth path:

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

A successful artifact is impossible unless the exact customer inputs, protected runtime credentials and real approved provider/database checks all succeed. The workflow may inspect PASS from completed approved manifests for final validation, but it cannot construct `IntegrationEvidenceCheckResult(PASS)` or synthesize provider truth.

## Exact producer identity and provenance

The merged workflow authenticates all of:

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

The dual identity invariant is permanent:

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

PR #90 added optional `dataset_id` to `IntegrationCheckPhysicalBinding`. Exact candidate integration certification requires it for the `fabric.pipeline` binding, so the customer/domain repository owns the representative business dataset. The framework workflow must not choose the dataset as an ad hoc workflow input.

Existing non-Pipeline and compatibility/reference bindings remain valid without `dataset_id`.

## Staged fail-closed integration order

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

`authorize_live_mutations=true` is required for mutating certification. Admin-level Warehouse session termination remains separately controlled by `authorize_warehouse_session_termination`; general mutation authorization never implies Admin/KILL authorization.

## Current release blockers

```text
candidate-integration-evidence workflow        MERGED + MAIN CI PROVEN (#90); NO LIVE RUN
fabric-customer candidate-business-path-inputs NOT YET IMPLEMENTED
real protected Fabric/control/Warehouse inputs NOT YET RETAINED
release-proof/domain identity machine binding  REQUIRED BEFORE CANDIDATE FREEZE
exact candidate freeze                         NOT YET
certified integration evidence                 NOT YET PRODUCED
five business-path live proofs                 NOT YET RETAINED
complete release proof                         NOT YET RETAINED
certified readiness artifact                   NOT YET PRODUCED
ordinary readiness blockers                    15
```

The non-integration `ReleaseReadinessProofBundle` currently binds framework version/candidate source/wheel but does not yet carry the customer/domain `domain_release_hash`. Before candidate freeze or promotion, complete release proof and certified integration evidence must be machine-bound to the same exact domain release identity.

## Next engineering order

```text
1. implement fabric-customer candidate-business-path-inputs with exact integration recipes, business-path plan and bounded extensions
2. hard-bind domain_release_hash across final release proof/candidate certification
3. validate producer and identity contracts fail closed
4. only then select/freeze one exact main candidate
5. produce real certified integration evidence
6. run five representative business-path drills
7. run candidate-release-proofs
8. candidate-certification must reach blockers=[]
9. exact-byte release promotion
10. only then publish immutable v0.4.0
11. only after immutable v0.4.0 exists migrate fabric-customer production dependency from v0.3.0
```

## Evidence vocabulary boundary

Current merged-main claim is **IMPLEMENTED + CI PROVEN** through PR #90 for portable release/certification contracts. Do not use `FABRIC PROVEN`, `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, or `RELEASE PROVEN` for 0.4 until retained approved real-service evidence and immutable release artifacts exist.
