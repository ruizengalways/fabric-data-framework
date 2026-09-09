# Reconciliation

## Purpose

Framework-owned semantic reconciliation policy evaluation and strategy checks.

## Start here

`engine.py, append.py, full_replace.py, scd2.py, snapshot_diff.py`

## Does not own

Provider observations as semantic authority.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
