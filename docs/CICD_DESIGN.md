# Enterprise CI/CD and Environment Promotion Design

Status: Canonical detailed design
Last updated: 2026-08-28

## 1. Purpose

This document defines the enterprise CI/CD model for the three-repository Microsoft Fabric data engineering platform. The design must support both Fabric-native ALM and external CI/CD automation without changing application/runtime architecture.

The core release invariant is:

```text
one immutable release candidate
        -> DEV
        -> UAT
        -> PROD
```

The same domain Git SHA/config bundle/framework version is promoted through environments. A downstream environment must never independently deploy whatever happens to be latest on `main`.

## 2. Fabric source-control terminology

Microsoft Fabric does not host its own Git repository service. Fabric provides workspace Git integration with supported Git providers and a Fabric-native deployment-pipeline capability.

The platform must therefore support:

1. workspace Git integration backed by GitHub;
2. workspace Git integration backed by Azure DevOps;
3. Fabric Deployment Pipelines for Fabric-native DEV -> UAT -> PROD promotion;
4. external automation using GitHub Actions or Azure Pipelines with Fabric APIs, `fabric-cicd`, Fabric CLI or another approved provider-neutral deployment adapter.

Repository provider and deployment mechanism are separate choices.

## 3. Supported enterprise release modes

### Mode A — Fabric-native promotion

Recommended when the enterprise wants Fabric Deployment Pipelines to be the release-control plane.

```text
GitHub / Azure DevOps
        |
        | PR + CI
        v
main / immutable Git SHA
        |
        | sync/deploy release to DEV
        v
DEV Workspace
        |
        | Fabric Deployment Pipeline
        v
UAT Workspace
        |
        | approval + Fabric Deployment Pipeline
        v
PROD Workspace
```

Git can be connected only to the DEV/integration workspace. UAT and PROD do not need independent Git branches or direct Git synchronization.

This preserves trunk-based development and avoids `dev`, `uat`, `prod` branches.

### Mode B — External CI/CD promotion

Recommended when the enterprise wants GitHub Actions/Azure Pipelines to be the release-control plane.

```text
Git provider
    |
    | PR + CI
    v
immutable release bundle
    |
    +--> deploy same bundle -> DEV
    +--> promote same bundle -> UAT
    +--> promote same bundle -> PROD
```

The deployment adapter may use Fabric Items APIs, `fabric-cicd`, Fabric CLI, DacFx/SQL tooling where appropriate, or other supported Fabric APIs.

### Mode C — Hybrid

A common enterprise model is:

- GitHub Actions or Azure Pipelines performs CI, package build, metadata validation, approvals and provenance;
- DEV is synchronized/deployed from Git;
- Fabric Deployment Pipelines perform workspace-to-workspace promotion;
- external automation calls Fabric deployment APIs and runs pre/post-deployment checks.

The framework must not care which of these modes is selected.

## 4. Deployment abstraction contract

CI/CD implementation must expose a logical deployment contract rather than embedding GitHub-specific behaviour in runtime code.

A release/deployment bundle is identified by at least:

```text
domain_release_version
domain_git_sha
framework_version
config_bundle_hash
config_schema_version
control_plane_schema_version
fabric_item_manifest_version
build_id / release_id
```

A deployment adapter receives:

```text
target_environment
release_bundle_identity
logical infrastructure bindings
approved environment configuration
```

and performs the stage-specific deployment.

The same release-bundle identity is used for DEV, UAT and PROD. Environment-specific resource IDs/secrets are resolved at deployment/runtime and are not baked into the immutable source artifact.

## 5. Environment-local control plane

Each environment owns an isolated control-plane instance or isolated control-plane namespace.

Reference topology:

```text
DEV
  Workspace(s)
  Control Plane DEV

UAT
  Workspace(s)
  Control Plane UAT

PROD
  Workspace(s)
  Control Plane PROD
```

The physical implementation may be a Warehouse, Lakehouse/Delta-backed control store, SQL endpoint or another approved Fabric-supported store. The architecture requirement is isolation, not a specific product choice.

### Why environment-local state is mandatory

Runtime state represents what has actually happened in that environment. DEV and PROD do not have the same source progress, data volume, failures, operators, schedules or recovery history.

Therefore:

```text
DEV watermark != UAT watermark != PROD watermark
```

and CI/CD must never promote runtime state as if it were release configuration.

## 6. What is promoted vs what stays local

### 6.1 Promoted as versioned release definition

The same logical definitions move DEV -> UAT -> PROD:

- Fabric item definitions such as Pipelines/Notebooks/Environment definitions where supported;
- framework/domain code and exact framework dependency version;
- control-plane schema/migration scripts;
- dataset semantic metadata definitions;
- dataset contracts and schema policies;
- capture/apply policies;
- business/merge keys;
- watermark/event-time column definitions;
- orchestration dependency/criticality definitions;
- DQ policy definitions;
- quarantine policy definitions;
- reconciliation policy definitions;
- deployment manifest/provenance metadata;
- reusable workflow/deployment logic, version pinned.

These are release artifacts.

### 6.2 Resolved per environment

The release is the same, but these values are environment-bound:

- workspace/Lakehouse/Warehouse IDs;
- connection IDs/endpoints;
- identities and credentials;
- secret references;
- capacity/resource bindings;
- Variable Library/environment variable values;
- environment-specific operational defaults such as bounded concurrency where explicitly allowed.

Environment-specific values must come from an environment/infrastructure contract, Fabric stage configuration/Variable Library, deployment rules, secret store or equivalent approved mechanism.

They are not implemented as different source-code branches.

### 6.3 Never promoted as runtime state

The following are environment-local and must not be copied from DEV to UAT/PROD:

```text
watermark
dataset_state
dataset_lease
pipeline_run
dataset_run
step_run
reconciliation_result
quarantine data / quarantine_batch execution state
schema_change observations
runtime_override values
reprocess_request execution history
operator actions / acknowledgements
```

`deployment_history` is also environment-local: each stage writes its own deployment record when that release reaches the stage.

A runtime override created in DEV is not automatically a PROD override. If an equivalent PROD override is required, it must be explicitly created in PROD with its own audit/reason/expiry.

## 7. Control-plane deployment sequence

For each environment, promotion follows an idempotent sequence conceptually:

```text
1. validate release bundle
2. resolve target environment bindings
3. acquire deployment lock / verify no conflicting deployment
4. apply compatible control-plane schema migrations
5. deploy/update Fabric item definitions
6. materialize the released semantic metadata snapshot
7. validate config hash + framework compatibility
8. run environment smoke/contract checks
9. write deployment_history for the target environment
10. mark release candidate eligible for next-stage promotion
```

Runtime state is preserved throughout deployment unless an explicitly approved migration transforms it.

Control-plane schema migration and semantic metadata materialization must be repeatable/idempotent.

## 8. Semantic metadata materialization

Source-controlled domain metadata is canonical in Git. Deployment materializes a stage-local runtime-readable snapshot.

Example:

```text
Git definition
  dataset = crm.customer
  merge_key = customer_id
  capture = WATERMARK
  apply = SCD2
        |
        | release bundle abc123 / config hash xyz
        v
DEV control plane deployed snapshot
        |
        | promote same release
        v
UAT control plane deployed snapshot
        |
        | promote same release
        v
PROD control plane deployed snapshot
```

The semantic values are equivalent for that release, but environment bindings and runtime states remain local.

The deployment process must record the config hash and Git SHA so a dataset run can prove exactly which released metadata it used.

## 9. Database/control-plane schema migrations

Schema migrations are code and are promoted with the release.

Rules:

- migrations have explicit versions;
- the target stage reports its current schema version before deployment;
- migrations are applied in order;
- migrations are idempotent or safely detectable as already applied;
- destructive changes are not silently executed;
- backward-compatible expand/contract patterns are preferred for live PROD state;
- migration result is audited in deployment history;
- data recovery and schema deployment rollback are separate concerns.

Do not copy DEV control-table rows to PROD to achieve schema parity. Apply the schema migration to the PROD control plane instead.

## 10. Fabric Deployment Pipeline semantics

Fabric Deployment Pipelines promote item metadata/configuration between workspaces; data itself is not treated as a release artifact.

This matches the control-plane architecture:

- deploy definitions/schema metadata where supported;
- preserve target-environment runtime/control data;
- run explicit control-plane migrations/materialization as pre/post deployment steps when Fabric item deployment alone is insufficient;
- apply environment-specific rebinding/rules/variables in the target stage.

The platform must not assume Fabric Deployment Pipelines automatically perform every control-plane migration or seed every metadata table. Those are explicit deployment responsibilities.

## 11. CI pipeline

Every substantive PR should run a provider-neutral validation contract such as:

```text
format/lint
unit tests
metadata schema validation
forbidden runtime-override tests
config semantic validation
control-plane migration validation
package build
framework/domain compatibility checks
Fabric item static validation where supported
security/secret scanning
```

Framework CI additionally validates reusable package behaviour and publishes immutable semantic versions after release criteria are met.

Customer/domain CI pins and tests an exact framework version.

### 11.1 Framework immutable release initiation

The GitHub reference implementation supports two equivalent release-entry paths without changing artifact semantics:

1. preferred operator path: GitHub `Actions` -> `framework-release` -> `Run workflow`, selecting `main` and entering the package version such as `0.3.0`;
2. compatibility path: push an already-created immutable tag such as `v0.3.0`.

For the UI-driven path, the workflow must:

```text
select main + enter version
    -> resolve immutable tag v<version>
    -> refuse an existing GitHub Release
    -> if the tag already exists without a Release, checkout that immutable tag for recovery
    -> otherwise keep the selected main SHA as the release candidate
    -> validate package version == tag version
    -> run static checks + tests + dependency checks
    -> build wheel once
    -> generate and verify portable SHA256SUMS
    -> create the annotated tag only after validation if it did not already exist
    -> create the GitHub Release from that exact tag
```

The workflow never moves an existing tag and never overwrites an existing Release. A rerun after a failure that occurred after tag creation but before Release creation is recoverable by validating the existing tag and completing the missing Release. This separates operator convenience from immutability: the UI may initiate the release, but the immutable tag and released wheel/checksum remain the actual version boundary.

## 12. CD gates

A production-grade release path should support:

```text
merge to main
   -> build immutable release bundle once
   -> deploy DEV
   -> smoke/integration/reconciliation tests
   -> promote exact same bundle to UAT
   -> UAT validation
   -> approval/change-control gate if required
   -> promote exact same bundle to PROD
   -> PROD smoke verification
```

Do not rebuild a different artifact for each environment.

Promotion eligibility and approvals belong to CI/CD, not to the data runtime package.

## 13. Deployment provenance

For each environment, `deployment_history` should eventually record at least:

```text
deployment_id
environment
domain
domain_release_version
domain_git_sha
framework_version
config_bundle_hash
control_plane_schema_version
fabric_item_manifest_version
deployment_mechanism
ci_provider
build_id / workflow_run_id
initiated_by
approved_by (when applicable)
started_at
completed_at
status
previous_deployment_id
```

`deployment_mechanism` can distinguish values such as:

```text
FABRIC_DEPLOYMENT_PIPELINE
FABRIC_GIT_API
FABRIC_ITEMS_API
FABRIC_CICD
FABRIC_CLI
```

Runtime does not branch its behaviour based on CI provider; this is provenance only.

## 14. Rollback and recovery

Three concerns remain separate:

### Code/item rollback
Deploy a previously known-good immutable release bundle.

### Control-plane schema rollback
Prefer forward-fix/expand-contract. Explicit rollback scripts are used only where proven safe for live runtime state.

### Data/runtime recovery
Use framework recovery modes (`RETRY`, `BACKFILL`, `REPLAY`, `FULL_REBUILD`) against the environment-local state. Do not restore DEV watermark/state into PROD as a deployment rollback technique.

## 15. Branching policy

The platform default remains trunk-based:

```text
feature branch -> PR -> main -> immutable release -> DEV -> UAT -> PROD
```

Do not create environment branches merely because Fabric Git integration can support branch-per-stage workflows.

If an enterprise mandates another branch model, the deployment adapter may support it, but framework/runtime correctness must not depend on branch names.

## 16. Security and enterprise controls

The CI/CD design must support:

- service-principal/workload identity where Fabric capability and tenant policy allow;
- least-privilege workspace permissions;
- protected environments/approval gates;
- secrets outside Git;
- auditable deployment history;
- separation between deployment permissions and routine data-runtime permissions;
- production deployment restrictions;
- network/private-access constraints defined by the enterprise estate.

Exact authentication support and preview/GA status must be rechecked against current Microsoft documentation when automation is implemented.

## 17. Implementation sequencing

### Phase 1 foundation
Define provider-neutral release/provenance/config contracts and control-plane migration primitives. Do not build the full Fabric release automation yet.

### Phase 2
Exercise deployed metadata/config provenance in the first Customer vertical slice.

### Phase 3 delivery spine
Implement enterprise CI/CD end to end, including:

- PR CI;
- framework package release/versioning;
- Customer exact dependency pin;
- immutable deployment manifest;
- selected Fabric-native and/or external deployment adapter;
- DEV/UAT/PROD same-artifact promotion;
- control-plane schema migration/materialization;
- environment-specific binding;
- deployment history;
- smoke gates and approvals.

At least one Fabric-native promotion path and one GitHub-driven automation path should be demonstrable by the final reference implementation, while sharing the same deployment contract.
