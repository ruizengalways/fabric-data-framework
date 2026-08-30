# CLI package

This directory contains the command-line presentation layer only.

```text
cli/
├─ __init__.py   public `main` export
├─ __main__.py   `python -m fabric_data_framework.cli`
├─ main.py       tiny composition/router entrypoint
├─ project.py    developer-time customer/domain init + static dry-run adapters
├─ release.py    release-candidate readiness report / hard-gate adapter
├─ base.py       general validation, metadata, deployment and preflight commands
└─ approved.py   approved evidence / real-environment commands
```

Dependency direction is deliberately one-way:

```text
CLI  --->  reusable framework modules

reusable framework modules  -X->  CLI
```

The framework library does not need this directory to execute capture/apply/runtime/recovery APIs. Removing `cli/` should only remove command-line functionality; it must not make the reusable package core unimportable.

Rules:

- business/data semantics never live here;
- provider/recovery logic never lives here;
- command handlers translate arguments to reusable APIs and render results;
- new CLI commands should be grouped by operator intent, not by creating another top-level `cli_*.py` file;
- core modules must never import `fabric_data_framework.cli`.

`project-init` and `project-validate` are intentionally developer/CI-time only.
Reusable scaffold and validation logic lives in `deployment/project.py`; the CLI only
parses arguments and renders deterministic JSON. Neither command creates Fabric items,
mutates a live environment, persists secrets, or upgrades a source-controlled dry run
to a live Fabric evidence claim.

`release-readiness` is also presentation only. Its reusable fail-closed aggregation
lives in `evidence/release_readiness.py`. Generating a blocked report returns success by
default because report generation itself is valid; `--require-ready` turns the same
report into a hard non-zero release gate when every required proof is expected to exist.
