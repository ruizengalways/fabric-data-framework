# Fabric Certification

## Purpose

Microsoft Fabric-specific binding discovery, asset bootstrap, job and pipeline-child certification.

## Start here

`bindings.py, assets.py, fabric_job.py, pipeline_child.py`

## Does not own

Provider-neutral certification semantics.

## Dependency rule

Keep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`](../../../../docs/DEVELOPMENT_GUIDE.md) for the repository-wide change workflow.
