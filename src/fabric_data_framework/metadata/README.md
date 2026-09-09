# Metadata

## Purpose

Typed DatasetConfig and capability validation.

## Start here

`config.py, capabilities.py`

## Does not own

Runtime side effects.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
