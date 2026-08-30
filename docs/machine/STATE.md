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
  pull_request: 80
  merge_sha: 353b43c37077a1ffc9e22b6c76ae5494a164306e
  milestone: fail-closed 0.4 exact-candidate release-readiness aggregation
  pr_ci_actions: 33309737895
  main_ci_actions: 33309805619
  tests: 636
  python_3_11: success
  python_3_13: success
  wheel_build: success
  readiness_contract: success
  readiness_release_ready: false
  readiness_required_blockers: 15
  readiness_artifact_id: 9731622350
  readiness_artifact_archive_digest: sha256:81fe0bf1345859b512c2e4385aecccac154939325ef9c5677031aa4d7451f33a
  wheel_ci_artifact_id: 9731620873
  wheel_ci_artifact_archive_digest: sha256:5b33c71d75f7b962535bd79cf1619d3c456a7a6b727f0139a9e3f419f6bc8335
documentation_model:
  human: docs/human
  machine: docs/machine
  examples: examples
  rule: human docs explain stable understanding and use; machine docs retain exact engineering state, evidence and compact provenance
```

## Release decision

`0.4.0` remains **UNRELEASED** and feature-frozen. PR #80 adds the release-readiness contract; it does not make the source releasable. The current main CI deliberately supplied no retained release proofs, therefore all 15 required gates remained blockers and `release_ready=false`.

The two GitHub artifact digests above are archive-upload digests reported by Actions. They are **not** substitutes for the inner wheel SHA256 that must be frozen and certified for the eventual candidate. No exact 0.4 candidate artifact has been frozen yet.

CI proves portable implementation contracts only. Exact-candidate retained enterprise evidence is still incomplete, so never infer `FABRIC PROVEN`, `FABRIC WAREHOUSE PROVEN`, `PRODUCTION DB PROVEN`, or an equivalent live claim from this baseline.

## Canonical source ownership

The package has one explicit import path per owner. Compatibility shims and broad re-export facades are intentionally absent.

```text
src/fabric_data_framework/
  __init__.py               namespace marker only

  contracts/                immutable provider-neutral semantic/runtime contracts
  metadata/                 DatasetConfig and metadata validation
  capture/                  source/capture semantics and bounded-read logic
  apply/                    SCD1/SCD2/append/upsert/delete application semantics
  data_plane/               Bronze and staging contracts
  quality/                  explicit quality/reconciliation/schema/temporal modules
  orchestration/            explicit planner and dispatcher modules
  execution/                execution planning/backends
  adapters/                 provider transports and auth
  control_plane/            relational state, repository, schema and certification
  recovery/                 retry/replay/rebuild/target commit recovery
  evidence/                 retained integration evidence, release-readiness aggregation and approved exact-run executors
  deployment/               release contracts, delivery/materialization and customer project init/validation
  extensions/               bounded extension loading/contracts
  cli/                      removable leaf presentation layer, including project and release-readiness commands
```

Representative imports:

```python
from fabric_data_framework.metadata.config import DatasetConfig
from fabric_data_framework.capture.semantic_contracts import SourceSemantics
from fabric_data_framework.apply.scd2 import apply_scd2
from fabric_data_framework.quality.schema_evolution import classify_schema_evolution
from fabric_data_framework.orchestration.planner import build_dispatch_plan
from fabric_data_framework.orchestration.dispatcher import dispatch_datasets
from fabric_data_framework.control_plane.sqlalchemy_repository import SqlAlchemyControlPlaneRepository
from fabric_data_framework.evidence.integration_evidence import IntegrationEvidenceManifest
from fabric_data_framework.evidence.release_readiness import evaluate_release_readiness
from fabric_data_framework.deployment.delivery import build_release_manifest
from fabric_data_framework.deployment.project import (
    initialize_customer_project,
    validate_customer_project,
)
```

The root `__version__` symbol is intentionally absent. CLI defaults read the installed distribution version using `importlib.metadata`.

## Customer project bootstrap + dry-run boundary

Reusable project behavior is owned by `deployment/project.py`; `cli/project.py` is presentation only.

```text
fabric-framework project-init <path> --domain <domain>
fabric-framework project-validate <path>
```

`project-init` contract:

```text
default target is absent/empty
--allow-existing may fill missing scaffold files only
existing files are never overwritten
existing fabric-project.json domain must match
no DatasetConfig semantic inference
no Fabric resource creation
no live-environment mutation
no secret persistence
one customer/domain repo may contain mixed FULL/WATERMARK/CDC and SCD1/SCD2 datasets
repo boundaries follow business ownership/release/security lifecycle, not apply strategy
execution_group is the operational grouping mechanism inside one repo
```

`project-validate` dry-run contract:

```text
loads the project manifest and every DatasetConfig in config/datasets
rejects duplicate/invalid DatasetConfig bundles through canonical delivery loading
rejects dependencies that reference datasets outside the project
rejects dependency cycles
validates capture and apply engines against the capability registry
requires one semantic selection for every DatasetConfig
rejects semantic selections for unknown datasets
runs semantic capture validation/overclaim guardrails for every dataset
summarizes capture/apply strategies, execution groups and resolved engines deterministically
may write a retained JSON report
never connects to Fabric or proves live environment readiness
```

The generated inventory intentionally asks for source/business facts before DatasetConfig authoring. Neither initialization nor validation turns unknown source semantics into guessed configuration.

## 0.4 release-readiness boundary

Reusable readiness behavior is owned by `evidence/release_readiness.py`; `cli/release.py` is presentation only. The source-controlled matrix is `release/0.4.0/readiness-spec.json`.

```text
fabric-framework release-readiness \
  --spec release/0.4.0/readiness-spec.json \
  --candidate-sha <exact-source-sha> \
  [--artifact-sha256 <exact-wheel-sha256>] \
  [--proofs <release-proof-bundle>] \
  [--integration-evidence <integration-manifest>] \
  [--require-ready]
```

Fail-closed invariants:

```text
missing retained evidence -> NOT_RUN
required NOT_RUN/FAIL -> release blocker
required OUT_OF_SCOPE -> FAIL/blocker
optional OUT_OF_SCOPE -> allowed
proof bundle must match framework version + exact candidate source SHA
live IntegrationEvidenceManifest requires exact artifact SHA256 match
integration-backed gates cannot be bypassed by generic/manual release proof
release_ready=true iff every required gate is PASS
```

The 0.4 matrix currently has 15 required gates. Debezium/Kafka remains optional unless it is explicitly promoted into the 0.4 GA-certified release scope.

## Readability contracts enforced by CI

```text
framework source root contains only __init__.py
root package is namespace-only
contracts/control_plane/deployment/recovery/capture/apply/quality/orchestration roots do not rebuild broad APIs
removed flat evidence, control-plane, deployment, contract and domain files remain absent
old module imports intentionally fail
src/tests use concrete owner modules
CLI is a removable leaf
core/control_plane/evidence/deployment do not depend on CLI
project init/validation reusable logic is outside CLI
release-readiness reusable logic is outside CLI
deployment project validation imports canonical deployment.delivery owner path, not a flat/sibling facade
```

PR 78 initially failed the deployment package-boundary test because `deployment/project.py` used a relative sibling import for delivery loading. The implementation was corrected to the canonical `fabric_data_framework.deployment.delivery` owner path before merge. This remains evidence that package-boundary tests are active architecture controls rather than documentation-only rules.

Do not continue moving files or adding new product capabilities during the 0.4 feature freeze unless a release blocker requires the change.

## Evidence boundary

Highest portable claims now include:

```text
IMPLEMENTED + CI PROVEN EVIDENCE HARNESS CONTRACT
IMPLEMENTED + CI PROVEN APPROVED-RUN PREFLIGHT / READ-ONLY RUNNER CONTRACT
IMPLEMENTED + CI PROVEN EVIDENCE MERGE CONTRACT
IMPLEMENTED + CI PROVEN APPROVED CONTROL-PLANE CERTIFICATION RUNNER CONTRACT
IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT
IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT
IMPLEMENTED + CI PROVEN FABRIC WAREHOUSE SESSION-TERMINATION ABSENCE CERTIFIER CONTRACT
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE SESSION-TERMINATION RECOVERY CONTRACT
IMPLEMENTED + CI PROVEN RELEASE-READINESS AGGREGATION CONTRACT
```

`project-init`, `project-validate`, and a green `release-readiness-contract` job are portable developer/CI capabilities. They do **not** mean workspace/item authorization, credentials, physical bindings, provider execution, target commit proof, recovery, or production evidence has been proven.

## Current real-service / release gaps

```text
freeze exact candidate source SHA + inner wheel SHA256
harden release workflow to consume/prove the exact certified wheel rather than silently rebuild an equivalent-looking artifact
enterprise Entra token acquisition under selected identity
real workspace/item authorization smoke
real production control-plane certification PASS
real approved Pipeline execution
real Copy/Spark capture with approved observation and verified CaptureReceipt
representative live FULL -> REPLACE proof
representative live WATERMARK -> SCD1 proof
representative live WATERMARK -> SCD2 proof
real retry/rerun idempotency + no-unsafe-progress proof
real reconciliation fail-closed proof
real Warehouse mutation + same-transaction marker
provider-specific live COMMIT fault injector and retained ambiguous-COMMIT PASS
live exact Warehouse session identity + Admin DMV/KILL/rollback chain where required by the selected recovery proof
capacity/SKU/throttling/gateway evidence
backup/restore/HA/DR/monitoring/retention/governance evidence
live Kafka/Debezium evidence only if promoted into the public 0.4 certification promise
complete exact-candidate release proof bundle + certified IntegrationEvidenceManifest
release-readiness required blockers = 0
```

## Preferred customer-repo flow before live deployment

```text
project-init
  -> source inventory
  -> DatasetConfig authoring
  -> semantic-selections.json authoring
  -> project-validate locally
  -> domain tests
  -> Git commit / PR
  -> project-validate again in CI
  -> immutable framework release artifact
  -> environment binding / deployment
  -> approved live evidence
```

## Next engineering order

```text
1. harden exact candidate wheel/artifact handoff in the release system
2. freeze one 0.4 candidate source SHA + exact inner wheel SHA256
3. bind fabric-customer compatibility proof to that exact candidate
4. read-only Fabric item/identity smoke
5. production control-plane certification
6. approved Pipeline
7. approved Copy + Spark capture
8. representative FULL/REPLACE, WATERMARK/SCD1 and WATERMARK/SCD2 proofs
9. retry/rerun + semantic reconciliation failure drills
10. Warehouse target + same-transaction marker proof
11. real ambiguous-COMMIT recovery proof
12. decide whether Debezium/Kafka remains OUT_OF_SCOPE or becomes required
13. aggregate exact proof bundle + IntegrationEvidenceManifest
14. run release-readiness with --require-ready; required blockers must be zero
15. only then create immutable v0.4.0 release
16. after v0.4.0 release, migrate fabric-customer from v0.3.0/exact-SHA-next lane to the immutable 0.4 wheel
```

## Repository ownership

```text
fabric-data-framework = reusable semantics/runtime/adapters/recovery/evidence/package + project init/dry-run + release-readiness contracts
fabric-customer       = domain DatasetConfig + semantic selections + bounded extensions + Fabric content
fabric-infra          = optional capacity/workspace/infrastructure lifecycle
```
