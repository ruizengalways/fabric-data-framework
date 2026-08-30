# MACHINE RELEASE READINESS CONTRACT

```yaml
schema: fabric-data-framework-release-readiness-v1
framework_version: 0.4.0-development-unreleased
public_release: v0.3.0
release_allowed: false
spec: release/0.4.0/readiness-spec.json
implementation: src/fabric_data_framework/evidence/release_readiness.py
cli: fabric-framework release-readiness
```

## Purpose

The release-readiness layer aggregates retained proof for an exact candidate. It does not execute Fabric, infer missing proof, or promote CI success into live evidence.

## Exact identity

```text
candidate_git_sha = exact 40-character source commit
artifact_sha256   = exact candidate wheel/artifact hash
framework_version = exact package version
```

A non-integration `ReleaseReadinessProofBundle` must match the framework version and candidate git SHA. If an artifact hash is present in both evaluation input and the proof bundle, it must match exactly.

Supplying live `IntegrationEvidenceManifest` requires an artifact SHA256. The manifest `release_hash` must equal that exact artifact SHA256. This is the release boundary that prevents provider proof for one candidate wheel from certifying a different rebuilt wheel.

## Evidence ownership

```text
ReleaseReadinessProofBundle
  -> source verification
  -> exact wheel integrity
  -> fabric-customer compatibility
  -> FULL/REPLACE representative proof
  -> WATERMARK/SCD1 representative proof
  -> WATERMARK/SCD2 representative proof
  -> retry/idempotency proof
  -> reconciliation fail-closed proof

IntegrationEvidenceManifest
  -> Fabric item authorization
  -> control-plane certification
  -> Fabric Pipeline
  -> Fabric Copy capture
  -> Fabric Spark capture
  -> Warehouse commit/marker
  -> ambiguous COMMIT drill
  -> optional Kafka/Delta provider proof
```

Integration-backed readiness gates cannot be satisfied through generic release proofs. That separation is intentional and prevents a manually-authored PASS from bypassing the approved integration evidence contracts.

## Fail-closed rules

```text
missing proof                   -> NOT_RUN
required NOT_RUN                -> blocker
required FAIL                   -> blocker
required OUT_OF_SCOPE           -> converted to FAIL/blocker
optional OUT_OF_SCOPE           -> allowed
unknown proof gate              -> reject
proof kind mismatch             -> reject
proof candidate SHA mismatch    -> reject
proof artifact SHA mismatch     -> reject
integration version mismatch    -> reject
integration release_hash mismatch -> reject
```

`release_ready=true` if and only if every required gate is `PASS`.

## 0.4 gate matrix

Required:

```text
source.tests
wheel.integrity
customer.compatibility
fabric.identity
control.certification
fabric.pipeline
fabric.copy
fabric.spark
warehouse.commit
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
warehouse.ambiguous_commit
```

Optional unless the release scope changes:

```text
external.cdc.debezium
```

If Debezium/Kafka is promoted into the 0.4 GA certification promise, change that gate to required before collecting/reviewing the final candidate evidence.

## Current CI meaning

Framework CI runs `release-readiness` with the 0.4 spec and the exact workflow SHA but intentionally supplies no proof bundle or integration manifest. The expected result is:

```text
release_ready = false
required gates = NOT_RUN
readiness artifact retained
```

A green CI job here proves only that the fail-closed readiness contract works. It is not live Fabric proof and does not make 0.4 releasable.

## Remaining release-system gap

The existing `framework-release` workflow rebuilds the wheel during release. Exact-artifact handoff is not yet hardened for 0.4 certification. Before 0.4 GA, the release process must consume or cryptographically prove the exact certified candidate artifact rather than assume a rebuilt wheel is equivalent.

Therefore current state remains:

```text
0.4.0 = UNRELEASED
release_allowed = false
next = candidate artifact handoff + real Fabric evidence
```
