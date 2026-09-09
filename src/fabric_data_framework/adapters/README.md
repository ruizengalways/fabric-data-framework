# Adapters

## Purpose

Provider/source-specific implementations behind framework-owned contracts.

## Start here

`fabric/, cdc/`

## Does not own

Framework semantic decisions.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
