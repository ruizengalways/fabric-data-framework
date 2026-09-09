# Quality

## Purpose

Row quality, quarantine payload persistence, schema/temporal checks, and reconciliation.

## Start here

`rules.py, quarantine_store.py, reconciliation/`

## Does not own

Business-specific cleansing logic.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
