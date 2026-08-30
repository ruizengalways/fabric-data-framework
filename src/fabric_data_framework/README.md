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
| control-plane state/runtime repository | `control_plane*.py`, `repository.py`, `relational_repository.py` |
| target idempotency / unknown commit recovery | `target_operations.py`, `target_operation_io.py`, `recovery/` |
| release/deployment materialization | `delivery.py`, `deployment.py` |
| approved integration evidence | `integration_*.py`, `approved_*_runner.py` |
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
  integration_* / approved_* / delivery / deployment
            |
            v
CLI presentation
  cli/
```

The arrows indicate allowed consumption direction at a high level. In particular, `cli/` is a leaf presentation layer and reusable framework modules must not depend on it.

## Why some modules are still flat

Several mature areas predate the current folder organization, especially:

```text
control_plane*.py
integration_*.py
approved_*_runner.py
repository.py / relational_repository.py
```

Do not move them merely for aesthetics. A folder extraction should happen only when:

1. the ownership boundary is clear;
2. public/import compatibility can be preserved or intentionally versioned;
3. dependency direction improves;
4. the full contract suite proves behavior did not change.

The CLI extraction is intentionally the first such cleanup because it is a true leaf dependency and can be physically removed without breaking core library use.
