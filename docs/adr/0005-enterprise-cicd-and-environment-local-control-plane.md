# ADR 0005 — Enterprise CI/CD and Environment-Local Control Plane

Status: Accepted
Date: 2026-08-28

## Context

The platform must support enterprise CI/CD in Microsoft Fabric while remaining portable across GitHub/Azure DevOps source control and Fabric-native/external deployment mechanisms.

The runtime also uses a metadata/control plane containing both released semantic definitions and environment-specific runtime state. Treating all control-table contents as deployable configuration would corrupt environment isolation: DEV/UAT/PROD have different watermarks, run history, overrides, quarantine and recovery state.

## Decision

1. Use trunk-based development with immutable release candidates promoted DEV -> UAT -> PROD.
2. Support Fabric workspace Git integration with GitHub or Azure DevOps; do not bind runtime architecture to a specific Git provider.
3. Support both Fabric Deployment Pipelines and external deployment automation (GitHub Actions/Azure Pipelines using Fabric APIs, `fabric-cicd`, Fabric CLI or equivalent approved adapters).
4. Define a provider-neutral deployment manifest/provenance contract.
5. Give DEV, UAT and PROD isolated control-plane instances/namespaces.
6. Promote control-plane schema migrations and source-controlled semantic metadata definitions.
7. Resolve workspace/resource/connection/secret/environment values separately per stage.
8. Never promote runtime state such as watermark, dataset state/lease, run audit, quarantine execution state, runtime overrides or reprocess history from one environment to another.
9. Write `deployment_history` independently in each environment when a release reaches that stage.
10. Keep code rollback, control-plane schema migration and data/runtime recovery as separate operational concerns.

## Promotion model

```text
Git SHA + framework version + config bundle hash
                     |
                     v
DEV definitions/config snapshot
DEV runtime state stays DEV
                     |
                     v
UAT same definitions/config snapshot
UAT runtime state stays UAT
                     |
                     v
PROD same definitions/config snapshot
PROD runtime state stays PROD
```

## Consequences

### Positive

- Same release identity can be proven across environments.
- GitHub and Azure DevOps enterprises can use the same architecture.
- Fabric-native deployment pipelines and GitHub/Azure external automation can coexist behind one deployment contract.
- PROD watermark/history cannot be accidentally overwritten by non-production state.
- Runtime state remains truthful for each environment.
- Control-plane schema evolution becomes testable and auditable.

### Trade-offs

- Deployment requires explicit schema migration and semantic-metadata materialization steps; copying a workspace item alone may not complete control-plane deployment.
- Environment-specific bindings must be managed deliberately.
- CI/CD implementation is more structured than manually synchronizing Fabric workspaces.

## Rejected alternatives

### Environment branches as the default

Rejected because the project standard is same-artifact trunk-based promotion. Branch-per-stage can be supported only as an enterprise-specific adapter, not as a framework assumption.

### Copy the entire DEV control plane into UAT/PROD

Rejected because watermarks, run history, leases, overrides, quarantine/reprocess state and other runtime data are environment-specific.

### GitHub-specific deployment logic inside framework runtime

Rejected because source-control/deployment provider is a delivery concern, not a data-runtime semantic dependency.

## References

Detailed design: `docs/CICD_DESIGN.md`.
