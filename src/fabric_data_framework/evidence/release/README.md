# Release Evidence

## Purpose

Candidate certification and release-readiness proof composition.

## Start here

`candidate_certification.py, readiness.py, merge.py`

## Does not own

Artifact creation or Fabric execution.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
