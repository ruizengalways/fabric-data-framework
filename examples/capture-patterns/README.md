# Capture pattern examples

Schema-valid example configurations for common source patterns.

Use these as examples only; do not copy source names, connection refs, release identity, physical bindings, or capability assumptions into production without validating the real source.

Files:

- `configs/crm.customer.json` — watermark + lookback-style current-state source.
- `configs/commerce.order_cdc.json` — Debezium/Kafka CDC + SCD2.
- `configs/lakehouse.customer_cdf.json` — Delta CDF + SCD2.
- `configs/partner.customer_api.json` — API incremental/watermark-style example.
- `configs/vendor.account_files.json` — recurring snapshot files + snapshot diff.
- `capture-selections.json` — concise examples of the semantic claim made for each dataset.

For the decision process behind these examples, read `docs/human/DATASET_ONBOARDING.md`.
