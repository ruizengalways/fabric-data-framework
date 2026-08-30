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

## Current 0.4 state

The repository CI intentionally generates a readiness report with no fabricated proof inputs. Therefore the current report is expected to be `BLOCKED`. This is a successful fail-closed contract test, not evidence that Fabric certification has happened.

The next engineering stage after this contract is merged is:

```text
select/freeze candidate artifact
-> retain exact candidate wheel SHA256
-> run representative real Fabric certification
-> create exact-candidate proof bundle
-> aggregate readiness report
-> require release_ready=true
-> only then create immutable v0.4.0 release
```

The existing release workflow still needs exact-candidate artifact handoff hardening before 0.4 GA. Do not treat a rebuilt release wheel as automatically equivalent to a wheel that was certified earlier; the exact artifact hash must remain part of the proof chain.
