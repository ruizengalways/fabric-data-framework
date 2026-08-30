# CLI package

This directory contains the command-line presentation layer only.

```text
cli/
├─ __init__.py   public `main` export
├─ __main__.py   `python -m fabric_data_framework.cli`
├─ main.py       tiny composition/router entrypoint
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
