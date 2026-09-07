# Deprecated document name: use IMPLEMENTATION_PROJECT_BOOTSTRAP.md

This filename is retained only so older links do not break.

The architecture changed: `fabric-customer` is now the independent Fabric-native, framework-agnostic source-system simulator. A real framework consumer should live in its own **implementation/domain repo** such as `fabric-health`.

Use the canonical runbook:

```text
docs/human/IMPLEMENTATION_PROJECT_BOOTSTRAP.md
```

Do not interpret the historical phrase "customer project" as permission to put DatasetConfig, framework adapters, SCD/apply policy or framework certification back into the `fabric-customer` repository.
