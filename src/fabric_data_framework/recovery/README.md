# Recovery

## Purpose

Replay, rebuild, target probing, cutover, and unknown-outcome recovery.

## Start here

`runtime.py, replay.py, rebuild.py, target_probe.py`

## Does not own

Ordinary happy-path execution.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
