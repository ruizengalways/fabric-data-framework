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

The latest merged candidate-capable baseline is PR #88:

```text
source SHA       1632aefe8c1fd71098200c434a1648d0385f4967
main CI          33346470401
tests            717
wheel SHA256     9c813a2c23344c55409ac5f4f7e879d4515196987835bee6473d54ff3a1e027f
artifact ID      9742145456
```

That wheel is candidate-capable only. It is not frozen and has no live certification.

## Step 1 — certified integration evidence

The integration template is source controlled at:

```text
release/0.4.0/integration-evidence-template.json
```

The remaining `.github/workflows/candidate-integration-evidence.yml` must execute the approved exact-candidate surfaces for:

```text
Fabric identity/item read
production control-plane certification
Pipeline
Copy
Spark
Warehouse target+marker commit
real ambiguous-COMMIT recovery
```

It must retain a fully certified manifest bound to the exact framework wheel SHA and exact customer/domain release hash. Generic PASS JSON cannot substitute for these checks.

This producer is not yet implemented, so no current candidate has certified integration evidence.

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

`.github/workflows/candidate-business-path-evidence.yml` is now merged and main-CI proven as a fail-closed producer contract. It still cannot create a real PASS artifact today because it depends on two missing trusted producers: framework integration evidence and exact customer business-path inputs. A green workflow contract is not live Fabric evidence.

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

Certification fails unless exact candidate/wheel identity matches, retained proof text is safe, integration evidence is fully certified, all 15 required readiness gates PASS, `release_ready=true`, and `blockers=[]`.

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
candidate-integration-evidence     not yet implemented
customer business-path inputs      not yet implemented / not retained
certified artifact                 not yet produced
```

No current state above is a live Fabric certification claim. The next release-blocking implementation is the trusted integration evidence producer, followed by the exact customer business-path input producer. Only after both producer paths are ready should an exact 0.4 candidate be selected/frozen.
