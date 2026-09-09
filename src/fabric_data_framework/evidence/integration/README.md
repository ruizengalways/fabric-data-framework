# Integration Evidence

## Purpose

Typed integration evidence, preflight, rerun/merge logic, and approved executors.

## Start here

`evidence.py, runner.py, checks.py, approved/`

## Does not own

Release policy or business-path semantics.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
