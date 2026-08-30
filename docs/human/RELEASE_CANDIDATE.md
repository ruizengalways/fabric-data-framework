# 0.4 release-candidate readiness

`0.4.0` is still development source. A green unit-test build, a retained wheel, or a provider-reported `Completed` state is not enough to publish it.

## Freeze rule

Once one main-CI wheel is selected as the candidate, stop adding product features. Only release blockers, certification defects, compatibility defects, evidence defects, and documentation defects may change the candidate. Any code fix creates a new candidate SHA and requires new exact-candidate evidence.

## The release chain

The 0.4 path is intentionally split into three stages:

```text
main CI builds exact candidate bytes
        ↓
approved evidence runs prove the exact candidate
        ↓
candidate-certification validates all retained evidence
        ↓
framework-release promotes the exact certified bytes
```

There is no release-time wheel rebuild.

## Source-controlled policies

Readiness gates:

```text
release/0.4.0/readiness-spec.json
```

Approved integration evidence check membership:

```text
release/0.4.0/integration-evidence-template.json
```

The integration template deliberately has no candidate hash. At certification time it is bound to the selected `DEV`, `UAT`, or `PROD` environment, the approved domain, and the exact inner wheel SHA256.

## 0.4 required proof

Required readiness proof currently covers:

```text
source tests / architecture / package checks
exact wheel integrity
fabric-customer exact-candidate compatibility
enterprise Fabric identity + item read
production control-plane certification
approved Fabric Pipeline execution
approved Copy capture
approved Spark capture
Warehouse target + marker commit safety
representative live FULL -> REPLACE
representative live WATERMARK -> SCD1
representative live WATERMARK -> SCD2
retry/rerun idempotency
semantic reconciliation fail-closed behavior
real ambiguous-COMMIT recovery drill
```

Debezium/Kafka remains optional for 0.4 unless the public GA scope explicitly promotes it to required certification.

## Ordinary readiness report

You can generate a fail-closed report before live proof exists:

```bash
fabric-framework release-readiness \
  --spec release/0.4.0/readiness-spec.json \
  --candidate-sha "$(git rev-parse HEAD)" \
  --output build/release-readiness.json
```

That command succeeding only means the report was generated. Missing required proof becomes `NOT_RUN`, so the report remains blocked.

## Exact candidate wheel

Main CI retains:

```text
fabric_data_framework-<version>-py3-none-any.whl
SHA256SUMS
CANDIDATE.json
```

`CANDIDATE.json` binds the package version, source SHA, GitHub Actions run ID/attempt, wheel filename, and exact inner wheel SHA256.

Do not use GitHub's uploaded ZIP digest as the wheel identity. Certification and release use the inner wheel SHA256 from `CANDIDATE.json` / `SHA256SUMS`.

## Candidate certification

Once the two retained evidence producers have completed for the same exact candidate, the certification command is:

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

Unlike ordinary `release-readiness`, `candidate-certify` is a hard certification command. It fails unless:

```text
release-proofs.json matches version + candidate SHA + exact wheel SHA
release proof references/details are safe to retain
integration-evidence.json matches the source-controlled integration template
environment/domain match the selected certification scope
integration release_hash equals the exact wheel SHA
all required integration checks are certified PASS
all 15 required readiness gates are PASS
release_ready=true
blockers=[]
```

## GitHub candidate-certification workflow

`.github/workflows/candidate-certification.yml` is manual and performs only certification aggregation. It verifies candidate CI provenance, downloads and authenticates the exact candidate wheel, installs that wheel without rebuilding it, verifies provenance of the two retained evidence runs, then invokes `candidate-certify`.

It accepts evidence only from these dedicated producer workflow paths:

```text
.github/workflows/candidate-release-proofs.yml
.github/workflows/candidate-integration-evidence.yml
```

Both producer runs must be successful explicit `workflow_dispatch` runs whose `head_sha` equals the exact candidate SHA. Their fixed artifact names are:

```text
release-proofs-<candidate SHA>
integration-evidence-<candidate SHA>
```

Only a successful certification uploads:

```text
release-readiness-certified-<candidate SHA>/
  release-readiness.json
  release-proofs.json
  integration-evidence.json
```

The certification workflow does not create tags, GitHub releases, or new wheel bytes.

## Exact promotion

`framework-release` then consumes the exact candidate run and the successful candidate-certification run. Before any release mutation it re-verifies source/version/run/wheel identity and checks that the certified readiness report has zero blockers and every required gate is PASS.

Only then does it create the immutable tag at the exact candidate SHA and publish the already-certified wheel plus checksum/candidate/evidence assets.

## Current state

The exact-byte candidate and release-promotion contracts already exist. The candidate-certification aggregator/workflow is the current release-blocking slice and still requires PR CI/merge before it can be called proven.

The next producer work is intentionally separate:

```text
candidate-release-proofs.yml
  -> source/wheel/customer compatibility + representative live business-path proofs

candidate-integration-evidence.yml
  -> Fabric identity/control-plane/Pipeline/Copy/Spark/Warehouse/ambiguous-COMMIT proof
```

Those workflows must produce real retained evidence; they must not manufacture PASS JSON.

Therefore today:

```text
public release       v0.3.0
0.4 source           feature-frozen / unreleased
candidate            not yet frozen
required blockers    15
certified artifact   not yet produced
```
