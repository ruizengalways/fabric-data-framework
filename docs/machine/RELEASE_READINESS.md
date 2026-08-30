# MACHINE RELEASE READINESS CONTRACT

```yaml
schema: fabric-data-framework-release-readiness-v1
framework_version: 0.4.0-development-unreleased
public_release: v0.3.0
release_allowed: false
spec: release/0.4.0/readiness-spec.json
implementation: src/fabric_data_framework/evidence/release_readiness.py
candidate_artifact_contract: src/fabric_data_framework/deployment/candidate_artifact.py
release_promotion_workflow: .github/workflows/release.yml
cli: fabric-framework release-readiness
```

## Purpose

The release-readiness layer aggregates retained proof for an exact candidate. It does not execute Fabric, infer missing proof, or promote CI success into live evidence.

The release-promotion layer is separate: it must publish the exact wheel bytes that were certified. Release-time rebuilding is forbidden for 0.4+ promotion.

## Exact identity

```text
candidate_git_sha = exact 40-character source commit
artifact_sha256   = exact inner candidate wheel hash
framework_version = exact package version
candidate_run_id  = successful main framework-ci run that built those bytes
```

A non-integration `ReleaseReadinessProofBundle` must match the framework version and candidate git SHA. Final certified proof must also bind the exact artifact SHA256.

Supplying live `IntegrationEvidenceManifest` requires an artifact SHA256. The manifest `release_hash` must equal that exact artifact SHA256. This is the release boundary that prevents provider proof for one candidate wheel from certifying a different rebuilt wheel.

GitHub Actions also reports an artifact archive digest. That archive digest is not the inner wheel SHA256 and must never replace `artifact_sha256` in release evidence.

## Candidate artifact manifest

Main CI creates `CANDIDATE.json` alongside the wheel and `SHA256SUMS`.

Exact fields:

```text
schema_version
package_name
framework_version
candidate_git_sha
workflow_run_id
workflow_run_attempt
wheel_filename
wheel_sha256
```

The manifest verifier is standard-library only so the downloaded wheel can be authenticated before installing/trusting that wheel.

Fail closed on:

```text
unknown/missing manifest keys
wrong package name
invalid source SHA
invalid wheel SHA256
path-traversal/non-plain wheel filename
zero/multiple wheel files at candidate creation
candidate SHA mismatch
workflow run ID/attempt mismatch
framework version mismatch
expected wheel SHA mismatch
actual downloaded wheel bytes mismatch
wheel METADATA package/version mismatch
```

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

## Fail-closed readiness rules

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

## Ordinary CI meaning

Framework CI runs `release-readiness` with the 0.4 spec and the exact workflow SHA but intentionally supplies no proof bundle or integration manifest. The expected result is:

```text
release_ready = false
required gates = NOT_RUN
readiness artifact retained
```

A green CI job here proves only that the fail-closed readiness contract works. It is not live Fabric proof and does not make 0.4 releasable.

The same CI run also retains an exact wheel candidate artifact. A main CI wheel artifact is a **candidate input**, not certification. Selecting a run does not create evidence by itself.

## Release promotion workflow

`framework-release` is manual promotion only. Tag-push auto-release is intentionally absent.

Required inputs:

```text
version
candidate_run_id
candidate_git_sha
candidate_wheel_sha256
readiness_run_id
```

Before any tag/release mutation it verifies:

```text
candidate source SHA is exact and reachable from main
source package version equals requested release version
release tag and GitHub release do not already exist
candidate run is successful framework-ci main push
candidate run head SHA equals candidate_git_sha
downloaded artifact name is framework-wheel-<candidate SHA>
CANDIDATE.json exact run/SHA/version/wheel SHA matches inputs
SHA256SUMS verifies exact wheel bytes
installed downloaded wheel passes validate-tag / pip check / full tests
readiness run is successful explicit candidate-certification workflow
certified artifact name is release-readiness-certified-<candidate SHA>
release-readiness.json matches version/SHA/wheel and has release_ready=true, blockers=[]
every required readiness result is PASS
release-proofs.json matches exact version/SHA/wheel
integration-evidence.json release_hash matches exact wheel SHA
```

Only then:

```text
create immutable tag at exact candidate_git_sha
publish already-certified wheel bytes
publish SHA256SUMS + CANDIDATE.json
publish exact readiness/proof/integration evidence assets
```

The release workflow contains no wheel build step. If candidate or readiness artifacts are missing/expired/mismatched, release must fail rather than rebuild or infer equivalence.

## Remaining release-system gap

The exact candidate promotion seam is implemented, but the trusted producer for:

```text
release-readiness-certified-<candidate SHA>
```

is not yet implemented/run. The next slice is the explicit `candidate-certification` workflow/evidence packaging that consumes a frozen candidate wheel and real approved Fabric evidence, then produces the three exact files required by promotion:

```text
release-readiness.json
release-proofs.json
integration-evidence.json
```

Therefore current state remains:

```text
0.4.0 = UNRELEASED
release_allowed = false
candidate = NOT YET FROZEN
certified readiness artifact = NOT YET PRODUCED
next = candidate-certification workflow + real Fabric evidence
```
