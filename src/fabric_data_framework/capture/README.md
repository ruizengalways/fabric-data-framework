# Capture

## Purpose

Source-change semantics and capture planning.

## Start here

`api.py, patterns.py, semantic_contracts.py`

## Does not own

Apply/target mutation semantics.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
