# Capability matrix

This file tracks capability ownership and **evidence level**, not exact candidate SHA/run IDs. Exact current release/Fabric state belongs in [`STATE.md`](STATE.md).

## Evidence vocabulary

```text
IMPLEMENTED
  reusable code/typed contract exists

SOURCE PROVEN
  deterministic source/contract tests exist and the selected executable CI has passed them

INSTALLED-WHEEL PROVEN
  clean installed-wheel package boundary has passed for the selected exact wheel

FABRIC PROVEN
  retained approved real Microsoft Fabric evidence exists for the selected exact wheel

EXTERNAL
  enterprise/platform control outside this repository
```

Never infer `FABRIC PROVEN` from a local/CI result.

## Ownership

| Responsibility | Owner |
|---|---|
| Capture/apply/orchestration/recovery framework | `fabric-data-framework` |
| Framework wheel/package lifecycle | `fabric-data-framework` |
| Installed-wheel + real-Fabric framework certification | `fabric-data-framework` |
| Framework integration-input/candidate evidence production | `fabric-data-framework` |
| Deterministic production-like source workload + expected truth | `fabric-customer` |
| Project DatasetConfig/mappings/bindings | implementation/domain repo |
| Physical v1/v2 target names + environment-specific logical-binding adapter | implementation/domain repo |
| Capacity/workspace/permission infrastructure | `fabric-infra` / enterprise platform |
| Irreversible business-data purge | manual operator/governance process |

Dependency invariant:

```text
implementation/domain repo -> approved fabric-data-framework wheel
fabric-customer -X-> fabric-data-framework
fabric-data-framework -X-> fabric-customer
```

## Semantic/runtime capability

| Capability | Canonical area | Evidence boundary |
|---|---|---|
| Immutable DatasetConfig/effective config hashing | `metadata/` | IMPLEMENTED + source contract |
| FULL / WATERMARK / CDC capture semantics | `capture/` | IMPLEMENTED + source contract |
| Source-fidelity/history overclaim guard | `capture/onboarding.py` | IMPLEMENTED + source contract |
| APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF | `apply/` | IMPLEMENTED + source contract |
| APPEND stable identity / exact replay no-op / conflicting identity fail-closed | `execution/append.py` + `apply/append.py` + `quality/append.py` | IMPLEMENTED + source contract |
| FULL incomplete-snapshot destructive guard | capture/apply | IMPLEMENTED; real Fabric proof tied to selected candidate |
| CDC ordering/dedupe/checkpoint | capture/adapters | IMPLEMENTED; provider live proof separate |
| Watermark ordering/lookback/bootstrap contracts | capture | IMPLEMENTED; provider live proof separate |
| CaptureReceipt/progress authority | `contracts/` | IMPLEMENTED |
| DQ/quarantine/reconciliation fail-closed | `quality/` + runtime | IMPLEMENTED |
| Retry/replay/backfill/unknown-commit recovery | `recovery/` | IMPLEMENTED |
| FULL_REBUILD scopes: TARGET_ONLY / CAPTURE_AND_TARGET / AUTHORITATIVE_RESET | `contracts/rebuild.py` + `recovery/rebuild.py` | IMPLEMENTED; source contract tests required; live project physical rebuild remains environment-specific |
| Dependency-aware contaminated-subgraph planning | `contracts/rebuild_impact.py` + `recovery/rebuild_impact.py` | IMPLEMENTED; computes roots + downstream descendants + rebuild waves and excludes unrelated branches |
| Versioned target + blue/green logical cutover contract | `contracts/target_version.py` + `recovery/target_cutover.py` | IMPLEMENTED; requires candidate build + reconciliation + consumer/UAT validation + matching approval reference |
| Old-version retention for rollback | target cutover contract | IMPLEMENTED semantic rule; physical retention is project-owned |
| Automated permanent business-data purge | outside framework | intentionally NOT IMPLEMENTED; manual governance boundary |
| Parent Pipeline dependency/fail-at-end behavior | orchestration/execution | IMPLEMENTED |
| Project init/validation/execution-group policy | deployment/CLI | IMPLEMENTED |

Semantic support does not imply every physical provider has retained live Fabric proof.

## Package/certification capability

| Capability | Owner | Evidence boundary |
|---|---|---|
| Build exact wheel + `CANDIDATE.json`/checksum provenance | CI/deployment | IMPLEMENTED |
| Clean interpreter wheel install | installed-wheel workflow | IMPLEMENTED |
| Installed package payload vs wheel bytes | `src/fabric_data_framework/certification/installed.py` | INSTALLED-WHEEL gate |
| Installed metadata/watermark/CDC semantic smoke | certification | INSTALLED-WHEEL gate |
| Lakehouse Delta bounded certification | certification bounded suite | FABRIC proof required per exact candidate |
| FULL/SCD1/SCD2/retry/reconciliation bounded checks | certification bounded suite | FABRIC proof required per exact candidate |
| Framework-owned integration bundle | certification integration project/workflow | IMPLEMENTED |
| Unified Control Plane/Pipeline/Copy/Spark/Warehouse certification | approved integration runners | IMPLEMENTED contracts; FABRIC proof required |
| Five representative business paths | evidence/business-path runners | IMPLEMENTED contracts; FABRIC proof required |

## Integration/candidate identity

Framework candidate certification uses exactly two independent identities:

```text
framework_artifact_sha256
integration_inputs_hash
```

| Capability | Owner | Boundary |
|---|---|---|
| Integration spec/result/manifest | `evidence/integration_evidence.py` | carries both identities |
| Approved integration run planning | `evidence/integration_runner.py` | validates identity, bindings, prerequisites, authorizations |
| Strict staged merge/rerun | evidence merge/rerun modules | contradictory evidence is not silently overwritten |
| Pipeline/Copy/Spark/Warehouse runners | approved runner modules | provider result must converge with framework semantic evidence |
| Retained secret scan | `evidence/safety.py` | fail closed before retention |
| Candidate readiness/proof merge | release-readiness modules | exact identities must agree |
| Candidate certification aggregation | `evidence/candidate_certification.py` | aggregation only; no provider execution |

No customer/domain release identity participates in framework candidate certification.

## Implementation project contract

| Capability | Owner | Evidence boundary |
|---|---|---|
| Project scaffold | framework deployment/project | static source-controlled scaffold |
| `project-init` / `project-validate` | framework CLI/deployment | static validation |
| Mixed FULL/WATERMARK/CDC capture + APPEND/SCD1/SCD2 apply patterns in one domain repo | DatasetConfig/project contract | supported model |
| Project mappings/DQ/bindings/deploy content | implementation/domain repo | project-owned |
| Rebuild physical mutation callback for the approved scope | implementation/domain repo | project-owned physical adapter; framework enforces scope/state gates |
| Physical target version materialization and logical-binding switch | implementation/domain repo | project-owned adapter; framework enforces candidate/cutover identity and gates |
| UAT/business validation evidence + approval reference | implementation/domain governance | project-owned evidence consumed by cutover gate |
| Real source connectivity/end-to-end result | implementation + environment | requires environment execution |

Static project validation does not prove Fabric connectivity or target commit.

## Independent customer simulator

| Capability | Owner | Boundary |
|---|---|---|
| Framework-free source simulation | `fabric-customer` | architecture invariant |
| Deterministic snapshot/incremental/CDC-shaped deliveries | `fabric-customer` | simulator/test contract |
| Delete/duplicate/late/schema-evolution/correction/replay scenarios | `fabric-customer` | simulator/test contract |
| Expected current/history/source-event truth | `fabric-customer` | source/business truth |
| `SHA256SUMS` + `WORKLOAD.json` + `workload_digest` | `fabric-customer` | workload identity |
| Real Fabric source delivery assets | `fabric-customer` | real Fabric proof separate |

For framework-version regression, compare against the same verified `workload_digest`.

## Fabric/provider capability

| Capability | Framework area | Current proof boundary |
|---|---|---|
| Fabric Pipeline backend | execution/adapters | implementation/source tests; live Fabric proof required |
| Copy capture | Fabric capture adapter | implementation/source tests; live Fabric proof required |
| Spark capture | Fabric adapter/runtime | implementation/source tests; live Fabric proof required |
| Fabric SQL Database Control Plane | control-plane | reference/source conformance; live Fabric proof required |
| Warehouse target mutation + marker | recovery/approved runner | source-tested contract; live Fabric proof required |
| Ambiguous-COMMIT recovery/session absence | recovery | source-tested contract; live fault evidence required |
| Logical target binding/view/alias implementation for a real project | implementation adapter | provider/environment-specific; live validation required |

## Release readiness

Executable gate definitions live in `release/<version>/readiness-spec.json`, certification resources and workflow/code contracts. This Markdown does not duplicate the full gate matrix.

Current high-level truth is always read from [`STATE.md`](STATE.md). Public `v0.3.0` remains the release truth until a later exact candidate is explicitly frozen, fully evidenced, authorized and published.
