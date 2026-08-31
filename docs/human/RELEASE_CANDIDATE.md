# 0.4 release-candidate readiness

`0.4.0` is still development source. A green build, retained wheel, or Fabric-reported `Completed` state is not enough to publish it.

## Freeze rule

Once one main-CI wheel is explicitly selected as the candidate, stop adding product features. Only release blockers, certification defects, compatibility defects, evidence defects and documentation defects may change it. Any code fix creates a new candidate SHA and requires new exact-candidate evidence.

No exact 0.4 candidate is frozen yet.

## Release chain

Required order:

```text
main CI builds exact framework candidate bytes
        ↓
customer repo packages exact domain certification inputs
        ↓
collect fully certified Fabric/control/Warehouse integration evidence
        ↓
run five representative live business-path drills
        ↓
re-verify static/customer proof and strict-merge live business-path proof
        ↓
candidate certification validates all retained evidence and identities
        ↓
framework-release re-verifies and promotes the exact certified bytes
```

There is no release-time wheel rebuild.

## Keep framework and domain identities separate

A candidate involves two independent SHA256 identities:

```text
framework wheel SHA256
  identifies the exact framework binary

customer ReleaseManifest.bundle.release_hash
  identifies the exact customer/domain release
```

They are not expected to be equal and must never be assumed equal.

The machine chain now carries them separately:

```text
IntegrationEvidence.release_hash
  = framework wheel SHA256

IntegrationEvidence.domain_release_hash
  = customer ReleaseManifest.bundle.release_hash

ReleaseReadinessProofBundle.artifact_sha256
  = framework wheel SHA256

ReleaseReadinessProofBundle.domain_release_hash
  = customer ReleaseManifest.bundle.release_hash

ReleaseReadinessReport.domain_release_hash
  = customer ReleaseManifest.bundle.release_hash
```

Customer approved-run config keeps the same split:

```text
ApprovedIntegrationRunnerConfig.framework_artifact_sha256
  = framework wheel SHA256

ApprovedIntegrationRunnerConfig.release_hash
  = customer/domain release hash
```

## Current merged framework baseline

PR #90 remains the latest merged engineering baseline while PR #92 is under review:

```text
source SHA       7e12a320e73aa06f3e80f57e3deed14a6cc7add0
final PR CI      33349005817
main CI          33349064335
tests            728
wheel SHA256     dbc9b0cbcc73598c94ae67c4798ba9eefdf6ba203a6169ff61088a9d1757c3b8
```

The current main documentation checkpoint is `689bc1097474b26866af8675e32592e4cf65fa1f`.

That wheel is candidate-capable only. It is not selected/frozen and has no live certification.

## Step 1 — exact customer/domain input artifact

The customer producer is now implemented and merged:

```text
fabric-customer/.github/workflows/candidate-business-path-inputs.yml
feature PR #10 merge      cda90f1c02fc9606aa64d2d1bd13f2ab89628aab
checkpoint PR #11 merge   31f3f506bc1c16a445652de2ad48fe512cfec10a
customer main CI          33353960915 SUCCESS
cert contract CI           33353960906 SUCCESS
```

It packages source-controlled WHAT: exact customer ReleaseManifest, DatasetConfig bundle, approved runner config, run recipes, business-path plan/scenarios and fingerprinted bounded extension wheels. It does not execute Fabric or decide PASS.

This is a producer **contract** proof. No selected-candidate customer input artifact has been retained yet. The customer repo intentionally still has real-environment blockers that must be replaced only with reviewed enterprise evidence/fault infrastructure.

Customer production/runtime dependency remains `fabric-data-framework==0.3.0` until immutable v0.4.0 exists.

## Step 2 — certified integration evidence

`.github/workflows/candidate-integration-evidence.yml` is **MERGED + MAIN CI PROVEN** from PR #90. It authenticates exact framework source/main-CI/wheel bytes and exact customer SHA/input-producer provenance before live mutation.

It must execute real approved paths for:

```text
Fabric identity/item read
production control-plane certification
Pipeline
Copy
Spark
Warehouse target+marker commit
real ambiguous-COMMIT recovery
```

It publishes only after:

```text
integration-evidence-merge --require-certified
integration-evidence-validate --require-certified
```

No current candidate has certified integration evidence. Green workflow-contract CI is not a live Fabric claim.

## Step 3 — representative business paths

`.github/workflows/candidate-business-path-evidence.yml` is merged and main-CI proven from PR #88. It executes exactly:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

The customer release owns deterministic scenarios, fixture/fault driver and read-only observer. Driver and observer cannot say PASS; the framework evaluator alone decides PASS/FAIL from provider/framework/state facts.

`candidate-business-path-run` now writes proof through `business_path_release_proof.py`, which binds the evaluator result to the exact Customer `ReleaseManifest.bundle.release_hash`. The retained business-path artifact also carries `customer-release-manifest.json` so later stages can independently authenticate the same domain release.

No real five-gate artifact has been retained yet.

## Step 4 — complete non-integration proof

`.github/workflows/candidate-release-proofs.yml` creates static PASS only for facts it re-verifies:

```text
source.tests
wheel.integrity
customer.compatibility
```

The five live gates arrive from the business-path producer. `release-proofs-merge` has no latest-wins or PASS-wins rule; contradictory substantive proof conflicts.

### PR #92 domain identity hardening

PR #92 is **PR CI PROVEN / PENDING MERGE**. Its first implementation head `f07c464fefaec2f1533a67549382549613823253` passed framework CI `33356673686` with **732 passed** on Python 3.13 plus successful Python 3.11, wheel build and ordinary fail-closed readiness.

The workflow does **not** accept `domain_release_hash` as a dispatch input. It first authenticates the retained business-path artifact and `customer-release-manifest.json`, including exact customer git SHA, framework version, framework candidate/wheel identity, domain release hash and five PASS business gates. Only then can that authenticated domain hash enter the static proof.

Strict partial proof merge requires every candidate partial bundle to carry the same non-empty domain release hash.

## Step 5 — candidate certification

`fabric-framework candidate-certify` is aggregation only. PR #92 makes the exact customer/domain release identity a hard machine requirement:

```text
proofs.domain_release_hash is present
integration.domain_release_hash is present
proofs.domain_release_hash == integration.domain_release_hash
```

The resulting readiness report carries the same hash.

Certification still requires:

```text
exact framework source/wheel identity matches
retained proof text is credential-safe
integration evidence is fully certified
all 15 required readiness gates PASS
release_ready = true
blockers = []
```

It does not execute Fabric, rebuild bytes, tag, or release.

## Step 6 — exact promotion

Before `framework-release` creates the immutable tag, PR #92 requires:

```text
release-readiness.json.domain_release_hash
  == release-proofs.json.domain_release_hash
  == integration-evidence.json.domain_release_hash
```

The hash must be a lowercase 64-character SHA256. Promotion still re-verifies candidate source/version/run/wheel and uses the exact already-certified wheel bytes.

## Current state

```text
public release                     v0.3.0
0.4 source                         feature-frozen / unreleased
release allowed                    no
candidate                          not yet frozen
ordinary required blockers         15
strict partial proof merge         merged + main CI proven (#86)
candidate-release-proofs           merged baseline (#87); PR #92 domain hardening PR-CI proven
candidate-business-path-evidence   merged + main CI proven (#88); no live run
candidate-integration-evidence     merged + main CI proven (#90); no live run
customer input producer contract   merged + customer main CI proven (#10/#11)
selected-candidate input artifact  not yet retained
certified integration artifact     not yet produced
five live business-path proofs     not yet retained
certified readiness artifact       not yet produced
immutable v0.4.0                   not yet published
```

## Next sequence

```text
1. finish PR #92 final-head CI, merge, and independently verify framework main
2. replace customer live placeholders only with reviewed real enterprise bindings/evidence
3. select/freeze one NEW exact framework main candidate
4. produce exact customer certification input artifact for that candidate
5. run protected candidate-integration-evidence
6. run five candidate-business-path-evidence drills
7. run candidate-release-proofs for the same framework + domain identities
8. candidate-certify must reach blockers=[]
9. framework-release promotes exact certified wheel bytes
10. only after immutable v0.4.0 exists migrate customer runtime dependency from v0.3.0
```

No current state above is a live Fabric certification or release claim.
