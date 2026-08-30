# 0.4 release-candidate readiness

`0.4.0` is still development source. A green unit-test build, a retained wheel, or a provider-reported `Completed` state is not enough to publish it.

## Freeze rule

Once one main-CI wheel is selected as the candidate, stop adding product features. Only release blockers, certification defects, compatibility defects, evidence defects, and documentation defects may change the candidate. Any code fix creates a new candidate SHA and requires new exact-candidate evidence.

## Release chain

```text
main CI builds exact candidate bytes
        ↓
approved exact-candidate evidence producers retain proof
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

The integration template deliberately has no candidate hash. At certification time it is bound to the selected `DEV`, `UAT`, or `PROD` environment, approved domain, and exact inner wheel SHA256.

## Required proof

The 15 required readiness gates currently cover:

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

Debezium/Kafka remains optional unless the public 0.4 GA scope explicitly promotes it to required certification.

## Ordinary readiness report

```bash
fabric-framework release-readiness \
  --spec release/0.4.0/readiness-spec.json \
  --candidate-sha "$(git rev-parse HEAD)" \
  --output build/release-readiness.json
```

Generating a report does not mean it passed. Missing required proof becomes `NOT_RUN`, so ordinary CI intentionally remains blocked.

## Exact candidate wheel

Main CI retains:

```text
fabric_data_framework-<version>-py3-none-any.whl
SHA256SUMS
CANDIDATE.json
```

`CANDIDATE.json` binds package version, source SHA, GitHub Actions run ID/attempt, wheel filename, and exact inner wheel SHA256.

Do not use GitHub's uploaded ZIP/archive digest as wheel identity. Certification and release use the inner wheel SHA256 from `CANDIDATE.json` / `SHA256SUMS`.

## Candidate certification

After both retained evidence producers complete for the same exact candidate:

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

`candidate-certify` fails unless:

```text
release-proofs.json matches version + candidate SHA + exact wheel SHA
release proof references/details are safe to retain
integration-evidence.json matches the source-controlled integration template
environment/domain match certification scope
integration release_hash equals exact wheel SHA
all required integration checks are certified PASS
all 15 required readiness gates PASS
release_ready=true
blockers=[]
```

## GitHub candidate-certification workflow

`.github/workflows/candidate-certification.yml` is manual certification aggregation only. It verifies candidate CI provenance, authenticates exact candidate bytes, installs that wheel without rebuilding, verifies upstream evidence-run provenance, then invokes `candidate-certify`.

It only accepts evidence from these fixed producer workflow paths:

```text
.github/workflows/candidate-release-proofs.yml
.github/workflows/candidate-integration-evidence.yml
```

Both producer runs must be successful explicit `workflow_dispatch` runs whose `head_sha` equals the candidate SHA. Fixed artifact names are:

```text
release-proofs-<candidate SHA>
integration-evidence-<candidate SHA>
```

Only successful certification can upload:

```text
release-readiness-certified-<candidate SHA>/
  release-readiness.json
  release-proofs.json
  integration-evidence.json
```

The certification workflow does not build wheel bytes, create tags, or publish releases.

## Exact promotion

`framework-release` consumes the exact candidate run and successful candidate-certification run. Before mutation it re-verifies source/version/run/wheel identity and verifies zero blockers with every required gate PASS.

Only then does it tag the exact candidate SHA and publish the already-certified wheel plus checksum/candidate/evidence assets.

## Current state

Candidate certification is now merged and CI proven:

```text
PR                 #84
merge SHA          bb9b7ed74e2696978c546011c893fb316ffdd57c
final PR CI        33314924064
main CI            33314977393
merged tests       653
latest wheel SHA   ce78ae1bc67b0e68bca360e825d36cf6b0cb171f811de8257cd9ce0225154748
candidate frozen   no
```

This is implementation proof only, not Fabric certification.

The two actual evidence producers are still intentionally missing:

```text
candidate-release-proofs.yml
  -> exact source/wheel/customer proof plus retained representative business-path evidence

candidate-integration-evidence.yml
  -> Fabric identity/control-plane/Pipeline/Copy/Spark/Warehouse/ambiguous-COMMIT evidence
```

Because release proofs mix portable/static checks and live business-path checks, the next framework change should first add strict partial proof merge. That lets independent producers contribute evidence without choosing “latest wins” or inventing a PASS.

Therefore today:

```text
public release       v0.3.0
0.4 source           feature-frozen / unreleased
release allowed      no
candidate            not yet frozen
required blockers    15
certified artifact   not yet produced
```
