# MACHINE IMPLEMENTATION MAP

Use this file to locate the implementation owner for a framework behavior before editing code.

## Top-level package ownership

```text
src/fabric_data_framework/
  config / semantic contracts
  capture / apply / CDC
  capability resolution / execution planning
  provider adapters / Fabric transports
  target-operation recovery / Warehouse commit proof
  relational control plane
  evidence/ integration evidence / approved runners
  extensions
  delivery / deployment
  cli/ presentation layer
```

Code-browser entrypoint: `src/fabric_data_framework/README.md`.

## Semantic configuration

| Area | Primary owner | Notes |
|---|---|---|
| Dataset semantic truth | `config.py` | immutable `DatasetConfig` and nested policies |
| Shared typed contracts | `contracts/` | capture/recovery/runtime value objects |
| Orthogonal capture semantics | `capture/semantic_contracts.py` | source/change/read/delete/Bronze/provider dimensions + 14 presets |
| Semantic onboarding | `capture/onboarding.py` | validates pattern combinations and overclaim constraints |
| Watermark semantics | watermark/capture modules | checkpoint/lookback/bounds/order rules |
| Snapshot -> CDC bootstrap | `capture/bootstrap_cdc.py` or corresponding bootstrap module | fenced handoff |
| Full baseline -> WATERMARK bootstrap | `capture/bootstrap_watermark.py` or corresponding bootstrap module | fenced handoff |

## Capture / Bronze / Apply

| Area | Primary owner |
|---|---|
| Bronze lineage/record | `bronze.py` |
| Capture source types | `capture/` |
| File/API replay guardrails | `capture/` file/API modules |
| Apply strategies | `apply/` |
| CDC order/dedupe/checkpoint | CDC modules |
| Debezium/Kafka adapter | CDC adapter modules |
| Delta CDF adapter | Delta/CDF adapter modules |

Rule: do not add engine-specific behavior to semantic config when a capability/adapter layer can own it.

## Execution / capability selection

Implementation includes capability profiles/resolver and immutable execution-plan units.

Expected ownership boundary:

```text
DatasetConfig semantics
  -> capability resolver
  -> immutable ExecutionPlan
  -> provider/framework execution unit
```

When engine selection is wrong, inspect capability resolution/plan compilation before modifying business semantics.

## Fabric/provider adapters

| Area | Primary owner |
|---|---|
| Fabric REST auth/token-provider abstraction | Fabric auth modules |
| Data Pipeline execution backend | Fabric Pipeline backend modules |
| Copy Job REST transport | Fabric Copy transport modules |
| Spark Job Definition REST transport | Fabric Spark transport modules |
| Provider-native capture evidence conversion | Fabric capture adapter modules |

Provider terminal status is transport evidence, not framework semantic success.

## Target operations / recovery

| Area | Primary owner | Critical invariant |
|---|---|---|
| Stable logical target operation | `target_operations.py` | operation identity independent of physical retry/run ID |
| Persistent target-operation CAS | `control_plane/target_operation_journal.py` | UNKNOWN/IN_PROGRESS cannot blind retry |
| Generic target probes | `recovery/target_probe.py` | tri-state COMMITTED/NOT_COMMITTED/UNRESOLVED |
| Fabric Warehouse marker store/probe | `recovery/fabric_warehouse.py` | target mutation + marker in same transaction |
| Warehouse session absence proof | `recovery/fabric_warehouse_session_absence.py` | exact session + open tx + Admin KILL + post-KILL marker reread |
| Warehouse fault injection contract | `recovery/warehouse_fault_injection.py` | bounded arm/disarm/verify, not commit/absence authority |
| Provider-native downstream recovery | recovery/provider modules | native cursor/state remains separate from semantic checkpoint |

## Relational control plane

| Area | Primary owner |
|---|---|
| Production-oriented SQL repository | `control_plane/sqlalchemy_repository.py` |
| Backend certification profiles/contracts | control-plane certification modules |
| Schema materialization/migration tooling | control-plane/delivery/CLI modules |

Runtime rule: production execution never silently provisions/migrates schema.

## Integration evidence package

Canonical implementation owner:

```text
src/fabric_data_framework/evidence/
```

| Area | Primary owner |
|---|---|
| Evidence check kinds/status/spec/manifest | `evidence/integration_evidence.py` |
| Safe projection from existing provider/runtime outcomes | `evidence/integration_checks.py` |
| Credential-free preflight/runtime env-var requirements | `evidence/integration_runner.py` |
| Strict partial manifest merge | `evidence/integration_evidence_merge.py` |
| Retained evidence secret scanning | `retained_evidence_safety.py` |

Root-level `integration_*` evidence modules are intentionally absent. `evidence/` is the only import and implementation surface.

Merge rule: contradictory substantive reruns conflict; no latest/PASS/FAIL precedence.

Evidence ownership rule:

```text
semantic/runtime/provider/recovery core
                 ↑
             evidence
```

Evidence proves existing contracts. It must not redefine dataset semantics, capture fidelity, target commit truth, or recovery behavior merely to make an evidence check PASS.

## Approved runners

| File | Exact responsibility |
|---|---|
| `evidence/approved_control_plane_runner.py` | exact-spec production-eligible control-plane conformance + external enterprise evidence references |
| `evidence/approved_pipeline_runner.py` | remote Pipeline execution + exact durable child `DatasetDispatchOutcome` requirement |
| `evidence/approved_capture_runner.py` | Copy/Spark exact-release execution + observation/native evidence/`CaptureReceipt` validation |
| `evidence/approved_warehouse_runner.py` | target operation claim + same-transaction Warehouse marker + UNKNOWN reconciliation |
| `evidence/approved_warehouse_fault_runner.py` | real ambiguous-COMMIT evidence drill; optional separately-authorized session-termination recovery |

Root-level `approved_*_runner.py` modules are intentionally absent; approved runners are imported only from `fabric_data_framework.evidence`.

Do not collapse approved runners into a single high-privilege command. Their separate authorization/evidence surfaces are intentional.

## Extension registry

Primary owner: `extensions/registry.py` and `extensions/`.

Known controlled entry points:

```text
fabric_data_framework.capture_observers
fabric_data_framework.spark_execution_data
fabric_data_framework.warehouse_mutations
fabric_data_framework.warehouse_commit_fault_injectors
```

Extension artifact identity must be pinned in exact release provenance where approved runners require it.

## Delivery / deployment / release

| Area | Primary owner |
|---|---|
| Config bundle hashing/materialization | `delivery.py` and related modules |
| Release manifest/provenance | deployment/delivery modules |
| Package metadata/version/console script | `pyproject.toml` |
| CI | `.github/workflows/ci.yml` |
| Release artifact workflow | `.github/workflows/release.yml` |

## CLI presentation boundary

All active CLI implementation lives under:

```text
src/fabric_data_framework/cli/
```

Ownership:

| File | Exact responsibility |
|---|---|
| `cli/main.py` | tiny composition root; routes command family only |
| `cli/base.py` | general validation, metadata, deployment and preflight commands |
| `cli/approved.py` | approved evidence / real-environment command adapters |
| `cli/__init__.py` | public console-script `main` export |
| `cli/__main__.py` | module execution entrypoint |
| `cli/README.md` | code-local dependency/ownership rule |
| `cli/` | only CLI import/implementation surface |

Non-negotiable dependency rule:

```text
cli -> evidence/core
evidence -X-> cli
core -X-> cli
```

`tests/test_cli_isolation.py` proves both:

```text
non-CLI source does not import the CLI package
physical removal of cli/ does not break core package/capture/apply/execution/recovery/runtime imports
```

The console script may cease to function if `cli/` is removed; that is expected. Library/runtime functionality must remain independent.

Do not add top-level CLI compatibility modules. Put command adapters inside `cli/` and keep reusable semantics/runtime outside it.

## Readability / future folder extraction rule

After CLI and evidence extraction, the main mature flat cluster still worth considering separately is:

```text
control_plane*.py
repository.py / relational_repository.py
```

Do not move it merely for aesthetics. Extract a folder only when:

```text
ownership boundary is clear
public/import compatibility is preserved or intentionally versioned
dependency direction improves
full contract suite proves no behavior regression
```

Do not combine a future control-plane extraction with unrelated feature/evidence/CLI changes.

## Tests as executable specification

`tests/` mirrors contracts rather than only code coverage.

When changing a semantic/recovery/evidence guarantee:

```text
1. identify the contract/invariant
2. add/change fail-closed tests
3. change implementation
4. run full suite
5. update machine docs
6. only then update human docs if user-facing behavior changed
```

Especially preserve tests for:

```text
semantic overclaim rejection
bootstrap gap/double-apply guards
provider Completed insufficient for PASS
UNKNOWN target outcome blocking retry
marker absence remaining UNRESOLVED
credential/evidence redaction
strict evidence merge conflicts
separate mutation/fault/Admin authorization
core library independent from CLI presentation layer
legacy evidence import paths failing to resolve
root evidence legacy module files remaining absent
```

## Documentation ownership after reorganization

```text
docs/human/README.md               human reading order
docs/human/CONCEPTS.md             stable conceptual model
docs/human/REPOSITORY_GUIDE.md     human repo/file map
docs/human/GETTING_STARTED.md      install/package/Fabric consumption
docs/human/DATASET_ONBOARDING.md   new-data decision guide
docs/human/OPERATIONS.md           operational/CLI guide

docs/machine/STATE.md              exact current engineering state
docs/machine/CONTEXT.md            invariants/fail-closed boundaries
docs/machine/CAPABILITIES.md       guarantee/evidence matrix
docs/machine/IMPLEMENTATION_MAP.md code ownership map
docs/machine/HISTORY.md            compact merged milestone history
```

Do not reintroduce one historical markdown file per implementation PR unless there is a durable standalone protocol that cannot be represented in the canonical machine docs.
