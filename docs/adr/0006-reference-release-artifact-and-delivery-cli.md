# ADR 0006 — Reference release artifact and provider-neutral delivery CLI

Status: Accepted
Date: 2026-08-28

## Context

The framework needs a real enterprise delivery spine before tenant-specific Fabric deployment credentials are available. The implementation must prove immutable build/release identity, exact framework consumption, control-plane migration/materialization and environment-local promotion semantics without coupling runtime code to GitHub Actions or one Fabric API.

## Decision

1. Framework semantic versions produce immutable wheel artifacts.
2. The reference GitHub implementation publishes the wheel and SHA-256 checksum as a tag-bound GitHub Release asset.
3. GitHub Release is a reference artifact channel only; the provider-neutral release identity can be backed by Azure Artifacts, an internal package repository or another approved artifact store.
4. A small `fabric-framework` CLI is the automation boundary for control-plane migration, semantic metadata materialization, release-manifest generation, deployment planning and deployment-history recording.
5. Environment bindings and credentials are never part of the immutable release identity.
6. Runtime state is never included in semantic metadata materialization or cross-environment promotion.
7. Fabric-specific external writes remain adapter responsibilities and require current capability/authentication verification at implementation time.

## Consequences

- GitHub Actions and Azure Pipelines can call the same contracts.
- Fabric-native deployment-pipeline automation can use the same pre/post-deployment control-plane steps.
- A domain can prove which exact Git SHA/config hash/framework wheel reached an environment.
- The reference implementation can demonstrate release mechanics without prematurely selecting the company's long-term artifact repository.
- A real Fabric deployment is not claimed until an authorized identity and target estate are exercised.
