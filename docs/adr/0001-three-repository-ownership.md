# ADR 0001 — Three-repository ownership model

Status: Accepted
Date: 2026-08-28

## Context

The platform needs clear ownership boundaries between infrastructure lifecycle, reusable data-engineering behaviour and domain-specific Customer logic. Combining these concerns would blur release cadence, permissions, accountability and dependency direction.

## Decision

Use exactly three primary repositories:

- `fabric-infra` — Infrastructure Platform Engineering.
- `fabric-data-framework` — reusable Data Platform Engineering runtime/package.
- `fabric-customer` — Customer Domain Data Engineering reference implementation.

Dependency direction is infrastructure -> Fabric estate/environment contract and framework package -> domain. Framework must not depend on Customer; infrastructure must not import domain business logic.

The runtime sharing model is **share code, not runtime**: domain runtimes are isolated and consume immutable framework versions.

## Consequences

- Infrastructure automation can be added later without refactoring framework behaviour.
- Framework releases can evolve independently from domain releases.
- Domain repositories retain explicit business logic and configuration.
- Cross-repository contracts must be documented and versioned carefully.
