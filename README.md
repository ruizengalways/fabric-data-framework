# fabric-data-framework

Reusable, versioned Microsoft Fabric data-engineering runtime for the Enterprise Fabric Data Engineering Platform reference implementation.

This repository owns platform-level data-engineering behaviour: configuration contracts, metadata-driven execution, capture/apply strategies, runtime state, control-plane schemas, reconciliation, recovery semantics, observability hooks, and reusable testing utilities.

Canonical project memory lives in GitHub, not in chat history:

- `docs/ECOSYSTEM_BLUEPRINT.md` — cross-repository architecture and ownership model.
- `docs/PROJECT_BLUEPRINT.md` — this repository's architecture and roadmap.
- `docs/CURRENT_STATUS.md` — exact implementation state and next step.
- `docs/adr/` — accepted architecture decisions.
- `docs/runbooks/` — operational/recovery procedures as they are implemented.

The first implementation phase intentionally establishes architecture and recovery context before runtime code is added.
