# MACHINE CAPABILITY MATRIX

This file describes **current capability ownership and evidence level**. Exact executable identity belongs in `docs/machine/STATE.md`.

Evidence vocabulary:

```text
REFERENCE / CONTRACT
  deterministic implementation or typed contract exists

CI PROVEN
  source/build/installed-wheel checks succeeded for the exact executable baseline recorded in STATE.md

RELEASE PROVEN
  immutable published artifact/checksum evidence exists

FABRIC PROVEN
  retained approved real Microsoft Fabric evidence exists for exact wheel bytes

EXTERNAL
  enterprise/platform control outside this repository
```

Never upgrade `CI PROVEN` to `FABRIC PROVEN` by inference.

## Repository ownership

| Responsibility | Owner | Current boundary |
|---|---|---|
| Reusable capture/apply/recovery framework | `fabric-data-framework` | active |
| Framework wheel/package lifecycle | `fabric-data-framework` | active |
| Installed-wheel certification | `fabric-data-framework` | active |
| Real Fabric framework certification | `fabric-data-framework` | active; live evidence still required |
| Deterministic production-like source workload | `fabric-customer` | independent, framework-agnostic |
| Expected source/business truth + workload digest | `fabric-customer` | independent, framework-agnostic |
| Project DatasetConfig/mappings/bindings | implementation/domain repo | per real project |
| Fabric capacity/workspace/permissions lifecycle | `fabric-infra` / enterprise platform | external to framework package |

Dependency invariant:

```text
implementation/domain repo -> approved fabric-data-framework wheel

fabric-customer -X-> fabric-data-framework
fabric-data-framework -X-> fabric-customer
```

Historical field names containing `customer` in readiness/integration serialization are compatibility labels only.

## Semantic / runtime capabilities

| Capability | Framework owner | Evidence |
|---|---|---|
| Immutable DatasetConfig + effective config hashing | metadata/config | REFERENCE + CI PROVEN |
| Capture/Bronze semantic contracts | capture semantic modules | REFERENCE + CI PROVEN |
| FULL / WATERMARK / CDC capture contracts | capture | REFERENCE + CI PROVEN |
| APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF | apply | REFERENCE + CI PROVEN |
| FULL incomplete-snapshot destructive guard | capture/apply | REFERENCE + CI PROVEN + installed-wheel smoke path |
| Provider-neutral CDC ordering/dedupe/checkpoint | capture CDC | REFERENCE + CI PROVEN + installed-wheel smoke |
| Watermark composite ordering / overlap contract | capture watermark | REFERENCE + CI PROVEN + installed-wheel smoke |
| CaptureReceipt / progress authority | contracts/capabilities | REFERENCE + CI PROVEN |
| DQ / quarantine / reconciliation fail-closed behavior | quality/runtime | REFERENCE + CI PROVEN |
| Retry / replay / backfill / unknown-commit recovery contracts | recovery/runtime | REFERENCE + CI PROVEN |
| Parent Pipeline dependency/fail-at-end behavior | orchestration | REFERENCE + CI PROVEN |
| Execution-group policy and project validation | deployment/orchestration | REFERENCE + CI PROVEN |

Semantic support is not live provider certification. Capture fidelity remains the ceiling of truthful downstream history fidelity.

## Package lifecycle and certification

| Capability | Owner | Evidence |
|---|---|---|
| Main CI builds exact wheel + SHA256SUMS + CANDIDATE.json | framework CI | CI PROVEN |
| Clean interpreter wheel install | `certification/smoke_installed_wheel.py` workflow | CI PROVEN |
| Installed package payload vs candidate wheel byte attestation | certification installed module | CI PROVEN |
| Installed metadata/config semantic smoke | certification | CI PROVEN |
| Installed incremental watermark semantic smoke | certification | CI PROVEN |
| Installed CDC normalization/dedupe smoke | certification | CI PROVEN |
| Bounded Lakehouse Delta read/write | certification bounded suite | REFERENCE; FABRIC PROOF REQUIRED for current exact wheel |
| Bounded FULL/REPLACE, SCD1, SCD2, retry, reconciliation in Fabric | certification bounded suite | REFERENCE; FABRIC PROOF REQUIRED |
| Unified environment-dependent certification | certification/integration runners | REFERENCE + CI PROVEN contracts; live resources required |

The current exact executable baseline and wheel SHA are intentionally not repeated here; use `docs/machine/STATE.md`.

## Implementation/domain project contract

A real framework-consuming project is **not** `fabric-customer`.

| Capability | Owner | Evidence |
|---|---|---|
| Non-destructive project scaffold | framework deployment/project | REFERENCE + CI PROVEN |
| `project-init` / `project-validate` | framework CLI + deployment/project | REFERENCE + CI PROVEN |
| Dependency/cycle/capability validation | framework deployment/project | REFERENCE + CI PROVEN fail-closed |
| Semantic-selection coverage / overclaim guard | deployment + capture onboarding | REFERENCE + CI PROVEN |
| Mixed FULL/WATERMARK/CDC + SCD1/SCD2 in one domain repo | DatasetConfig/project contract | REFERENCE MODEL + CI PROVEN |
| Project-specific DatasetConfig/mappings/bindings | implementation/domain repo | project-owned; framework validates contract |

Project validation is static/local unless a separate end-to-end Fabric run is performed. It does not prove source connectivity, workspace authorization, provider execution or target commit.

## Independent customer simulator/testbed

Current `fabric-customer` capability is source/workload simulation only.

| Capability | Owner | Evidence |
|---|---|---|
| No runtime/dev framework dependency | customer architecture guard/CI | CI PROVEN |
| No production Python framework import | AST architecture guard | CI PROVEN |
| Deterministic Day 1-7 source scenarios | customer simulator | CI PROVEN |
| Snapshot / incremental / Debezium-shaped CDC deliveries | customer simulator | CI PROVEN |
| Delete / duplicate / late arrival / schema evolution / correction / replay | customer scenarios | CI PROVEN |
| Framework-neutral current/history/source-event truth | customer simulator | CI PROVEN |
| `SHA256SUMS` + `WORKLOAD.json` | customer materializer | CI PROVEN |
| `fabric-customer verify` tamper detection | customer simulator/tests | CI PROVEN |
| Real Fabric Notebook/Copy/Warehouse/Eventstream source execution | customer Fabric assets/runbook | FABRIC PROOF REQUIRED |

When used for framework v1/v2 comparison, both implementations must consume the same verified `workload_digest`.

## Fabric/provider execution capabilities

| Capability | Framework owner | Current evidence |
|---|---|---|
| Fabric Data Pipeline backend | execution backend | IMPLEMENTED + CI PROVEN CONTRACT |
| Copy transport/provider integration | Fabric capture adapter | IMPLEMENTED + CI PROVEN CONTRACT |
| Spark Job Definition/provider integration | Fabric Spark adapter | IMPLEMENTED + CI PROVEN CONTRACT |
| Provider Completed insufficient for semantic PASS | execution/capture adapters | REFERENCE + CI PROVEN |
| Fabric SQL Database Control Plane contract | control-plane repository | REFERENCE + CI PROVEN CONTRACT |
| Warehouse same-transaction target marker | Warehouse recovery | IMPLEMENTED + CI PROVEN CONTRACT |
| Ambiguous-COMMIT reconcile / exact-session recovery contract | Warehouse recovery | IMPLEMENTED + CI PROVEN CONTRACT |

No row above is a live Fabric claim until retained exact-wheel execution evidence exists.

## Approved integration evidence

| Capability | Framework owner | Evidence |
|---|---|---|
| Evidence spec/result/manifest/hash | evidence modules | IMPLEMENTED + CI PROVEN |
| Approved-run preflight | integration runner | IMPLEMENTED + CI PROVEN |
| Strict staged evidence merge | integration evidence merge | IMPLEMENTED + CI PROVEN fail-closed |
| Pipeline / Copy / Spark / Warehouse runners | approved integration runners | IMPLEMENTED + CI PROVEN CONTRACTS |
| Retained text secret scanning | evidence safety | IMPLEMENTED + CI PROVEN fail-closed |
| Real exact-wheel integration evidence | environment execution | NOT YET RETAINED for current executable baseline |

Legacy integration fields may retain framework/domain hash separation. Do not reinterpret those serialized fields as a runtime dependency on the current `fabric-customer` repo.

## Release readiness

| Capability | Framework owner | Evidence |
|---|---|---|
| Source-controlled 0.4 readiness matrix | release/readiness spec | CONTRACT + CI PROVEN |
| Exact candidate source/wheel readiness binding | release-readiness evidence | IMPLEMENTED + CI PROVEN fail-closed |
| Strict proof merge / contradictory evidence rejection | release-readiness merge | IMPLEMENTED + CI PROVEN |
| Candidate artifact manifest | deployment candidate artifact | IMPLEMENTED + CI PROVEN |
| Candidate certification aggregation | candidate certification | IMPLEMENTED + CI PROVEN |
| Exact certified wheel promotion without rebuild | release workflow | IMPLEMENTED + CI PROVEN CONTRACT |

Ordinary CI remains intentionally fail-closed with 15 required readiness blockers for the current exact executable baseline. One serialized gate is historically named `customer.compatibility`; treat it as a deprecated compatibility gate label, not current simulator ownership.

## Real proof still missing for current executable bytes

| Proof / capability | State |
|---|---|
| Frozen exact 0.4 candidate | NOT YET |
| Exact-wheel real Fabric bounded certification | NOT YET RETAINED |
| Fabric identity/workspace authorization evidence | NOT YET RETAINED |
| Control Plane live certification | NOT YET RETAINED |
| Live Pipeline/Copy/Spark for current wheel | NOT YET RETAINED |
| Live Warehouse commit/recovery evidence | NOT YET RETAINED |
| Required representative business-path live evidence | NOT YET RETAINED |
| Readiness blockers = 0 | NOT YET; ordinary CI has 15 blockers |
| Capacity/IAM/network/DR/monitoring/governance | EXTERNAL / NOT YET RETAINED |

## Historical release truth

```text
v0.3.0 immutable release = RELEASE PROVEN for v0.3.0
0.4.0 source             = DEVELOPMENT / UNRELEASED / READINESS BLOCKED
release_allowed          = false
candidate_status         = not_frozen
```

For the exact current Git SHA, CI runs, wheel SHA256 and next real-Fabric action, read `docs/machine/STATE.md`.
