# Extensions

## Purpose

Explicit registered extension points for supported customization.

## Start here

`registry.py`

## Does not own

Ad-hoc imports of framework internals.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
