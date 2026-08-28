# Domain Extension Model — fabric-data-framework

Status: Canonical design
Last updated: 2026-08-28

## Purpose

The released framework wheel must cover ordinary enterprise ingestion/application patterns without modification while still supporting genuinely irregular datasets.

Custom logic belongs in the domain solution/package and plugs into stable framework extension contracts. It does not fork or patch `fabric-data-framework`.

## Stable logical extension names

Source-controlled dataset metadata references a logical extension name, not an arbitrary Python import path.

Example:

```yaml
extensions:
  transform: weird_feed_v1
```

The domain Python package registers that implementation through a controlled registry / Python package entry point, conceptually:

```toml
[project.entry-points."fabric_data_framework.transforms"]
weird_feed_v1 = "fabric_customer.extensions.weird_feed:WeirdFeedTransform"
```

This creates a stable boundary:

```text
metadata logical name
  -> framework extension registry
  -> domain release plugin implementation
```

The domain release identity therefore versions both ordinary metadata and any exceptional custom implementation.

## Bounded extension contracts

Initial extension families may include:

- capture adapter — unusual source protocol or custom micro-batch acquisition;
- parser/normalizer — irregular binary/text/semi-structured format;
- batch transform — domain-specific transformation before standard apply;
- DQ rule provider — domain/business validation rules;
- specialized apply adapter — only when no standard APPEND/REPLACE/UPSERT/SCD strategy is sufficient.

Each extension receives a typed immutable execution context and typed landing/batch reference. It returns typed data/evidence rather than controlling the entire run lifecycle.

## Framework-owned boundaries that extensions cannot bypass

Custom code may not directly own or override:

- framework watermark/checkpoint commits;
- dataset leases;
- row-accounting invariants;
- reconciliation status;
- final dataset status;
- release/config provenance;
- production secret resolution;
- undeclared target publication;
- semantic strategy changes at runtime.

Where custom code performs a physical write, it must do so through a declared extension contract that returns publication evidence to the framework and participates in the same recovery/idempotency model.

## Failure behavior

Extensions must fail explicitly with categorized framework exceptions/evidence. They must not silently skip malformed records or mutate target/state before the framework can determine whether the operation is retryable or recoverable.

## Why this is preferred over framework edits

Routine domain onboarding becomes:

```text
standard dataset
  -> metadata only

standard dataset + business rules
  -> metadata + domain DQ/mapping

true exception
  -> metadata + registered domain extension

new reusable industry-wide pattern
  -> framework feature through normal framework release process
```

Only the last case changes `fabric-data-framework` itself.
