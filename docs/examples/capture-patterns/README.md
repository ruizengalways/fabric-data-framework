# Capture Pattern Examples

These examples are intentionally executable documentation. They show how a domain repository can keep ordinary dataset semantics in metadata rather than framework code.

Files:

- `configs/crm.customer.json` — SQL/current-state source using `WATERMARK_LOOKBACK` + SCD1.
- `configs/commerce.order_cdc.json` — Debezium/Kafka full CDC + SCD2.
- `configs/lakehouse.customer_cdf.json` — Delta Change Data Feed + SCD2.
- `configs/partner.customer_api.json` — API cursor/current-state changes + SCD1.
- `configs/vendor.account_files.json` — complete file snapshots + SNAPSHOT_DIFF.
- `capture-selections.json` — source-fidelity/delete/history claims reviewed alongside the configs.

Validate them exactly as a domain CI job would:

```bash
fabric-framework capture-onboarding-validate \
  --config-dir docs/examples/capture-patterns/configs \
  --selections docs/examples/capture-patterns/capture-selections.json \
  --require-all
```

The examples are also loaded by the framework test suite so documentation cannot silently drift away from typed configuration.
