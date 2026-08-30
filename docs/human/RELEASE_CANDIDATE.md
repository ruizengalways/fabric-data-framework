# 0.4 release-candidate readiness

`0.4.0` is development source until every required release gate is backed by retained evidence for the exact candidate. Passing unit tests or a provider-reported `Completed` state is not enough.

## Freeze rule

Once a candidate is selected, do not add new capture/apply strategies, package restructuring, or unrelated CLI behavior. Only release blockers, certification defects, compatibility defects, and evidence/documentation defects should change the candidate.

A code fix creates a new candidate SHA. Evidence from an older candidate is not silently inherited.

## Source-controlled gate matrix

The 0.4 gate matrix lives at:

```text
release/0.4.0/readiness-spec.json
```

It currently requires retained proof for:

```text
source tests / architecture / package checks
exact candidate wheel integrity
fabric-customer compatibility
enterprise Fabric identity + item read
control-plane certification
approved Pipeline execution
approved Copy capture
approved Spark capture
Warehouse target/marker commit safety
representative FULL -> REPLACE
representative WATERMARK -> SCD1
representative WATERMARK -> SCD2
retry/rerun idempotency
semantic reconciliation fail-closed behavior
real ambiguous-COMMIT recovery drill
```

Debezium/Kafka is optional in the 0.4 matrix unless the release scope explicitly promotes it to a required GA-certified path. If it remains optional, documentation must say that the `EXTERNAL_CDC` contract exists but live Debezium/Kafka production certification is outside the 0.4 GA proof set.

## Generate a readiness report

A report can be generated before evidence exists:

```bash
fabric-framework release-readiness \
  --spec release/0.4.0/readiness-spec.json \
  --candidate-sha "$(git rev-parse HEAD)" \
  --output build/release-readiness.json
```

That command succeeding only means the report was generated. Missing proof becomes `NOT_RUN`; required `NOT_RUN`, `FAIL`, or `OUT_OF_SCOPE` gates keep `release_ready=false`.

To use the command as a hard release gate:

```bash
fabric-framework release-readiness \
  --spec release/0.4.0/readiness-spec.json \
  --candidate-sha "${CANDIDATE_SHA}" \
  --artifact-sha256 "${CANDIDATE_WHEEL_SHA256}" \
  --proofs evidence/release-proofs.json \
  --integration-evidence evidence/integration-evidence.json \
  --output build/release-readiness.json \
  --require-ready
```

`--require-ready` exits non-zero while any required gate is not `PASS`.

## Exact candidate wheel produced by main CI

`framework-ci` builds one framework wheel and creates:

```text
dist/
  fabric_data_framework-<version>-py3-none-any.whl
  SHA256SUMS
  CANDIDATE.json
```

`CANDIDATE.json` binds:

```text
framework version
candidate git SHA
GitHub Actions run ID
GitHub Actions run attempt
exact wheel filename
exact inner wheel SHA256
```

The manifest is created and re-verified before upload. Main-branch wheel artifacts are retained longer than PR artifacts so a selected candidate can be certified without rebuilding it.

The GitHub artifact ZIP digest is only the digest of GitHub's uploaded archive. It is not the framework wheel SHA256. Certification and release use the inner wheel SHA256 recorded in `CANDIDATE.json` and `SHA256SUMS`.

## Exact identity rules

The proof bundle must match the exact framework version and 40-character candidate git SHA. If an exact artifact SHA256 is supplied, the proof bundle must match it as well.

Live integration evidence is stricter: supplying `IntegrationEvidenceManifest` requires `--artifact-sha256`, and the manifest `release_hash` must equal that exact artifact SHA256. This prevents evidence for one wheel from being used to certify another rebuilt artifact.

Integration-backed gates cannot be satisfied by generic proof entries. For example, a manually written `FABRIC_PIPELINE=PASS` proof cannot replace the existing approved Pipeline integration evidence contract.

## Evidence split

Two evidence channels are intentionally separate:

```text
ReleaseReadinessProofBundle
  source verification
  wheel integrity
  customer compatibility
  representative business-path drills such as FULL/SCD1/SCD2/retry/reconciliation

IntegrationEvidenceManifest
  Fabric item authorization
  control-plane certification
  Pipeline
  Copy
  Spark
  Warehouse commit
  ambiguous COMMIT drill
  optional Kafka/Delta provider evidence
```

This preserves the existing IntegrationEvidence contract instead of creating another provider truth model.

## Exact promotion, never release-time rebuild

The release workflow is manual exact-candidate promotion. It no longer builds a new wheel and does not publish merely because someone pushes a version tag.

A future release invocation must provide:

```text
version
candidate_run_id
candidate_git_sha
candidate_wheel_sha256
readiness_run_id
```

Before creating a tag or GitHub release it verifies all of the following:

```text
candidate SHA is reachable from main
candidate source package version matches requested release
candidate CI run is a successful main push of framework-ci
candidate CI run head SHA equals candidate_git_sha
exact framework-wheel-<candidate SHA> artifact is downloaded from that run
CANDIDATE.json run/SHA/version/wheel SHA all match
SHA256SUMS matches the downloaded wheel bytes
exact downloaded wheel installs and the full test suite passes
readiness run is a successful explicit candidate-certification workflow
certified readiness artifact name is release-readiness-certified-<candidate SHA>
release-readiness.json says release_ready=true and blockers=[]
every required readiness result is PASS
release-proofs.json matches version + candidate SHA + wheel SHA
integration-evidence.json release_hash matches the exact wheel SHA
```

Only after those checks does the workflow create the immutable tag **at the exact candidate SHA** and publish the already-certified wheel bytes plus candidate/readiness evidence assets.

If the certified readiness artifact does not exist, release is impossible. That is intentional.

## Current 0.4 state

The ordinary repository CI still intentionally generates a readiness report with no fabricated proof inputs. Therefore that report is expected to be `BLOCKED`. This is a successful fail-closed contract test, not evidence that Fabric certification has happened.

Exact artifact promotion is now a framework release contract, but **no candidate is frozen yet and no certified readiness run exists yet**.

The next engineering stage is:

```text
build candidate-certification workflow / evidence packaging
-> select one successful main CI run as the candidate
-> freeze candidate git SHA + inner wheel SHA256
-> bind fabric-customer compatibility to that exact wheel
-> run representative real Fabric certification
-> retain release-proofs.json + integration-evidence.json
-> generate release-readiness.json with --require-ready
-> upload release-readiness-certified-<candidate SHA>
-> only when required blockers are zero invoke framework-release
-> framework-release promotes the exact certified wheel; it never rebuilds it
```
