# `fabric_data_framework` code map

Use this file when browsing source code. It describes the current code organization, not implementation history.

For a full end-to-end reading path — `DatasetConfig -> ExecutionPlan -> orchestration -> backend -> remote child -> capture/quality/apply/reconciliation -> durable outcome -> certification/release` — read [`docs/CODE_READING_GUIDE.md`](../../docs/CODE_READING_GUIDE.md).

## Start here by task

| You want to understand/change | Start here |
|---|---|
| dataset metadata and policy | `metadata/config.py`, `metadata/` |
| source/capture semantics | `capture/` |
| APPEND/change-log execution | `capture/watermark.py` -> `execution/append.py` -> `apply/append.py` -> `quality/reconciliation/append.py` |
| Bronze/Silver apply semantics | `apply/`, `execution/` |
| current-from-SCD2 projection semantics | `contracts/current_projection.py`, `apply/current_projection.py`, `execution/current_projection.py`, `deployment/current_projection.py` |
| execution-plan contract | `contracts/execution_plan.py` |
| execution-plan compilation | `execution/plan_compiler.py`, `metadata/capabilities.py` |
| orchestration | `orchestration/planner.py`, `orchestration/dispatcher.py` |
| Fabric / CDC provider adapters | `adapters/` |
| quality/schema ordering rules | `quality/`, `contracts/schema.py` |
| control-plane state/runtime repository | `control_plane/` |
| target idempotency / unknown commit recovery | `contracts/target_operation.py`, `control_plane/target_operation_journal.py`, `recovery/` |
| FULL_REBUILD scope + state cutover | `contracts/rebuild.py`, `recovery/rebuild.py` |
| dependency-aware rebuild impact | `contracts/rebuild_impact.py`, `recovery/rebuild_impact.py` |
| target version / blue-green cutover | `contracts/target_version.py`, `recovery/target_cutover.py` |
| approved integration evidence | `evidence/` |
| release/deployment materialization | `deployment/delivery.py`, `deployment/contracts.py` |
| command line interface | `cli/` |

## Execution-plan ownership

The plan value and the plan compiler are intentionally separate:

```text
contracts/execution_plan.py
  ExecutionKind
  ExecutionRole
  ExecutionUnit
  ExecutionPlan
        |
        ^ immutable output only
        |
execution/plan_compiler.py
  compile_execution_plan(...)
  build_default_execution_plan(...)
        ^
        |
metadata/capabilities.py
  capture/apply capability resolution
```

`contracts/execution_plan.py` does not re-export compiler functions. Code that transports, validates, or persists an `ExecutionPlan` can depend on the immutable contract without importing engine/capability-resolution logic. Code that constructs a plan imports `execution.plan_compiler` explicitly.

## APPEND/change-log trace

For application audit/change-history rows that are incrementally readable but may be re-observed because of bounded lookback:

```text
capture/watermark.py
  source window + overlap semantics
        |
        v
execution/append.py
  capture-neutral batch coordination
        |
        v
apply/append.py
  append_identity dedup + idempotent replay + conflict fail-closed
        |
        v
quality/reconciliation/append.py
  APPEND reconciliation
```

Keep these separate:

```text
entity key != event identity != incremental cursor
```

Raw/Event Bronze may retain repeated source observations. Silver APPEND may collapse exact replay under a stable `append_identity`. The same identity with different business payload must fail closed.

## Rebuild and cutover trace

Data-correctness repair is not ordinary retry/replay recovery. The canonical runtime ownership is:

```text
contracts/rebuild.py
  TARGET_ONLY / CAPTURE_AND_TARGET / AUTHORITATIVE_RESET
        |
        v
recovery/rebuild.py
  exact requested/completed scope + target/reconciliation/state-cutover gates

contracts/rebuild_impact.py
        |
        v
recovery/rebuild_impact.py
  first bad root + downstream contaminated descendants only

contracts/target_version.py
        |
        v
recovery/target_cutover.py
  candidate/UAT/approval/generation/idempotency cutover gates
```

The framework never automatically deletes the old physical target version and does not automate permanent business-data purge. Detailed operator procedure lives in [`docs/REPAIR_AND_REBUILD.md`](../../docs/REPAIR_AND_REBUILD.md).

## Dependency shape

Think about the package in layers:

```text
semantic contracts
  config / capture / apply / quality / contracts
            |
            v
planning + runtime + orchestration
  execution/plan_compiler.py / dispatcher / backends / control plane / recovery
            |
            v
provider adapters
  adapters / Fabric / CDC
            |
            v
operational evidence + delivery
  evidence / delivery / deployment
            |
            v
CLI presentation
  cli/
```

The arrows indicate allowed consumption direction at a high level. In particular:

```text
execution plan compiler -> immutable execution-plan contract + metadata capabilities
CLI -> evidence/core
evidence -> semantic/runtime/provider/recovery core
core -X-> CLI
```

`evidence/` proves existing contracts; it must not become a second semantic truth.

## `evidence/` reading order

```text
integration_evidence.py
  retained evidence vocabulary/spec/result/manifest
        |
        v
integration_checks.py
  safe projection of existing provider/runtime outcomes
        |
        v
integration_evidence_merge.py + integration_runner.py
  strict staged merge + credential-free exact-release preflight
        |
        v
approved_*_runner.py
  explicitly authorized environment-facing evidence execution
```

There are no root-level evidence compatibility modules. Import evidence contracts and approved runners only from `fabric_data_framework.evidence...`.

## Why some modules are still flat

Several mature areas predate the current folder organization, especially:

```text
control_plane*.py
repository.py / relational_repository.py
```

Do not move them merely for aesthetics. A folder extraction should happen only when:

1. the ownership boundary is clear;
2. compatibility is intentionally preserved or intentionally hard-cut as a versioned contract decision;
3. dependency direction improves;
4. the full contract suite proves behavior did not change.

CLI and evidence were extracted as separate slices. A future control-plane extraction should also be isolated rather than mixed into unrelated feature work.

Package-root imports are intentionally unsupported; import the owning submodule explicitly.
