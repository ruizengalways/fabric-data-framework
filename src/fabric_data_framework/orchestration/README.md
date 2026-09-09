# Orchestration

## Purpose

Plan and dispatch dataset work without owning provider execution details.

## Start here

`planner.py, dispatcher.py`

## Does not own

Capture/apply semantics or provider APIs.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
