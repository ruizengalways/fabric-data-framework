# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-08-30
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
feature_freeze: true
candidate_status: not_frozen
code_baseline:
  pull_request: 84
  merge_sha: bb9b7ed74e2696978c546011c893fb316ffdd57c
  milestone: exact-candidate certification aggregation over retained evidence
  pr_ci_actions_final: 33314924064
  main_ci_actions: 33314977393
  tests: 653
  python_3_11: success
  python_3_13: success
  wheel_build: success
  candidate_artifact_contract: success
  readiness_contract: success
  candidate_certification_contract: success
  candidate_certification_workflow_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  candidate_capable_main_artifact:
    selected_as_frozen_candidate: false
    workflow_run_id: 33314977393
    workflow_run_attempt: 1
    candidate_git_sha: bb9b7ed74e2696978c546011c893fb316ffdd57c
    wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl
    wheel_inner_sha256: ce78ae1bc67b0e68bca360e825d36cf6b0cb171f811de8257cd9ce0225154748
    artifact_id: 9733146071
    artifact_archive_digest: sha256:6a4d45618e64f7bf34b508652ee999b95e37a0f23cdf07927807e593bfabdde4
    artifact_expires_at: 2026-11-28T13:44:16Z
  blocked_readiness_artifact:
    artifact_id: 9733147988
    artifact_archive_digest: sha256:99a666e7d1461f741a3ea792de5022e817a23340a5a29e306f5f07875db2a11e
    artifact_expires_at: 2026-09-13T13:44:33Z
documentation_model:
  human: docs/human
  machine: docs/machine
  examples: examples
  rule: human docs explain stable use; machine docs retain exact state, evidence boundaries and provenance
```

## Release decision

`0.4.0` remains **UNRELEASED**, feature-frozen and not release-allowed.

PR #84 closes the certification-aggregation gap between retained evidence and exact-byte release promotion. The framework now has all three release-system seams:

```text
main CI exact candidate identity
        ↓
retained evidence -> candidate-certification
        ↓
framework-release exact-byte promotion
```

This does **not** mean a candidate is frozen or that Fabric certification has happened. Ordinary CI still deliberately supplies no exact-candidate release proof bundle or live IntegrationEvidenceManifest, so all 15 required readiness gates remain blockers and `release_ready=false`.

Main run `33314977393` produced a valid candidate-capable wheel for source SHA `bb9b7ed74e2696978c546011c893fb316ffdd57c` with exact inner wheel SHA256:

```text
ce78ae1bc67b0e68bca360e825d36cf6b0cb171f811de8257cd9ce0225154748
```

It is **not selected/frozen**. The GitHub artifact archive digest is transport metadata and is not interchangeable with the inner wheel SHA256 used by certification/release truth.

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
  evidence/         integration evidence + approved runners + readiness + candidate certification
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
from fabric_data_framework.evidence.candidate_certification import certify_release_candidate
from fabric_data_framework.deployment.project import initialize_customer_project, validate_customer_project
```

## Customer project contract

Reusable project logic is in `deployment/project.py`; `cli/project.py` is presentation only.

```text
fabric-framework project-init <path> --domain <domain>
fabric-framework project-validate <path>
```

Non-negotiable boundaries:

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

## Release readiness contract

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

Ordinary CI intentionally proves this blocked behavior; a green readiness job is not release readiness.

## Exact candidate identity

Canonical implementation:

```text
src/fabric_data_framework/deployment/candidate_artifact.py
```

Main CI retains:

```text
fabric_data_framework-<version>-py3-none-any.whl
SHA256SUMS
CANDIDATE.json
```

`CANDIDATE.json` binds exact source SHA, version, main CI run ID/attempt, wheel filename and inner wheel SHA256. Candidate bytes are verified before installation.

## Candidate certification — merged PR #84

Source-controlled integration policy:

```text
release/0.4.0/integration-evidence-template.json
```

Reusable implementation:

```text
src/fabric_data_framework/evidence/candidate_certification.py
```

Presentation/orchestration:

```text
fabric-framework candidate-certify
.github/workflows/candidate-certification.yml
```

Certification requires:

```text
exact candidate SHA reachable from main
candidate provenance = successful main push framework-ci run
CANDIDATE.json + SHA256SUMS + downloaded wheel bytes all match exact input identity
exact candidate wheel is installed; no rebuild occurs
release proof producer run is successful workflow_dispatch at exact candidate SHA
integration evidence producer run is successful workflow_dispatch at exact candidate SHA
release proof bundle matches version + candidate SHA + exact wheel SHA
release proof references/details reject obvious credential material
integration manifest matches source-controlled check template bound to env/domain/wheel SHA
integration manifest is certified for all required integration checks
release-readiness returns release_ready=true, blockers=[] and every required gate PASS
```

Only then may the workflow upload:

```text
release-readiness-certified-<candidate SHA>/
  release-readiness.json
  release-proofs.json
  integration-evidence.json
```

Candidate certification itself does not execute Fabric, build wheels, create tags or publish releases.

## Exact release promotion

`.github/workflows/release.yml` is manual promotion only. It re-verifies the exact candidate and successful candidate-certification artifact, then tags the exact candidate SHA and publishes the already-certified wheel/evidence assets.

There is no release-time wheel rebuild and no tag-push auto-release.

## Current release blockers

The certification aggregator is now implemented and CI proven. The next missing producer seams are explicit and intentional:

```text
.github/workflows/candidate-release-proofs.yml        NOT YET IMPLEMENTED
.github/workflows/candidate-integration-evidence.yml  NOT YET IMPLEMENTED
```

They must produce retained evidence for the exact candidate. They must never manufacture PASS JSON to satisfy certification.

Real evidence still missing includes:

```text
select/freeze exact candidate source SHA + inner wheel SHA256
fabric-customer exact-candidate compatibility proof
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
release-readiness blockers = 0
capacity/SKU/network/DR/monitoring/governance evidence
Debezium/Kafka live certification only if promoted into 0.4 GA scope
```

## Next engineering order

```text
1. add strict partial merge for ReleaseReadinessProofBundle so static and live proof producers remain separate
2. implement candidate-release-proofs producer for exact static/portable proofs without fabricating live business gates
3. implement candidate-integration-evidence producer around existing approved exact-run surfaces
4. select/freeze one exact 0.4 candidate only when producer path is ready
5. bind fabric-customer compatibility to that exact wheel
6. collect real Fabric identity/control-plane/Pipeline/Copy/Spark/Warehouse evidence
7. collect representative FULL/REPLACE, WATERMARK/SCD1, WATERMARK/SCD2, retry and reconciliation evidence
8. run real ambiguous-COMMIT drill
9. aggregate exact proof bundle + certified IntegrationEvidenceManifest
10. candidate-certification must produce zero blockers
11. framework-release promotes exact certified bytes
12. only then immutable v0.4.0 exists
13. after release migrate fabric-customer from v0.3.0/exact-SHA-next to immutable 0.4
```

## Evidence vocabulary boundary

Highest current claim is **IMPLEMENTED + CI PROVEN** for portable contracts including project init/validation, approved evidence runners, release readiness, exact candidate identity, candidate certification and exact-byte promotion.

Do not use `FABRIC PROVEN`, `FABRIC WAREHOUSE PROVEN` or `PRODUCTION DB PROVEN` until retained approved real-service evidence exists for the exact frozen candidate/artifact.

## Repository ownership

```text
fabric-data-framework = reusable semantics/runtime/adapters/recovery/evidence/package + project/release contracts
fabric-customer       = domain DatasetConfig + semantic selections + bounded extensions + Fabric content
fabric-infra          = optional capacity/workspace/infrastructure lifecycle
```
