# Data Plane

## Purpose

Source-faithful Bronze normalization and transient staging primitives.

## Start here

`bronze.py, staging.py`

## Does not own

Durable control state or provider transport.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
