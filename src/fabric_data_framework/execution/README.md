# Execution

## Purpose

Reference dataset execution paths and backend dispatch contracts.

## Start here

`watermark_scd2.py, append.py, full_replace.py, snapshot_diff.py, backends/`

## Does not own

Business-specific mappings.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
