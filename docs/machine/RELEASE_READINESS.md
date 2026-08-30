# MACHINE RELEASE READINESS CONTRACT

```yaml
schema: fabric-data-framework-release-readiness-v1
framework_version: 0.4.0-development-unreleased
public_release: v0.3.0
release_allowed: false
readiness_spec: release/0.4.0/readiness-spec.json
integration_template: release/0.4.0/integration-evidence-template.json
readiness_implementation: src/fabric_data_framework/evidence/release_readiness.py
certification_implementation: src/fabric_data_framework/evidence/candidate_certification.py
candidate_artifact_contract: src/fabric_data_framework/deployment/candidate_artifact.py
candidate_certification_workflow: .github/workflows/candidate-certification.yml
release_promotion_workflow: .github/workflows/release.yml
readiness_cli: fabric-framework release-readiness
certification_cli: fabric-framework candidate-certify
```

## Purpose

The release system has three deliberately separate layers:

```text
candidate artifact identity
  -> retained evidence certification
  -> immutable exact-byte promotion
```

No layer executes Fabric merely to make another layer pass. Provider/business-path evidence is produced by approved evidence workflows, certification validates retained evidence, and release only promotes already-certified bytes.

## Exact identity

```text
candidate_git_sha = exact 40-character source commit
artifact_sha256   = exact inner candidate wheel SHA256
framework_version = exact package version
candidate_run_id  = successful main framework-ci run that built those bytes
```

GitHub's artifact archive digest is transport metadata only. It is not the inner wheel SHA256 and must never replace `artifact_sha256` in certification or release evidence.

## Candidate artifact manifest

Main CI creates `CANDIDATE.json` beside the wheel and `SHA256SUMS`. It binds:

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

The standard-library verifier authenticates the downloaded wheel before that wheel is installed. It rejects manifest key drift, path traversal, wrong package/version, source/run/attempt mismatch, expected-hash mismatch, and changed wheel bytes.

## Readiness evidence ownership

```text
ReleaseReadinessProofBundle
  -> source tests / architecture / package checks
  -> exact wheel integrity
  -> fabric-customer compatibility
  -> representative live FULL -> REPLACE
  -> representative live WATERMARK -> SCD1
  -> representative live WATERMARK -> SCD2
  -> retry/rerun idempotency drill
  -> semantic reconciliation fail-closed drill

IntegrationEvidenceManifest
  -> Fabric item authorization
  -> control-plane certification
  -> Fabric Pipeline
  -> Fabric Copy capture
  -> Fabric Spark capture
  -> Warehouse commit/marker
  -> real ambiguous-COMMIT drill
  -> optional Kafka/Debezium proof
```

Integration-backed readiness gates cannot be satisfied through generic release proof entries.

## 0.4 integration evidence template

The approved integration check membership is source controlled at:

```text
release/0.4.0/integration-evidence-template.json
```

The template intentionally has `release_hash=null`. `candidate-certify` materializes the exact spec at certification time by binding:

```text
environment = DEV | UAT | PROD
domain      = exact approved domain
release_hash = exact inner candidate wheel SHA256
```

The retained `IntegrationEvidenceManifest` must match that materialized spec exactly and must be certified under the existing integration evidence contract. Optional Kafka evidence may remain not run while its 0.4 readiness gate remains optional.

## Candidate certification contract

Reusable implementation:

```text
src/fabric_data_framework/evidence/candidate_certification.py
```

Presentation/workflow surfaces:

```text
fabric-framework candidate-certify
.github/workflows/candidate-certification.yml
```

Certification is stricter than ordinary readiness reporting. It requires all of the following before `release-readiness-certified-<candidate SHA>` may be uploaded:

```text
exact candidate source SHA is reachable from main
candidate CI provenance = successful main push framework-ci run
CANDIDATE.json matches candidate run/SHA/version/inner wheel SHA
SHA256SUMS verifies the downloaded wheel bytes
exact candidate wheel is installed; no rebuild occurs
release proof artifact comes from successful explicit candidate-release-proofs workflow
integration evidence artifact comes from successful explicit candidate-integration-evidence workflow
both evidence workflow head SHAs equal the candidate SHA
release proof bundle matches framework version + candidate SHA + wheel SHA
release proof references/details reject obvious credential material
integration manifest matches the materialized source-controlled integration spec
integration manifest is certified for all required integration checks
integration release_hash equals exact inner wheel SHA
release-readiness aggregation returns release_ready=true
blockers=[]
every required readiness result is PASS
```

If any condition fails, the workflow exits before the certified artifact upload step.

The certification workflow performs no release mutation: no tag creation, no GitHub release creation, and no wheel build.

## Readiness fail-closed rules

```text
missing proof                     -> NOT_RUN
required NOT_RUN                  -> blocker
required FAIL                     -> blocker
required OUT_OF_SCOPE             -> FAIL/blocker
optional OUT_OF_SCOPE             -> allowed
unknown proof gate                -> reject
proof kind mismatch               -> reject
proof candidate SHA mismatch      -> reject
proof artifact SHA mismatch       -> reject
integration spec mismatch         -> reject
integration release_hash mismatch -> reject
integration not certified         -> reject certification
credential-like release proof text -> reject certification
```

`release_ready=true` if and only if every required readiness gate is `PASS`.

## 0.4 readiness matrix

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

Optional unless scope changes:

```text
external.cdc.debezium
```

## Ordinary CI meaning

Framework CI intentionally runs `release-readiness` without fabricated proof inputs. Therefore current main readiness is expected to remain:

```text
release_ready = false
15 required blockers
```

A green readiness-contract job proves only that the aggregator fails closed. It is not live Fabric proof and does not make 0.4 releasable.

Likewise a main CI candidate artifact proves exact wheel identity, not certification.

## Immutable release promotion

`framework-release` is manual promotion only and contains no wheel build step. It consumes:

```text
candidate_run_id
candidate_git_sha
candidate_wheel_sha256
readiness_run_id
```

It re-verifies candidate CI provenance and exact candidate bytes, downloads `release-readiness-certified-<candidate SHA>`, verifies the report/proof/integration identities, then and only then creates the immutable tag at the exact candidate SHA and publishes those already-certified wheel bytes and evidence assets.

## Current 0.4 release-system state

The candidate-certification aggregator/workflow is implemented on the current feature branch and requires CI before it may be described as proven.

The intentionally missing next producers are:

```text
.github/workflows/candidate-release-proofs.yml
.github/workflows/candidate-integration-evidence.yml
```

Those producers must generate retained evidence from approved exact-candidate tests/live runs. They must not manufacture PASS records simply to satisfy certification.

Therefore current truth remains:

```text
0.4.0 = UNRELEASED
release_allowed = false
candidate = NOT YET FROZEN
ordinary readiness blockers = 15
certified readiness artifact = NOT YET PRODUCED
next = validate/merge candidate certification -> build trusted evidence producers -> freeze candidate -> collect real evidence
```
