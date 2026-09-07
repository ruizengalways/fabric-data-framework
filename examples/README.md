# Examples

This directory contains schema-valid example inputs for framework commands and contracts.

## Capture semantics examples

`capture-patterns/` contains representative DatasetConfig-style examples for:

- watermark/current-state sources;
- Debezium/Kafka CDC;
- Delta CDF;
- incremental APIs;
- recurring snapshot files + snapshot diff.

The semantic decision guide is `docs/DATA_PATTERNS.md`.

## Approved evidence examples

Files prefixed with `dev_` are credential-free example recipes/specs/configs for approved evidence commands, including Copy Job, Spark, Warehouse, fault drill, and integration runner/evidence configuration.

They may contain placeholder hashes, UUIDs, logical extension names, or env-var names. Replace placeholders with the exact current candidate/integration-input/environment values before a real run.

Examples are not proof that a provider or environment has been certified.
