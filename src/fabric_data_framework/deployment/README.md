# Deployment package

This folder owns release identity, promotion/deployment contracts and the
credential-free delivery/materialization helpers that operate on those contracts.

```text
contracts.py  immutable release identity, environment bindings, promotion plan, provenance
delivery.py   config bundle/hash, release manifest I/O, semantic metadata materialization, deployment history
```

The package root intentionally has no compatibility re-exports. Use explicit
`deployment.contracts` or `deployment.delivery` imports.
