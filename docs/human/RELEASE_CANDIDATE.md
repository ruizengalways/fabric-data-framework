# 0.4 release-candidate readiness

`0.4.0` is still development source. A green unit-test build, a retained wheel, or a provider-reported `Completed` state is not enough to publish it.

## Freeze rule

Once one main-CI wheel is selected as the candidate, stop adding product features. Only release blockers, certification defects, compatibility defects, evidence defects, and documentation defects may change the candidate. Any code fix creates a new candidate SHA and requires new exact-candidate evidence.

## Release chain

```text
main CI builds exact candidate bytes
        ↓
static/customer proof + live business-path proof
        ↓
strict release-proof merge
        ↓
approved Fabric integration evidence
        ↓
candidate-certification validates all retained evidence
        ↓
framework-release promotes the exact certified bytes
```

There is no release-time wheel rebuild.

## Required proof

The 15 required readiness gates cover source/package checks, exact wheel integrity, exact-candidate `fabric-customer` compatibility, Fabric identity/control-plane/Pipeline/Copy/Spark/Warehouse evidence, representative FULL→REPLACE and WATERMARK→SCD1/SCD2 paths, retry/idempotency, semantic reconciliation fail-closed behavior, and a real ambiguous-COMMIT drill.

Debezium/Kafka remains optional unless the public 0.4 GA scope explicitly promotes it to required certification.

## Exact candidate wheel

Main CI retains:

```text
fabric_data_framework-<version>-py3-none-any.whl
SHA256SUMS
CANDIDATE.json
```

`CANDIDATE.json` binds package version, source SHA, GitHub Actions run ID/attempt, wheel filename, and exact inner wheel SHA256. Do not use GitHub's uploaded ZIP/archive digest as wheel identity.

## Merge partial release proof safely

Portable/static proof and representative live business-path proof are produced independently and merged only when both bind the same exact source SHA and inner wheel SHA256:

```bash
fabric-framework release-proofs-merge \
  --spec release/0.4.0/readiness-spec.json \
  --input evidence/static-release-proofs.json \
  --input evidence/business-path-release-proofs.json \
  --output evidence/release-proofs.json
```

Omitted or `NOT_RUN` means “no proof”. A substantive `PASS`, `FAIL`, or `OUT_OF_SCOPE` is retained unchanged. Different substantive evidence for the same gate is a conflict—even two different PASS records. There is no latest-wins, PASS-wins, or timestamp precedence.

This strict merge was merged in PR #86 (`0f70e037806482c677fccae0ce9432504f2a9885`), with PR CI `33342779028`, main CI `33342806854`, and 664 tests on Python 3.13.

## Candidate release-proof workflow

`.github/workflows/candidate-release-proofs.yml` is the final non-integration proof producer. It is manual and must be dispatched at the exact candidate ref.

It takes:

```text
candidate_run_id
candidate_git_sha
candidate_wheel_sha256
customer_git_sha
business_path_evidence_run_id
```

It directly creates PASS only for facts it re-verifies itself:

```text
source.tests
wheel.integrity
customer.compatibility
```

For those gates it verifies the successful exact main-CI run and required CI jobs, re-authenticates `CANDIDATE.json` / `SHA256SUMS` / wheel bytes, installs the exact candidate wheel, checks that the selected `fabric-customer` commit is reachable from customer `main`, runs `project-validate`, and regenerates/validates the 100-table Health framework-next contract against that exact wheel.

It deliberately does **not** directly mark these five live gates PASS:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

Those must come from a separate successful exact-candidate `.github/workflows/candidate-business-path-evidence.yml` run. `candidate-release-proofs.yml` verifies that run's workflow path, event, conclusion and exact `head_sha`, downloads its retained partial proof, then strict-merges the static and live bundles.

Final `release-proofs-<candidate SHA>` is uploaded only when the merged bundle contains exactly all eight required non-integration gates and every one is PASS. Missing live evidence therefore blocks the workflow instead of being converted to PASS.

The workflow does not build wheel bytes, create tags, or create releases.

## Candidate integration evidence

Integration-backed gates are separate from `release-proofs.json`. The approved integration evidence template is source controlled at:

```text
release/0.4.0/integration-evidence-template.json
```

The remaining `.github/workflows/candidate-integration-evidence.yml` must run the approved exact-candidate Fabric evidence surfaces for identity/item read, control-plane certification, Pipeline, Copy, Spark, Warehouse commit, and ambiguous-COMMIT recovery. It must not replace those checks with generic release proof entries.

## Candidate certification

After the complete release proof and certified integration manifest exist for the same exact candidate:

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

`candidate-certify` fails unless exact version/SHA/wheel identity matches, retained text is safe, the integration manifest exactly matches the source-controlled template, all required integration checks PASS, all 15 required readiness gates PASS, `release_ready=true`, and `blockers=[]`.

`.github/workflows/candidate-certification.yml` performs the same aggregation with strict upstream workflow provenance and uploads `release-readiness-certified-<candidate SHA>` only after those conditions hold.

## Exact promotion

`framework-release` consumes the exact candidate run and successful candidate-certification run. It re-verifies source/version/run/wheel identity and zero blockers before creating the immutable tag at the exact candidate SHA and publishing the already-certified wheel and evidence assets.

## Current state

```text
public release                    v0.3.0
0.4 source                        feature-frozen / unreleased
release allowed                   no
candidate                         not yet frozen
ordinary required blockers        15
strict partial proof merge        merged + CI proven
candidate-release-proofs          feature branch implemented / CI pending
candidate-business-path-evidence  not yet implemented
candidate-integration-evidence    not yet implemented
certified artifact                not yet produced
```

No current state above is a claim of live Fabric certification. The next release-blocking work is to validate/merge the release-proof producer, then implement real retained business-path evidence and approved Fabric integration evidence.