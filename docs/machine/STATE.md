# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-08-30
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
code_baseline:
  pull_request: 57
  merge_sha: 3ddbb873029a13985af4e563228629c1efc4f7d4
  exact_candidate_head: faf109101e1eaedce2121512ad67ab2569a5808c
  milestone: CLI extracted as removable leaf package plus source-code navigation boundary
  ci_actions: 33286548611
  tests: 539
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

Active command-line implementation is isolated under:

```text
src/fabric_data_framework/cli/
  main.py       tiny composition/router
  base.py       general CLI adapters
  approved.py   approved evidence / real-environment CLI adapters
```

Core dependency invariant:

```text
cli -> framework core
framework core -X-> cli
```

`tests/test_cli_isolation.py` physically removes `cli/` from a copied package and proves reusable core imports still work. Removing `cli/` is allowed to remove the console command; it must not remove Python library/runtime functionality.

`src/fabric_data_framework/cli_router.py` is deprecated compatibility only and contains no command/business implementation.

Source-code reading map: `src/fabric_data_framework/README.md`.

Do not broadly move mature flat modules only for aesthetics. Future folder extraction requires a clear ownership boundary, preserved/versioned import compatibility, improved dependency direction, and full contract-suite proof.

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

The CLI refactor does not add or promote any live-service evidence label.

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

For readability work, prefer isolated leaf/ownership refactors over broad directory churn. Potential future clusters such as control-plane or evidence modules should be separate, contract-preserving slices only if their dependency boundaries are demonstrably clearer.

Avoid broadening provider surface only to increase feature count.

## Repository ownership

```text
fabric-data-framework = reusable semantics/runtime/adapters/recovery/evidence/package
fabric-customer       = business/domain DatasetConfig + bounded extensions + Fabric content
fabric-infra          = optional capacity/workspace/infrastructure lifecycle
```

Initial enterprise evaluation may proceed without `fabric-infra`.
