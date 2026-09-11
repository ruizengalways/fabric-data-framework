# Implementation map

Use this file to locate the canonical module before changing framework behavior. It is a code-ownership map, not a second architecture or release-history document.

## Top-level package ownership

```text
src/fabric_data_framework/
  contracts/       provider-neutral immutable runtime/semantic contracts
  metadata/        DatasetConfig + capability metadata and resolution
  capture/         source/capture semantics and onboarding/bootstrap
  apply/           target apply semantics
  data_plane/      Bronze/staging contracts
  quality/         DQ/reconciliation/schema/temporal quality
  orchestration/   dataset dependency planning, ready waves, parent dispatch/failure isolation
  execution/       plan compilation, execution backends, Pipeline child, bounded helpers
  adapters/        Fabric/provider transports and auth
  control_plane/   relational operational state/schema/certification
  recovery/        retry/replay/rebuild/impact/cutover/target-commit recovery
  evidence/        integration/business-path/readiness evidence
  certification/   installed-wheel/bounded/unified framework certification
  deployment/      project scaffold, delivery provenance, candidate artifact
  extensions/      bounded extension registry/contracts
  cli/             presentation/composition leaf
```

Execution-plan ownership is deliberately split by responsibility:

```text
src/fabric_data_framework/contracts/execution_plan.py
  immutable: ExecutionKind / ExecutionRole / ExecutionUnit / ExecutionPlan

src/fabric_data_framework/execution/plan_compiler.py
  planning: compile_execution_plan(...) / build_default_execution_plan(...)
  resolves capability/engine choices into immutable ExecutionPlan values
```

There is no compatibility re-export from the contract module. Callers that need compilation import the execution-layer compiler explicitly; callers that only transport or validate plan values depend only on the immutable contract.

Core dependency direction:

```text
source/business semantics
-> DatasetConfig / semantic selection
-> capability resolution
-> execution plan compiler
-> immutable ExecutionPlan
-> provider/framework execution
-> durable evidence/recovery
```

Provider mechanics must not become semantic truth.

## Semantic and planning owners

| Area | Canonical owner |
|---|---|
| Dataset semantic config | `metadata/config.py` |
| Capture fidelity/delete/history contracts | `capture/semantic_contracts.py` |
| Onboarding/overclaim guards | `capture/onboarding.py` |
| Capability resolution | `metadata/capabilities.py` |
| FULL/WATERMARK/CDC bootstrap | capture bootstrap modules |
| APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF | `apply/` |
| DQ/quarantine | `quality/rules.py` + quarantine modules |
| Reconciliation policy/check definitions | `metadata/config.py` |
| Reconciliation observation/result contracts | `contracts/reconciliation.py` |
| Declarative reconciliation evaluation | `quality/reconciliation/engine.py` |
| Strategy-specific reconciliation composition | `quality/reconciliation/scd2.py`, `quality/reconciliation/full_replace.py`, `quality/reconciliation/append.py`, `quality/reconciliation/snapshot_diff.py` |
| Immutable execution-plan contracts | `contracts/execution_plan.py` |
| Execution-plan compilation | `execution/plan_compiler.py` |
| Dataset dependency graph / ready-wave planning | `orchestration/planner.py` |
| Parent dispatch and failure isolation | `orchestration/dispatcher.py` |
| In-process/Fabric backend execution | `execution/backends/` |
| Remote Pipeline child contract/runtime | `execution/pipeline_child.py` |

Capture and apply stay orthogonal. SCD2 never upgrades source fidelity.

## Reconciliation ownership and call flow

Reconciliation is intentionally split into collection, evaluation, and execution-gate layers:

```text
DatasetConfig.reconciliation
  metadata/config.py
        |
        v
provider/project adapter
  collects bounded scalar/partition observations
        |
        v
ReconciliationObservation
  contracts/reconciliation.py
        |
        +-----------------------------+
        | strategy base metrics       |
        | FULL / APPEND / SCD2 /      |
        | SNAPSHOT_DIFF invariants     |
        +-----------------------------+
        |
        v
quality/reconciliation/engine.py
  validates evidence identity
  applies tolerance
  classifies ERROR/WARNING
  produces PASS/WARN/FAIL
        |
        v
execution/*
  decides publish/state behavior using
  required_for_state_commit + independent gates
        |
        v
Control Plane ReconciliationResult
```

Portable check kinds are:

```text
ROW_COUNT_MATCH
UNIQUE_KEY
NULL_RATE
AGGREGATE_MATCH
CHECKSUM_MATCH
CUSTOM
```

Ownership boundaries:

```text
metadata/config.py
  source-controlled check semantics, partitioning, tolerance and severity

contracts/reconciliation.py
  provider-neutral observation/metric/result values

quality/reconciliation/engine.py
  central framework authority for validation + evaluation

provider/project adapters
  observation collection only; provider Completed is never semantic PASS

execution paths
  publication/state gating; WARNING is non-blocking and
  required_for_state_commit=false makes reconciliation observability-only

deployment/delivery.py
  persists complete policy definition into existing reconciliation_policy.definition
```

Do not move generic tolerance or PASS/WARN/FAIL logic into SQL/Spark/Fabric adapters. Do not replace strategy-specific invariants with generic count/aggregate checks.

Canonical user guidance: `docs/RECONCILIATION.md`.

## APPEND/change-log execution owners

For an application change-log/audit table using `WATERMARK + bounded LOOKBACK -> APPEND`, read the concrete runtime path in this order:

```text
capture/watermark.py
-> execution/append.py
-> apply/append.py
-> quality/reconciliation/append.py
-> quality/reconciliation/engine.py
```

Ownership remains distinct:

```text
capture/watermark.py          source window/overlap semantics
execution/append.py           capture-neutral APPEND batch coordination
apply/append.py               append identity, idempotent replay, conflict fail-closed rules
quality/reconciliation/append.py             APPEND strategy-specific reconciliation metrics
quality/reconciliation/engine.py declarative policy composition
```

Entity key, event identity, and incremental cursor are separate concepts. The framework may collapse exact replay under `append_identity`; reuse of the same identity with different business payload fails closed.

## Recovery/rebuild owners

| Area | Canonical owner | Important boundary |
|---|---|---|
| Reprocess request/run-mode contract | `contracts/recovery.py` | non-normal work must be explicit/audited |
| Rebuild scope + post-rebuild state contract | `contracts/rebuild.py` | `TARGET_ONLY`, `CAPTURE_AND_TARGET`, `AUTHORITATIVE_RESET` |
| FULL_REBUILD coordinator | `recovery/rebuild.py` | requested scope must equal completed scope before state cutover |
| Issue origin + immutable impact plan | `contracts/rebuild_impact.py` | first bad point determines minimum root scope |
| Dependency-aware impact planner | `recovery/rebuild_impact.py` | only root + downstream descendants; unrelated branches excluded |
| Versioned physical target/cutover contracts | `contracts/target_version.py` | stable logical object + explicit physical version + validation/approval gate |
| Blue/green logical-binding cutover coordinator | `recovery/target_cutover.py` | optimistic generation check; no automatic old-version deletion |
| Retry/unknown outcome runtime | `recovery/runtime.py` | no blind retry after ambiguous commit |
| Quarantine replay | `recovery/replay.py` | retained immutable payload only |
| Warehouse same-transaction marker | `recovery/fabric_warehouse.py` | target mutation + marker commit together |
| Exact-session absence/recovery | `recovery/fabric_warehouse_session_absence.py` | Admin path separately authorized |

Rebuild scope invariant:

```text
TARGET_ONLY
  -> retained capture/Bronze is authoritative
  -> capture/runtime state replacement must be unchanged

CAPTURE_AND_TARGET
  -> rebuild capture/Bronze + target
  -> checkpoint/boundary may change
  -> RebuildProgressKind may not change

AUTHORITATIVE_RESET
  -> widest reset
  -> explicit post-rebuild state required
  -> RebuildProgressKind may change
```

Impact/cutover invariant:

```text
first untrustworthy root
-> compute only downstream contaminated subgraph
-> rebuild in dependency waves
-> build v2 candidate beside active v1 when blue/green is required
-> reconciliation + consumer/UAT validation + approval
-> switch stable logical binding
-> retain v1 for rollback
-> manual cleanup only
```

All three rebuild scopes are scopes of `RunMode.FULL_REBUILD`; they are not separate run modes. Permanent business-data purge is deliberately outside framework automation.

The canonical operator manual for data correctness repair/rebuild/v1-v2 cutover is `docs/REPAIR_AND_REBUILD.md`. `docs/OPERATIONS.md` owns transient runtime recovery and contains only the decision/redirect boundary for `FULL_REBUILD`.

## Fabric/provider owners

| Area | Canonical owner | Important boundary |
|---|---|---|
| Fabric auth/REST | `adapters/fabric/` | secrets not retained |
| Fabric Pipeline backend | `execution/backends/fabric_pipeline.py` | provider terminal status != semantic outcome |
| Pipeline child contract | `execution/pipeline_child.py` | exact config/plan/run correlation |
| Fabric capture transports | `adapters/fabric/capture_transports.py` | provider evidence + framework receipt |
| Fabric SQL auth | `adapters/fabric/sql_auth.py` | token/runtime credential boundary |
| Warehouse same-transaction marker | `recovery/fabric_warehouse.py` | target mutation + marker commit together |
| Exact-session absence/recovery | `recovery/fabric_warehouse_session_absence.py` | Admin path separately authorized |
| Reconciliation observation query/collection | implementation/provider adapter | collect evidence only; framework owns policy evaluation |

## Certification owners

| Area | Canonical owner |
|---|---|
| Active installed package vs wheel bytes | `src/fabric_data_framework/certification/installed.py` |
| Installed semantic smoke | `src/fabric_data_framework/certification/semantic.py` |
| Lakehouse bounded Fabric checks | `src/fabric_data_framework/certification/bounded.py` |
| Conventional one-call API | `src/fabric_data_framework/certification/simple.py` |
| Unified environment-dependent orchestrator | `src/fabric_data_framework/certification/unified.py` |
| Framework-owned reference integration fixtures/config | `certification_harness/integration_project/` plus packaged certification resources |

`certify_installed()` is the preferred high-level boundary: attest installed bytes first, then execute semantic/Fabric certification.

## Integration evidence owners

| Area | Canonical owner | Boundary |
|---|---|---|
| Spec/result/manifest/hash | `evidence/integration/evidence.py` | exact framework + integration-input identities |
| Approved run planning/config | `evidence/integration/runner.py` | bindings, runtime names, authorization, identity |
| Provider result projection | `evidence/integration/checks.py` | does not redefine semantic truth |
| Strict merge | `evidence/integration/merge.py` | contradictory reruns do not use precedence shortcuts |
| Explicit rerun projection | `evidence/integration/rerun.py` | fully bound source evidence required |
| Control Plane runner | `evidence/integration/approved/control_plane.py` | real selected backend |
| Pipeline runner | `evidence/integration/approved/pipeline.py` | native run + exact durable child outcome |
| Copy/Spark runner | `evidence/integration/approved/capture.py` | native provider evidence + verified CaptureReceipt |
| Warehouse runner | `evidence/integration/approved/warehouse.py` | mutation + marker proof |
| Ambiguous-COMMIT runner | `evidence/integration/approved/warehouse_fault.py` | real fault/recovery evidence |
| Secret scan | `evidence/safety.py` | fail closed before retention |

Identity invariant:

```text
IntegrationEvidenceSpec.framework_artifact_sha256
  = exact candidate framework wheel SHA256

IntegrationEvidenceSpec.integration_inputs_hash
  = exact framework-owned integration input bundle hash

ApprovedIntegrationRunnerConfig.framework_artifact_sha256
  = same exact candidate wheel SHA256

ApprovedIntegrationRunnerConfig.integration_inputs_hash
  = same exact integration input bundle hash
```

No customer/domain release identity is part of framework candidate certification.

## Business-path evidence owners

| Area | Canonical owner |
|---|---|
| Scenarios/observations/evaluator | `evidence/business_paths/evidence.py` |
| Driver recipe/request/receipt | `evidence/business_paths/driver.py` |
| Five-gate certification plan | `evidence/business_paths/plan.py` |
| Approved execution orchestration | `evidence/business_paths/approved_runner.py` |
| Candidate proof packaging | `evidence/business_paths/release_proof.py` |

Representative gates are:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

Drivers/observers report execution facts; evaluator/readiness code owns PASS authority.

## Release-readiness owners

| Area | Canonical owner |
|---|---|
| Readiness spec/proof/result/report | `evidence/release/readiness.py` |
| Strict proof merge | `evidence/release/merge.py` |
| Business-path partial proof packaging | `evidence/business_paths/release_proof.py` |
| Candidate certification aggregation | `evidence/release/candidate_certification.py` |
| Candidate artifact identity | `deployment/candidate_artifact.py` |
| Source-controlled policy | `release/<version>/readiness-spec.json` |
| Candidate integration-input producer | `.github/workflows/candidate-integration-inputs.yml` |
| Candidate integration evidence | `.github/workflows/candidate-integration-evidence.yml` |
| Candidate business paths | `.github/workflows/candidate-business-path-evidence.yml` |
| Candidate release proofs | `.github/workflows/candidate-release-proofs.yml` |
| Final candidate aggregation | `.github/workflows/candidate-certification.yml` |
| Exact-byte publication/promotion | `.github/workflows/release.yml` |

Final framework candidate chain:

```text
framework source/version provenance
+ framework_artifact_sha256
+ integration_inputs_hash
+ required release proofs
+ certified integration evidence
-> fail-closed ReleaseReadinessReport
-> explicit release authorization
-> exact-byte promotion
```

## Implementation project owners

| Area | Canonical owner |
|---|---|
| Config bundle hashing/materialization | `deployment/delivery.py` |
| Project scaffold/static validation | `deployment/project.py` |
| Semantic onboarding | `capture/onboarding.py` |
| Capability validation | `metadata/capabilities.py` |
| Project-specific DatasetConfig/mappings/DQ/reconciliation/bindings | implementation/domain repo |
| Provider reconciliation observation adapters + CUSTOM business controls | implementation/domain repo |
| Physical v1/v2 target names and provider-specific logical-binding adapter | implementation/domain repo |
| UAT/business validation and approval reference | implementation/domain governance |
| Old target-version deletion after rollback window | manual operator/governance process |

`project-init` never guesses source semantics or creates Fabric resources. `project-validate` is static and never upgrades itself to live evidence.

## CLI boundary

```text
cli -> reusable framework/deployment/evidence modules
reusable modules -X-> cli
```

The CLI is a presentation/composition leaf. Business/evidence semantics belong in reusable modules so the same contracts can be used from CI, notebooks and other callers.

## Documentation ownership

```text
docs/ARCHITECTURE.md                 durable architecture
docs/GETTING_STARTED.md              setup/consumption
docs/IMPLEMENTATION_PROJECT.md       real consumer project runbook
docs/DATA_PATTERNS.md                source/capture/apply decisions
docs/RECONCILIATION.md               reconciliation policy/observation/gate semantics
docs/OPERATIONS.md                   transient runtime operations/recovery
docs/REPAIR_AND_REBUILD.md           data correctness repair/rebuild/v1-v2 cutover
docs/CODE_READING_GUIDE.md           end-to-end source reading order/call graph
docs/DEVELOPMENT_GUIDE.md            safe framework modification/extension/testing/debugging/review workflow
docs/TESTING_AND_CERTIFICATION.md    certification lifecycle
docs/RELEASE.md                      release lifecycle
docs/reference/                      narrow technical contracts
docs/internal/STATE.md               exact current state
docs/internal/CAPABILITIES.md        capability/evidence matrix
docs/internal/IMPLEMENTATION_MAP.md  this module map
```

## Runtime safety implementation map

```text
src/fabric_data_framework/contracts/typed_values.py
  canonical typed codec / deterministic canonical bytes

src/fabric_data_framework/contracts/runtime.py
src/fabric_data_framework/capture/watermark.py
src/fabric_data_framework/control_plane/repository.py
src/fabric_data_framework/control_plane/sqlalchemy_repository.py
src/fabric_data_framework/execution/watermark_scd2.py
  composite watermark comparison, monotonic transition, expected-version CAS, typed persistence

src/fabric_data_framework/apply/record_hash.py
src/fabric_data_framework/apply/scd2.py
src/fabric_data_framework/apply/cdc_scd2.py
  typed change hashing and CDC tombstone/history ordering

src/fabric_data_framework/evidence/safety.py
src/fabric_data_framework/execution/backends/fabric_pipeline.py
src/fabric_data_framework/orchestration/dispatcher.py
  bounded recursive audit redaction and terminal ordinary-exception boundaries

src/fabric_data_framework/recovery/runtime.py
  unknown-commit resolver terminalization; only explicit NOT_COMMITTED permits retry

src/fabric_data_framework/quality/quarantine_store.py
  typed payload schema v2, identity/content-hash validation, create-if-absent publish
```
