# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-08-30
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
code_baseline:
  merge_sha: b9187d93015d921614147831da1336b2d91f3e22
  milestone: approved Warehouse session-termination recovery wiring
  ci_actions: 33284190041
  tests: 534
  python_3_11: success
  python_3_13: success
  wheel: success
latest_pre_reorg_docs_checkpoint:
  merge_sha: c5baff6318b5facc366fa9466d23041291835fd5
  ci_actions: 33284381347
documentation_model:
  pull_request: 55
  human: docs/human
  machine: docs/machine
  examples: examples
  rule: human docs contain stable understanding/usage; machine docs contain exact engineering state/evidence/history
```

## Release decision

`0.4.0` remains **UNRELEASED**.

Reason: portable semantics/runtime/approved-runner contracts are broad, but exact-candidate retained real enterprise evidence is incomplete.

Never infer live proof from CI.

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

Avoid broadening provider surface only to increase feature count.

## Repository ownership

```text
fabric-data-framework = reusable semantics/runtime/adapters/recovery/evidence/package
fabric-customer       = business/domain DatasetConfig + bounded extensions + Fabric content
fabric-infra          = optional capacity/workspace/infrastructure lifecycle
```

Initial enterprise evaluation may proceed without `fabric-infra`.
