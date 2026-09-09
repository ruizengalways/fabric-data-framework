# Apply

## Purpose

Provider-neutral target-state mutation semantics.

## Start here

`current_state.py, scd1.py, scd2.py, cdc.py`

## Does not own

Capture transport or orchestration.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
