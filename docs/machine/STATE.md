# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-08-31
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
feature_freeze: true
candidate_status: not_frozen
merged_engineering_baseline:
  pull_request: 90
  merge_sha: 7e12a320e73aa06f3e80f57e3deed14a6cc7add0
  milestone: exact-candidate approved integration-evidence producer
  final_pr_ci_actions: 33349005817
  main_ci_actions: 33349064335
  tests: 728
merged_docs_baseline:
  commit_sha: 689bc1097474b26866af8675e32592e4cf65fa1f
  milestone: merged integration-producer documentation checkpoint
current_release_blocker_pr:
  pull_request: 92
  milestone: exact customer/domain release hash binding across final proof/certification/promotion
  first_implementation_head: f07c464fefaec2f1533a67549382549613823253
  first_pr_ci_actions: 33356673686
  first_pr_ci_tests: 732
  status: PR_CI_PROVEN_PENDING_MERGE
ordinary_readiness:
  release_ready: false
  required_blockers: 15
live_fabric_evidence_retained: false
customer_input_contract:
  feature_pr_10_merge: cda90f1c02fc9606aa64d2d1bd13f2ab89628aab
  checkpoint_pr_11_merge: 31f3f506bc1c16a445652de2ad48fe512cfec10a
  customer_main_ci: 33353960915
  customer_certification_contract_ci: 33353960906
  released_runtime_pin: fabric-data-framework==0.3.0
  actual_selected_candidate_input_artifact_retained: false
```

## Release decision

`0.4.0` remains **UNRELEASED**, feature-frozen, not release-allowed and without a selected/frozen exact candidate. Ordinary CI still deliberately has no complete release proof or live certified integration manifest, so `release_ready=false` with 15 required blockers remains correct.

No current claim is `FABRIC PROVEN`, `PRODUCTION DB PROVEN`, `FABRIC WAREHOUSE PROVEN`, or `RELEASE PROVEN`.

## Merged-main baseline

The latest merged engineering baseline is PR #90:

```text
merge SHA      7e12a320e73aa06f3e80f57e3deed14a6cc7add0
final PR CI    33349005817
main CI        33349064335
tests          728
wheel SHA256   dbc9b0cbcc73598c94ae67c4798ba9eefdf6ba203a6169ff61088a9d1757c3b8
selected       false
```

The current main documentation checkpoint is `689bc1097474b26866af8675e32592e4cf65fa1f`. Neither commit is a frozen candidate.

## Customer certification-input contract is now merged

The former external producer gap is closed at the **contract/source** level in `fabric-customer`:

```text
.github/workflows/candidate-business-path-inputs.yml
feature PR #10 merge        cda90f1c02fc9606aa64d2d1bd13f2ab89628aab
checkpoint PR #11 merge     31f3f506bc1c16a445652de2ad48fe512cfec10a
customer main CI            33353960915 SUCCESS
certification-contract CI    33353960906 SUCCESS
```

This does not mean an input artifact has been produced for a selected candidate. Customer production/runtime dependency remains exactly `fabric-data-framework==0.3.0` until immutable v0.4.0 exists.

Customer source intentionally still fail-closes on real-environment prerequisites such as reviewed control-plane external evidence and a real Warehouse ambiguous-COMMIT fault controller.

## Permanent dual-hash invariant

The framework and customer release identities are independent:

```text
IntegrationEvidence.release_hash
  = exact framework candidate wheel SHA256

IntegrationEvidence.domain_release_hash
  = exact customer/domain ReleaseManifest.bundle.release_hash

ApprovedIntegrationRunnerConfig.framework_artifact_sha256
  = exact framework wheel SHA256

ApprovedIntegrationRunnerConfig.release_hash
  = exact customer/domain release hash
```

These hashes must never be assumed equal.

PR #92 extends the same customer/domain identity through the non-integration readiness chain:

```text
ReleaseReadinessProofBundle.domain_release_hash
ReleaseReadinessReport.domain_release_hash
```

## PR #92 release-blocker hardening

PR #92 is **PR CI PROVEN / PENDING MERGE**. First implementation head `f07c464fefaec2f1533a67549382549613823253` passed framework CI `33356673686` with:

```text
Python 3.11 tests       SUCCESS
Python 3.13 tests       SUCCESS — 732 passed
build-wheel             SUCCESS
release-readiness       SUCCESS — intentionally release_ready=false
```

The hardening does four things:

```text
1. business-path proof packaging binds evaluator output to exact Customer ReleaseManifest.bundle.release_hash
2. strict ReleaseReadinessProofBundle merge requires identical non-empty domain_release_hash for candidate partial proofs
3. candidate-certify rejects proof/integration evidence unless both carry the same exact domain_release_hash
4. framework-release re-checks report/proofs/integration domain_release_hash equality before creating the tag
```

`candidate-release-proofs.yml` cannot accept `domain_release_hash` as a workflow input. It derives the hash only after authenticating the retained business-path artifact's `customer-release-manifest.json` and exact customer SHA.

## What is still not proven

```text
exact candidate freeze                         NOT YET
real customer input artifact for selected SHA  NOT YET RETAINED
certified integration evidence                 NOT YET PRODUCED
five business-path live proofs                 NOT YET RETAINED
complete release proof                         NOT YET RETAINED
certified readiness artifact                   NOT YET PRODUCED
immutable v0.4.0                               NOT YET PUBLISHED
customer production dependency migration       NOT ALLOWED YET
```

## Next engineering order

```text
1. finish PR #92 final-head CI
2. squash merge #92 and independently verify framework main
3. checkpoint exact merged SHA/main run/test count in STATE/HISTORY/CAPABILITIES/IMPLEMENTATION_MAP
4. replace customer live placeholders only with reviewed real enterprise bindings/evidence
5. select/freeze one NEW exact framework main candidate
6. produce exact customer certification input artifact for that candidate
7. run candidate-integration-evidence in protected real Fabric/control/Warehouse environment
8. run five candidate-business-path-evidence drills
9. run candidate-release-proofs with the same framework + domain identities
10. candidate-certify must reach blockers=[]
11. promote exact certified wheel bytes
12. only then migrate fabric-customer production runtime from v0.3.0 to immutable v0.4.0
```

## Evidence vocabulary boundary

Portable contract CI proves implementation and fail-closed behavior only. Do not infer live provider truth from green ordinary CI or from the existence of producer workflows.
