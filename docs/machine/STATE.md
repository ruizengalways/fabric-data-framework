# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-08-31
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
feature_freeze: true
candidate_status: not_frozen
code_baseline:
  pull_request: 86
  merge_sha: 0f70e037806482c677fccae0ce9432504f2a9885
  milestone: strict exact-candidate partial ReleaseReadinessProofBundle merge
  pr_ci_actions: 33342779028
  main_ci_actions: 33342806854
  tests: 664
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  release_proof_merge_contract: success
  candidate_certification_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  candidate_capable_main_artifact:
    selected_as_frozen_candidate: false
    workflow_run_id: 33342806854
    workflow_run_attempt: 1
    candidate_git_sha: 0f70e037806482c677fccae0ce9432504f2a9885
    wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    wheel_inner_sha256: edcde5a85ded7a01ec8502d065e7b04c4621f8609ae887c7a479d8b253978656
    artifact_id: 9741061544
    artifact_archive_digest: sha256:9585033dbc4c88b97e6e3877b9e9c647dfab896010c224a2cbfa4f0dfe362782
    artifact_expires_at: 2026-11-28T23:49:01Z
feature_branch_release_blocker:
  branch: codex/candidate-release-proofs-workflow
  capability: exact-candidate non-integration release-proof producer
  state: implemented_ci_pending
  direct_pass_scope:
    - source.tests
    - wheel.integrity
    - customer.compatibility
  external_live_scope:
    - full.replace
    - watermark.scd1
    - watermark.scd2
    - retry.idempotency
    - reconciliation.fail_closed
documentation_model:
  human: docs/human
  machine: docs/machine
  examples: examples
```

## Release decision

`0.4.0` remains **UNRELEASED**, feature-frozen and not release-allowed. No exact candidate has been selected/frozen.

Ordinary CI deliberately supplies no complete exact-candidate release proof bundle and no certified live `IntegrationEvidenceManifest`, so all 15 required readiness gates remain blockers and `release_ready=false`.

Main run `33342806854` produced a candidate-capable wheel for source SHA `0f70e037806482c677fccae0ce9432504f2a9885` with inner SHA256:

```text
edcde5a85ded7a01ec8502d065e7b04c4621f8609ae887c7a479d8b253978656
```

It is **not selected/frozen**. The GitHub artifact archive digest is transport metadata only and is not interchangeable with the inner wheel SHA256 used by proof/certification/release truth.

## Canonical ownership

```text
src/fabric_data_framework/
  __init__.py       namespace marker only
  contracts/        provider-neutral immutable contracts
  metadata/         DatasetConfig + capability metadata
  capture/          capture semantics/onboarding/bootstrap/bounded reads
  apply/            target apply semantics
  data_plane/       Bronze/staging contracts
  quality/          reconciliation/schema/temporal quality
  orchestration/    planning/dispatch/failure isolation
  execution/        execution plans/backends
  adapters/         provider transports/auth
  control_plane/    relational state/schema/certification
  recovery/         retry/replay/target commit ambiguity recovery
  evidence/         integration evidence + approved runners + readiness + proof merge + candidate certification
  deployment/       delivery/release provenance + candidate identity + project init/validation
  extensions/       bounded extension loading/contracts
  cli/              removable presentation leaf
```

No broad root-level compatibility facades should be reintroduced during the 0.4 freeze.

Representative current imports:

```python
from fabric_data_framework.metadata.config import DatasetConfig
from fabric_data_framework.capture.semantic_contracts import SourceSemantics
from fabric_data_framework.control_plane.sqlalchemy_repository import SqlAlchemyControlPlaneRepository
from fabric_data_framework.evidence.integration_evidence import IntegrationEvidenceManifest
from fabric_data_framework.evidence.release_readiness import evaluate_release_readiness
from fabric_data_framework.evidence.release_readiness_merge import merge_release_readiness_proof_bundles
from fabric_data_framework.evidence.candidate_certification import certify_release_candidate
from fabric_data_framework.deployment.project import initialize_customer_project, validate_customer_project
```

## Customer project contract

Reusable project logic is in `deployment/project.py`; `cli/project.py` is presentation only.

```text
project-init never guesses PK/watermark/delete/history semantics
project-init never overwrites existing files
project-init never creates Fabric resources or persists secrets
one domain repo may mix FULL/WATERMARK/CDC and SCD1/SCD2
execution_group handles operational grouping
project-validate rejects unknown dependencies/cycles/capability mismatch/semantic overclaim
project-validate requires exact semantic-selection coverage
project-validate is local/static and never upgrades PASS to live Fabric proof
```

## Release readiness and strict partial proof merge

Source-controlled readiness matrix:

```text
release/0.4.0/readiness-spec.json
```

Required gates: 15. Debezium/Kafka remains optional unless the 0.4 GA promise explicitly promotes it.

Fail-closed readiness invariants:

```text
missing proof -> NOT_RUN
required NOT_RUN/FAIL/OUT_OF_SCOPE -> blocker
proof framework/candidate/artifact mismatch -> reject
integration-backed gate cannot be satisfied by generic proof
IntegrationEvidenceManifest release_hash must equal exact inner wheel SHA256
release_ready=true iff every required gate PASS
```

Strict partial non-integration proof merge is canonical in:

```text
src/fabric_data_framework/evidence/release_readiness_merge.py
fabric-framework release-proofs-merge
```

PR #86 proves:

```text
every partial bundle binds exact schema/version/candidate SHA/non-null wheel SHA
unknown or integration-backed gates reject
NOT_RUN/omitted means no proof
identical duplicate substantive proof may merge
different substantive proof conflicts, including two different PASS records
no latest/PASS/FAIL/timestamp precedence
credential-like retained text rejects before merged output
```

A successful proof merge does not create live evidence or make the release ready.

## Candidate release-proof producer — feature branch

`.github/workflows/candidate-release-proofs.yml` is implemented on the current feature branch and is **CI pending**.

Its direct PASS scope is deliberately limited to facts it observes itself:

```text
source.tests
wheel.integrity
customer.compatibility
```

It re-verifies exact successful main framework CI and required jobs, re-authenticates exact candidate wheel bytes, installs that wheel, verifies an explicit `fabric-customer` SHA from customer main history, runs customer `project-validate`, and regenerates/validates the 100-table Health framework-next contract against the exact candidate.

It does not directly create PASS for:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

Those five gates must come from a successful exact-candidate `.github/workflows/candidate-business-path-evidence.yml` retained artifact. The final producer verifies that run provenance, strict-merges static + live partial proof, and refuses `release-proofs-<candidate SHA>` unless exactly all eight required non-integration gates exist and PASS.

## Candidate certification — merged PR #84

Source-controlled integration policy:

```text
release/0.4.0/integration-evidence-template.json
```

Reusable implementation/presentation:

```text
src/fabric_data_framework/evidence/candidate_certification.py
fabric-framework candidate-certify
.github/workflows/candidate-certification.yml
```

Certification requires exact candidate/run/wheel identity, a successful exact-SHA release-proof producer run, a successful exact-SHA integration-evidence producer run, safe retained proof text, a fully certified exact integration manifest, and final readiness with `release_ready=true`, `blockers=[]`, every required gate PASS.

Candidate certification itself does not execute Fabric, build wheels, create tags, or publish releases.

## Exact release promotion

`.github/workflows/release.yml` is manual promotion only. It re-verifies the exact candidate and successful candidate-certification artifact, then tags the exact candidate SHA and publishes the already-certified wheel/evidence assets. There is no release-time wheel rebuild and no tag-push auto-release.

## Current release blockers

```text
candidate-release-proofs workflow      FEATURE BRANCH IMPLEMENTED / CI PENDING
candidate-business-path-evidence       NOT YET IMPLEMENTED
candidate-integration-evidence         NOT YET IMPLEMENTED
exact candidate freeze                 NOT YET
certified readiness artifact           NOT YET PRODUCED
release-readiness blockers             15 in ordinary CI
```

Real evidence still missing includes:

```text
fabric-customer exact frozen-candidate compatibility artifact
enterprise Entra identity + workspace/item authorization
production control-plane certification
approved Pipeline
approved Copy + Spark capture
representative live FULL -> REPLACE
representative live WATERMARK -> SCD1
representative live WATERMARK -> SCD2
retry/rerun idempotency + no-unsafe-progress drill
semantic reconciliation fail-closed drill
Warehouse mutation + same-transaction marker
provider-specific real ambiguous-COMMIT drill
exact Warehouse session/Admin recovery chain where required
complete release proof bundle + certified IntegrationEvidenceManifest
capacity/SKU/network/DR/monitoring/governance evidence
Debezium/Kafka live certification only if promoted into 0.4 GA scope
```

## Next engineering order

```text
1. validate/merge candidate-release-proofs workflow
2. implement candidate-business-path-evidence using real retained path observations, not authored PASS JSON
3. implement candidate-integration-evidence around existing approved exact-run surfaces
4. select/freeze one exact 0.4 candidate only when both producer paths are ready
5. run exact customer/static proof
6. collect representative FULL/REPLACE, WATERMARK/SCD1, WATERMARK/SCD2, retry and reconciliation evidence
7. collect Fabric identity/control-plane/Pipeline/Copy/Spark/Warehouse/ambiguous-COMMIT evidence
8. aggregate exact release proof + certified IntegrationEvidenceManifest
9. candidate-certification must produce zero blockers
10. framework-release promotes exact certified bytes
11. only then immutable v0.4.0 exists
12. after release migrate fabric-customer from v0.3.0/exact-SHA-next to immutable 0.4
```

## Evidence vocabulary boundary

Highest current claim is **IMPLEMENTED + CI PROVEN** for merged portable contracts including project init/validation, approved evidence runners, release readiness, exact candidate identity, strict proof merge, candidate certification and exact-byte promotion.

The current `candidate-release-proofs` feature branch is not yet part of that merged claim. Do not use `FABRIC PROVEN`, `FABRIC WAREHOUSE PROVEN` or `PRODUCTION DB PROVEN` until retained approved real-service evidence exists for the exact frozen candidate/artifact.

## Repository ownership

```text
fabric-data-framework = reusable semantics/runtime/adapters/recovery/evidence/package + project/release contracts
fabric-customer       = domain DatasetConfig + semantic selections + bounded extensions + Fabric content
fabric-infra          = optional capacity/workspace/infrastructure lifecycle
```
