# 0.4 release-candidate readiness

`0.4.0` is still development source. A green build, retained wheel, or Fabric-reported `Completed` state is not enough to publish it.

## Freeze rule

Once one main-CI wheel is selected as the candidate, stop adding product features. Only release blockers, certification defects, compatibility defects, evidence defects, and documentation defects may change it. Any code fix creates a new candidate SHA and requires new exact-candidate evidence.

No exact 0.4 candidate is frozen yet.

## Release chain

The required evidence order is:

```text
main CI builds exact candidate bytes
        ↓
prepare exact customer/domain release inputs
        ↓
collect fully certified Fabric integration evidence
        ↓
run the five representative live business-path drills
        ↓
re-verify static/customer proof and merge the live business-path proof
        ↓
candidate certification validates all retained evidence
        ↓
framework-release promotes the exact certified bytes
```

There is no release-time wheel rebuild.

The integration evidence comes before the representative business-path reruns because those reruns reuse already-proven Fabric identity, control-plane, and Pipeline prerequisites. They do not silently overwrite the original certified integration evidence.

## Keep the two SHA256 identities separate

A candidate involves two independent release hashes:

```text
framework wheel SHA256
  identifies the exact framework binary

customer ReleaseManifest.bundle.release_hash
  identifies the exact customer/domain DatasetConfig release
```

They are not expected to be equal.

For exact candidate integration evidence:

```text
IntegrationEvidence.release_hash
  = framework wheel SHA256

IntegrationEvidence.domain_release_hash
  = customer ReleaseManifest.bundle.release_hash
```

The customer approved-run config keeps `release_hash` as the domain release hash and adds `framework_artifact_sha256` for the exact framework wheel.

## Exact candidate wheel

Main CI retains:

```text
fabric_data_framework-<version>-py3-none-any.whl
SHA256SUMS
CANDIDATE.json
```

`CANDIDATE.json` binds package version, source SHA, main Actions run ID/attempt, wheel filename, and exact inner wheel SHA256. Do not use GitHub's uploaded ZIP/archive digest as wheel identity.

The latest **merged-main** candidate-capable baseline is PR #88:

```text
source SHA       1632aefe8c1fd71098200c434a1648d0385f4967
main CI          33346470401
tests            717
wheel SHA256     9c813a2c23344c55409ac5f4f7e879d4515196987835bee6473d54ff3a1e027f
artifact ID      9742145456
```

That wheel is candidate-capable only. It is not frozen and has no live certification.

PR #90 contains newer integration-producer release-blocker work. Its PR CI run `33347382522` passed Python 3.11/3.13, wheel build and fail-closed readiness with **727 tests**. Until it is merged and independently re-proven on main, it is PR-CI proven only and is not a candidate to freeze.

## Step 1 — certified integration evidence

The integration template is source controlled at:

```text
release/0.4.0/integration-evidence-template.json
```

`.github/workflows/candidate-integration-evidence.yml` is implemented in PR #90 and **PR CI PROVEN / PENDING MERGE**. It is a manual protected-environment exact-candidate producer around the existing approved runner commands.

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

The producer authenticates the exact framework source/main CI run/wheel bytes and the exact customer SHA/input-producer run before any live mutation. It also verifies the exact customer `ReleaseManifest`, DatasetConfig bundle, source-controlled run recipes, and fingerprinted extension wheels.

The customer approved integration config owns physical bindings. For the representative `fabric.pipeline` binding, PR #90 adds an optional `dataset_id` field and the candidate producer requires it. This keeps the representative business dataset choice in the customer/domain repo rather than as an ad hoc framework workflow input.

The workflow stages approved partial manifests and finishes only if:

```text
integration-evidence-merge --require-certified
integration-evidence-validate --require-certified
```

both succeed. It may read final PASS statuses for re-validation, but it must not construct `IntegrationEvidenceCheckResult(PASS)` itself.

A successful artifact must be bound to:

```text
exact framework candidate wheel SHA256
exact customer/domain ReleaseManifest.bundle.release_hash
environment
domain
framework version
all required integration check identities
```

General live mutation authorization and Admin Warehouse session-termination authorization are separate controls. The Admin/KILL path is never enabled implicitly by ordinary mutation authorization.

No current candidate has certified integration evidence. PR #90 proves only the portable workflow contract; real protected credentials and exact customer inputs are still required.

## Step 2 — representative live business paths

The framework business-path evidence contract is merged and main-CI proven from PR #88 for:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

The customer/domain release owns an exact five-gate certification plan, scenarios, bounded fixture/fault driver, and read-only state observer. All plan/config/plugin bytes must be fingerprinted in the exact customer `ReleaseManifest`.

The framework separates responsibilities:

```text
driver     prepares deterministic fixture/fault state; cannot say PASS
observer   reads target/history/progress semantic facts; cannot say PASS
Pipeline   provides Fabric native status + durable framework outcome
framework  evaluates the source-controlled expectations and decides PASS/FAIL
```

The business-path command is:

```bash
fabric-framework candidate-business-path-run \
  --runner-config evidence/runner-config.json \
  --integration-spec evidence/integration-spec.json \
  --certified-integration-evidence evidence/integration-evidence.json \
  --release-manifest evidence/customer-release-manifest.json \
  --config-dir config/datasets \
  --scenario config/certification/full.replace.scenario.json \
  --driver-config config/certification/full.replace.driver.json \
  --candidate-sha "${CANDIDATE_SHA}" \
  --artifact-sha256 "${CANDIDATE_WHEEL_SHA256}" \
  --pipeline-check-id fabric.pipeline \
  --evidence-reference "<durable retained run reference>" \
  --report-output evidence/full.replace.report.json \
  --proof-output evidence/full.replace.proof.json \
  --allow-pipeline-execution \
  --allow-scenario-mutation
```

The command first verifies exact identities and prerequisites. It then creates a new explicit Pipeline-rerun prerequisite from the separately retained certified integration manifest; the original certified manifest remains unchanged.

For FULL/SCD1/SCD2, Fabric must be `Completed`, the durable framework outcome must be `SUCCEEDED`, and final target/progress semantic state must match the scenario expectation. SCD2 additionally verifies history and the one-current-row invariant.

For retry, the first attempt must fail retryably without changing target/progress, and the second attempt must succeed with the same execution-plan hash and a distinct dataset run.

For reconciliation fail-closed, Fabric must reach `Completed` while the durable framework outcome is `FAILED`, and target/progress must remain unchanged. This directly proves that provider success cannot override framework semantic failure.

Cleanup failure blocks publication even if the earlier evaluator had calculated PASS.

`.github/workflows/candidate-business-path-evidence.yml` is merged and main-CI proven as a fail-closed producer contract. It still cannot create a real PASS artifact because the exact customer input producer and retained certified integration evidence do not yet exist.

## Step 3 — non-integration proof merge

`.github/workflows/candidate-release-proofs.yml` is merged and main-CI proven from PR #87. It directly creates PASS only for facts it re-verifies itself:

```text
source.tests
wheel.integrity
customer.compatibility
```

It never directly marks the five live business-path gates PASS. Instead it requires a successful exact-candidate business-path producer artifact and strict-merges that with its static/customer proof.

The reusable merge is:

```bash
fabric-framework release-proofs-merge \
  --spec release/0.4.0/readiness-spec.json \
  --input evidence/static-release-proofs.json \
  --input evidence/business-path-release-proofs.json \
  --output evidence/release-proofs.json
```

Different substantive reruns conflict—even two different PASS records. There is no latest-wins, PASS-wins, or timestamp precedence.

Final `release-proofs-<candidate SHA>` is retained only when exactly all eight non-integration gates are present and PASS.

### Domain identity hardening before freeze

The current `ReleaseReadinessProofBundle` machine identity binds framework version, candidate source SHA and exact wheel SHA256. Certified integration evidence independently binds the customer/domain release hash.

Before choosing/finally freezing a 0.4 candidate, the final release-proof/candidate-certification path must machine-bind the same `domain_release_hash` so a complete proof bundle cannot be paired with a different customer/domain release merely because references happen to look compatible. This is a release blocker.

## Step 4 — candidate certification

After complete release proof and the same certified integration manifest exist for the exact candidate:

```bash
fabric-framework candidate-certify \
  --readiness-spec release/0.4.0/readiness-spec.json \
  --integration-template release/0.4.0/integration-evidence-template.json \
  --candidate-sha "${CANDIDATE_SHA}" \
  --artifact-sha256 "${CANDIDATE_WHEEL_SHA256}" \
  --environment DEV \
  --domain customer \
  --proofs evidence/release-proofs.json \
  --integration-evidence evidence/integration-evidence.json \
  --output build/release-readiness.json
```

Certification fails unless exact candidate/wheel/domain identity matches, retained proof text is safe, integration evidence is fully certified, all 15 required readiness gates PASS, `release_ready=true`, and `blockers=[]`.

## Step 5 — exact promotion

`framework-release` consumes the exact candidate run and successful candidate-certification artifact. It re-verifies source/version/run/wheel identity and zero blockers before creating the immutable tag at the exact candidate SHA and publishing the already-certified wheel and evidence assets.

## Current state

```text
public release                     v0.3.0
0.4 source                         feature-frozen / unreleased
release allowed                    no
candidate                          not yet frozen
ordinary required blockers         15
strict partial proof merge         merged + CI proven (#86)
candidate-release-proofs           merged + main CI proven (#87)
candidate-business-path-evidence   merged + main CI proven contract (#88); no live run
candidate-integration-evidence     PR CI proven / pending merge (#90); no live run
customer business-path inputs      not yet implemented / not retained
release-proof/domain binding       required before candidate freeze
certified artifact                 not yet produced
```

No current state above is a live Fabric certification claim. Finish PR #90 merge/main verification, then implement the exact `fabric-customer` business-path/integration input producer and the release-proof/domain identity hardening. Only after those producer paths are ready should an exact 0.4 candidate be selected/frozen.
