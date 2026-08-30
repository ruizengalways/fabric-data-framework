# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-08-30
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
code_baseline:
  pull_request: 63
  merge_sha: 661651387fd75ad548da8b049da59529b296ec9a
  exact_candidate_head: 6721e89900d61e525ad90c628179852028432f44
  milestone: canonical-only CLI, evidence and relational control-plane package surfaces; flat legacy paths physically removed
  ci_actions: 33288912694
  tests: 575
  python_3_11: success
  python_3_13: success
  wheel: success
documentation_baseline:
  pull_request: 55
  merge_sha: 46c10ab00fefc2ca546fd7f2bea369a7037216da
  exact_candidate_head: bc791829c2f3e5be82d012f2b425adf7efab7a5e
  ci_actions: 33285255666
  human: docs/human
  machine: docs/machine
  examples: examples
  rule: human docs contain stable understanding/usage; machine docs contain exact engineering state/evidence/history
```

## Release decision

`0.4.0` remains **UNRELEASED**.

Reason: portable semantics/runtime/approved-runner contracts are broad, but exact-candidate retained real enterprise evidence is incomplete.

Never infer live proof from CI.

## Current package readability boundary

The current source tree uses canonical-only module ownership for the extracted CLI, evidence and relational control-plane clusters:

```text
src/fabric_data_framework/
  evidence/
    integration_evidence.py
    integration_checks.py
    integration_evidence_merge.py
    integration_runner.py
    approved_*_runner.py

  cli/
    main.py       tiny composition/router
    base.py       general CLI adapters
    approved.py   approved evidence / real-environment CLI adapters

  control_plane/
    schema.py                    relational schema + explicit migration contract
    io.py                        CDC/quarantine/reprocess/capture persistence helpers
    schema_evidence.py           immutable schema-observation persistence
    certification.py             backend qualification + conformance evidence
    repository.py                repository protocol + in-memory adapter
    sqlalchemy_repository.py     durable SQLAlchemy runtime repository
    operator.py                  typed read-only operational views
    target_operation_journal.py  durable target-operation CAS/event journal
```

Dependency direction:

```text
semantic/runtime/provider/recovery core
            ↑             ↑
      control_plane    evidence
                          ↑
                         cli

core -X-> cli
control_plane -X-> cli
evidence -X-> cli
```

`evidence/` is the **only** import and implementation surface for retained integration-evidence contracts, strict merge/preflight and approved exact-run executors. Root `integration_*` and `approved_*_runner.py` modules are physically absent. Old root imports intentionally fail with `ModuleNotFoundError`.

`cli/` is the **only** CLI import and implementation surface. `cli_router.py` is physically absent. CLI tests patch canonical `fabric_data_framework.cli` / `fabric_data_framework.cli.approved` modules directly.

`control_plane/` is the **only** relational control-plane implementation surface. Former flat `control_plane.py`, `control_plane_*`, `repository.py`, `relational_repository.py`, `operator.py` and `target_operation_io.py` paths are physically absent. `control_plane/__init__.py` deliberately contains no re-export imports; callers use explicit submodules.

`target_operations.py` remains outside `control_plane/` because it owns provider-neutral semantic operation identity/state. Only its durable relational CAS/event persistence belongs to `control_plane/target_operation_journal.py`.

Contract tests enforce all of the following:

```text
removed root evidence files stay absent
old root evidence imports do not resolve
cli_router.py stays absent
old cli_router import does not resolve
removed flat control-plane/repository/operator/journal files stay absent
old flat control-plane imports do not resolve
src/ and tests/ may not reintroduce removed flat import paths
evidence/ may not depend on cli/
control_plane/ may not depend on cli/
control_plane package root may not recreate a re-export API
cli/ remains removable from reusable core
```

Evidence proves existing semantic/runtime/provider/recovery truth; it must not redefine dataset semantics, capture fidelity, target commit truth or recovery behavior merely to make a check PASS.

The CLI remains a removable leaf presentation layer. `tests/test_cli_isolation.py` physically removes `cli/` from a copied package and proves reusable core imports still work. Removing `cli/` may remove the console command; it must not remove Python library/runtime functionality.

Source-code reading map: `src/fabric_data_framework/README.md`.

For unreleased `0.4.0` readability refactors, prefer one canonical path over legacy aliases. A folder extraction is acceptable only when ownership is clear, all internal imports/tests/docs are migrated together, dependency direction improves, removed paths are intentionally tested as absent, and the full contract suite stays green. CLI, evidence and relational control-plane now follow this rule; future cleanup should choose another ownership-complete cluster rather than reopening these boundaries.

## Current highest evidence labels

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

The CLI/evidence/control-plane readability refactors do not add or promote any live-service evidence label.

Do not use `FABRIC PROVEN`, `FABRIC WAREHOUSE PROVEN`, `PRODUCTION DB PROVEN`, or equivalent without retained exact-release approved real-service evidence.

## Current real-service gaps

```text
enterprise Entra token acquisition under selected identity
real workspace/item authorization smoke
real Fabric SQL Database or Azure SQL Database production-certified PASS
real approved Pipeline execution
real Copy Job execution + approved post-run observation + verified CaptureReceipt
real bounded Spark execution + approved post-run observation + verified CaptureReceipt
real Fabric Warehouse target mutation + same-transaction marker
provider-specific live Warehouse COMMIT fault injector
retained real ambiguous-COMMIT fault-drill PASS
live exact Warehouse connection_id + session_id capture using selected SQL driver
live Admin DMV observation / KILL / rollback chain
production-approved marker-absence recovery
capacity/SKU/throttling/gateway evidence
backup/restore/HA/DR/monitoring/retention/governance evidence
live Kafka coordination if included in 0.4.0 public scope
live Delta CDF bounded read/retention if included in 0.4.0 public scope
complete exact-release certified IntegrationEvidenceManifest
```

## Preferred real evidence order

```text
1. exact candidate release hash / item UUIDs / artifact fingerprints
2. read-only item smoke
3. production control-plane certification
4. strict merge item + control-plane prerequisites
5. approved Pipeline
6. approved Copy Job / Spark capture
7. approved Warehouse target+marker recovery
8. optional provider-specific real ambiguous-COMMIT fault drill
9. optional exact-session termination recovery under separate Admin authority
10. strict merge required evidence
11. integration-evidence-validate --require-certified
12. Kafka/Delta live only if in public release promise
13. exact-candidate release audit
14. only then consider 0.4.0 release
```

## Current reusable-work boundary

Do not add another generic Warehouse recovery algorithm.

Commit proof, ambiguous-COMMIT evidence separation, exact-session absence proof, and approved session-termination recovery are implemented at CI-contract level.

Without real enterprise inputs, useful next work should be limited to:

```text
exact-candidate release/evidence preparation
or
provider-specific live fault/identity integration when the actual enterprise mechanism is known
```

For readability work, prefer isolated ownership refactors over broad directory churn. CLI, evidence and relational control-plane are canonical-only packages. Any next extraction should migrate the real implementation and all consumers together, delete superseded flat paths, and prove their absence in CI rather than retaining compatibility shims.

Avoid broadening provider surface only to increase feature count.

## Repository ownership

```text
fabric-data-framework = reusable semantics/runtime/adapters/recovery/evidence/package
fabric-customer       = business/domain DatasetConfig + bounded extensions + Fabric content
fabric-infra          = optional capacity/workspace/infrastructure lifecycle
```

Initial enterprise evaluation may proceed without `fabric-infra`.
