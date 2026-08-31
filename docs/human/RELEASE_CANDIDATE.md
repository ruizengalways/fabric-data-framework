# 0.4 release-candidate readiness

`0.4.0` is still development source. A green build, retained wheel, or Fabric-reported `Completed` state is not enough to publish it.

## Freeze rule

Once one main-CI wheel is explicitly selected as the candidate, stop adding product features. Only release blockers, certification defects, compatibility defects, evidence defects and documentation defects may change it. Any code fix creates a new candidate SHA and requires new exact-candidate evidence.

No exact 0.4 candidate is frozen yet.

## Release chain

Required order:

```text
main CI builds exact candidate bytes
        ↓
prepare exact customer/domain certification inputs
        ↓
collect fully certified Fabric integration evidence
        ↓
run the five representative live business-path drills
        ↓
re-verify static/customer proof and merge live business-path proof
        ↓
candidate certification validates all retained evidence
        ↓
framework-release promotes the exact certified bytes
```

There is no release-time wheel rebuild.

Integration evidence comes first because representative business-path reruns reuse separately retained Fabric identity, control-plane and Pipeline prerequisites. The original certified integration manifest remains immutable.

## Keep framework and domain identities separate

A candidate involves two independent SHA256 identities:

```text
framework wheel SHA256
  identifies the exact framework binary

customer ReleaseManifest.bundle.release_hash
  identifies the exact customer/domain release
```

They are not expected to be equal.

Exact candidate integration evidence binds:

```text
IntegrationEvidence.release_hash
  = framework wheel SHA256

IntegrationEvidence.domain_release_hash
  = customer ReleaseManifest.bundle.release_hash
```

The customer approved-run config keeps `release_hash` as the domain release hash and uses `framework_artifact_sha256` for the exact framework wheel.

## Latest candidate-capable main artifact

PR #90 is now merged and independently re-proven on main:

```text
source SHA       7e12a320e73aa06f3e80f57e3deed14a6cc7add0
final PR CI      33349005817
main CI          33349064335
tests            728
wheel SHA256     dbc9b0cbcc73598c94ae67c4798ba9eefdf6ba203a6169ff61088a9d1757c3b8
artifact ID      9742969993
```

Main CI retains:

```text
fabric_data_framework-0.4.0-py3-none-any.whl
SHA256SUMS
CANDIDATE.json
```

`CANDIDATE.json` binds package version, source SHA, main Actions run ID/attempt, wheel filename and exact inner wheel SHA256. GitHub's uploaded artifact ZIP digest is not the wheel identity.

This wheel is **candidate-capable only**. It is not selected/frozen and has no live certification.

## Step 1 — exact customer/domain input artifact

The next implementation blocker is the customer-owned producer:

```text
fabric-customer/.github/workflows/candidate-business-path-inputs.yml
```

This producer must package source-controlled WHAT, not execute Fabric or decide PASS. It must retain the exact customer/domain release manifest, DatasetConfig bundle, approved integration runner config, integration run recipes, business-path plan/scenarios, and fingerprinted bounded extension wheels needed by the framework evidence workflows.

The framework production/runtime dependency in `fabric-customer` remains `fabric-data-framework==0.3.0` until immutable 0.4 exists. Certification tooling may use an exact 0.4 candidate in a separate release-evidence lane; that must not silently upgrade the released runtime dependency.

## Step 2 — certified integration evidence

The integration template is source controlled at:

```text
release/0.4.0/integration-evidence-template.json
```

`.github/workflows/candidate-integration-evidence.yml` is now **MERGED + MAIN CI PROVEN** from PR #90. It is a manual protected-environment exact-candidate producer around the existing approved runner commands.

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

The producer authenticates exact framework source/main-CI/wheel bytes and exact customer SHA/input-producer provenance before live mutation. It verifies the customer `ReleaseManifest`, DatasetConfig bundle, source-controlled run recipes and fingerprinted extension wheels.

For the representative `fabric.pipeline` binding, the customer approved integration config must carry `dataset_id`. This keeps the representative business dataset choice in the customer/domain repo rather than as an ad hoc framework workflow input.

The workflow publishes only after both:

```text
integration-evidence-merge --require-certified
integration-evidence-validate --require-certified
```

succeed. It may read final PASS statuses for re-validation, but it cannot construct `IntegrationEvidenceCheckResult(PASS)` itself.

General live mutation authorization and Admin Warehouse session-termination authorization are separate controls.

No current candidate has certified integration evidence. Merged workflow/CI proof is not a live Fabric claim.

## Step 3 — representative live business paths

The business-path evidence contract is merged and main-CI proven from PR #88 for:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

The customer/domain release owns an exact five-gate certification plan, scenarios, bounded fixture/fault driver and read-only state observer. All plan/config/plugin bytes must be fingerprinted in the exact customer `ReleaseManifest`.

Responsibilities remain separate:

```text
driver     prepares deterministic fixture/fault state; cannot say PASS
observer   reads target/history/progress facts; cannot say PASS
Pipeline   supplies Fabric native status + durable framework outcome
framework  evaluates source-controlled expectations and decides PASS/FAIL
```

The approved command is `fabric-framework candidate-business-path-run`. It first verifies exact identities and prerequisites, projects the selected Pipeline check from the separately retained fully certified integration manifest back to explicit `NOT_RUN`, then executes a new Pipeline run without mutating the original certified manifest.

For FULL/SCD1/SCD2, provider terminal success must agree with durable framework `SUCCEEDED` and exact target/progress expectations. SCD2 additionally validates history and exactly one current row per business key.

For retry, the first attempt must fail retryably without changing target/progress; the second must succeed with the same execution-plan hash and a distinct dataset run.

For reconciliation fail-closed, Fabric may reach `Completed` while durable framework outcome is `FAILED`; target/progress must remain unchanged. This proves provider success cannot override framework semantic failure.

Cleanup failure blocks proof publication.

`.github/workflows/candidate-business-path-evidence.yml` is merged + main-CI proven as a fail-closed contract, but no real business-path PASS artifact has been retained.

## Step 4 — non-integration proof merge

`.github/workflows/candidate-release-proofs.yml` is merged + main-CI proven from PR #87. It directly creates PASS only for facts it re-verifies itself:

```text
source.tests
wheel.integrity
customer.compatibility
```

The five live business-path gates arrive from the separate business-path producer. `release-proofs-merge` rejects contradictory substantive records; there is no latest-wins or PASS-wins rule.

### Domain identity hardening still required

The current `ReleaseReadinessProofBundle` machine identity binds framework version, candidate source SHA and exact wheel SHA256, while certified integration evidence separately binds `domain_release_hash`.

Before choosing/finally freezing a candidate, complete release proof and candidate certification must also machine-bind the same exact `domain_release_hash`. A proof bundle for one customer/domain release must not be pairable with integration evidence from another domain release based only on human-readable references.

This is the next framework release hardening after the customer input producer.

## Step 5 — candidate certification

After complete release proof and fully certified integration evidence exist for the same exact framework candidate and domain release, `fabric-framework candidate-certify` and `.github/workflows/candidate-certification.yml` re-authenticate identities and retained evidence.

Certification must fail unless:

```text
exact framework source/wheel identity matches
exact customer/domain release identity matches
retained proof text is credential-safe
integration evidence is fully certified
all 15 required readiness gates PASS
release_ready = true
blockers = []
```

Candidate certification does not execute Fabric, rebuild bytes or publish a release.

## Step 6 — exact promotion

`framework-release` consumes the successful exact candidate-certification artifact. It re-verifies source/version/run/wheel/evidence identity before creating the immutable tag at the exact candidate SHA and publishing the already-certified wheel and evidence assets.

No release-time rebuild exists.

## Current state

```text
public release                     v0.3.0
0.4 source                         feature-frozen / unreleased
release allowed                    no
candidate                          not yet frozen
ordinary required blockers         15
strict partial proof merge         merged + main CI proven (#86)
candidate-release-proofs           merged + main CI proven (#87)
candidate-business-path-evidence   merged + main CI proven (#88); no live run
candidate-integration-evidence     merged + main CI proven (#90); no live run
customer business-path inputs      not yet implemented / not retained
release-proof/domain binding       required before candidate freeze
certified artifact                 not yet produced
```

No current state above is a live Fabric certification claim. The next engineering sequence is customer input producer first, then domain-release proof hardening, and only then explicit candidate selection/freeze and real evidence collection.
