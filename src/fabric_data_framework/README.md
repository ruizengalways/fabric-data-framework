# `fabric_data_framework` code map

Use this file when browsing source code. It describes the current code organization, not implementation history.

## Start here by task

| You want to understand/change | Start here |
|---|---|
| dataset metadata and policy | `config.py`, `metadata/` |
| source/capture semantics | `capture/` |
| Bronze/Silver apply semantics | `apply/`, `execution/` |
| execution plan / orchestration | `contracts/execution_plan.py`, `orchestration/`, `dispatcher.py` |
| Fabric / CDC provider adapters | `adapters/` |
| quality/schema ordering rules | `quality/`, `schema_contract.py` |
| control-plane state/runtime repository | `control_plane/` |
| target idempotency / unknown commit recovery | `target_operations.py`, `control_plane/target_operation_journal.py`, `recovery/` |
| approved integration evidence | `evidence/` |
| release/deployment materialization | `delivery.py`, `deployment.py` |
| command line interface | `cli/` |

## Dependency shape

Think about the package in layers:

```text
semantic contracts
  config / capture / apply / quality / contracts
            |
            v
runtime + orchestration
  execution / dispatcher / control plane / recovery
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
2. public/import compatibility can be preserved or intentionally versioned;
3. dependency direction improves;
4. the full contract suite proves behavior did not change.

CLI and evidence were extracted as separate slices. A future control-plane extraction should also be isolated rather than mixed into unrelated feature work.
