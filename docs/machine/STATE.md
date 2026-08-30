# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-08-30
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
code_baseline:
  pull_request: 78
  merge_sha: 8094e4742507c23ffad16220aebd6862876a3cd0
  exact_candidate_head: 10c010560ab9e61f46d50cdfadbbc160266f3cd7
  milestone: customer/domain project init plus complete source-controlled project dry-run validation
  ci_actions: 33305885406
  tests: 627
  python_3_11: success
  python_3_13: success
  wheel: success
documentation_model:
  human: docs/human
  machine: docs/machine
  examples: examples
  rule: human docs explain stable understanding and use; machine docs retain exact engineering state, evidence and compact provenance
```

## Release decision

`0.4.0` remains **UNRELEASED**. CI proves portable implementation contracts only. Exact-candidate retained enterprise evidence is still incomplete, so never infer `FABRIC PROVEN`, `FABRIC WAREHOUSE PROVEN`, `PRODUCTION DB PROVEN`, or an equivalent live claim from this baseline.

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
  evidence/                 retained evidence and approved exact-run executors
  deployment/               release contracts, delivery/materialization and customer project init/validation
  extensions/               bounded extension loading/contracts
  cli/                      removable leaf presentation layer, including project commands
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
deployment project validation imports canonical deployment.delivery owner path, not a flat/sibling facade
```

PR 78 initially failed the deployment package-boundary test because `deployment/project.py` used a relative sibling import for delivery loading. The implementation was corrected to the canonical `fabric_data_framework.deployment.delivery` owner path before merge. This is evidence that package-boundary tests remain active architecture controls rather than documentation-only rules.

Do not continue moving files merely to maximize folder count. Inspect `execution/`, `adapters/`, `extensions/`, `metadata/`, and `data_plane/` independently; remove another facade only where ownership is unambiguous and readability materially improves.

## Evidence boundary

Highest portable claims remain:

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
```

`project-init` and `project-validate` are local/source-control developer and CI capabilities. A successful dry run means the source-controlled project is internally valid under framework contracts; it does **not** mean workspace/item authorization, credentials, physical bindings, provider execution, target commit proof, recovery, or production evidence has been proven.

## Current real-service gaps

```text
enterprise Entra token acquisition under selected identity
real workspace/item authorization smoke
real production control-plane certification PASS
real approved Pipeline execution
real Copy/Spark capture with approved observation and verified CaptureReceipt
real Warehouse mutation + same-transaction marker
provider-specific live COMMIT fault injector and retained ambiguous-COMMIT PASS
live exact Warehouse session identity + Admin DMV/KILL/rollback chain
capacity/SKU/throttling/gateway evidence
backup/restore/HA/DR/monitoring/retention/governance evidence
live Kafka/Delta evidence if included in the public release promise
complete exact-release certified IntegrationEvidenceManifest
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
  -> immutable release artifact
  -> environment binding / deployment
  -> approved live evidence
```

## Preferred real evidence order

```text
1. freeze exact candidate hashes, item IDs and artifact fingerprints
2. read-only item smoke
3. production control-plane certification
4. strict prerequisite evidence merge
5. approved Pipeline
6. approved Copy/Spark capture
7. approved Warehouse target + marker recovery
8. optional real ambiguous-COMMIT fault drill
9. optional exact-session termination recovery
10. strict merge and --require-certified validation
11. exact-candidate release audit
12. only then consider 0.4.0 release
```

## Repository ownership

```text
fabric-data-framework = reusable semantics/runtime/adapters/recovery/evidence/package + project init/dry-run contracts
fabric-customer       = domain DatasetConfig + semantic selections + bounded extensions + Fabric content
fabric-infra          = optional capacity/workspace/infrastructure lifecycle
```
