# Approved Fabric Data Pipeline Evidence Runner

Status: implementation/runbook checkpoint  
Last updated: 2026-08-29

## Purpose

This command executes one exact-release Fabric Data Pipeline evidence check without weakening the framework semantic-success contract.

A Fabric job reaching `Completed` is necessary but not sufficient. The reusable child pipeline must persist the exact framework `DatasetDispatchOutcome` for the generated `dataset_run_id` into the relational control plane. Only then may the approved runner emit `FABRIC_PIPELINE_RUN=PASS`.

```text
exact runner config + evidence spec
        ↓
prerequisite merged evidence
  item read PASS
  control-plane certification PASS
  selected Pipeline check NOT_RUN
        ↓
release manifest + exact config bundle hash
        ↓
explicit Pipeline execution authorization
        ↓
runtime Fabric token + control-plane DB URL
        ↓
parent PipelineRunAudit RUNNING
        ↓
FabricPipelineBackend
  -> remote Fabric Data Pipeline
  -> child persists exact DatasetDispatchOutcome
  -> backend verifies exact dataset_run_id + terminal outcome
        ↓
parent PipelineRunAudit SUCCESS / FAILED
        ↓
partial IntegrationEvidenceManifest
```

## Why prerequisite evidence is mandatory

The runner intentionally refuses to execute until the same exact `IntegrationEvidenceSpec` already contains:

```text
FABRIC_ITEM_READ              PASS
CONTROL_PLANE_CERTIFICATION   PASS
FABRIC_PIPELINE_RUN           NOT_RUN
```

This prevents a remote mutation before read-only identity/authorization and the durable control plane have been proven for the exact release.

If the Pipeline check already contains PASS, FAIL or EXTERNAL_REQUIRED, the runner refuses automatic rerun. The operator must explicitly choose the intended evidence/rerun path instead of silently performing another remote mutation.

## Exact release inputs

The command requires both:

```text
release manifest
released dataset config directory
```

It validates:

```text
runner/spec environment/domain/framework/release identity
release manifest domain/framework/release_hash
config bundle hash == release manifest config_bundle_hash
selected dataset exists in that exact bundle
physical workspace/pipeline item binding exists for the selected check
production-eligible control-plane profile is configured
```

The relational repository then verifies the deployed dataset `config_hash` against the same released config before remote execution starts.

## Runtime secrets

Source control contains only environment-variable names:

```text
FABRIC_ACCESS_TOKEN
CONTROL_PLANE_DATABASE_URL
```

The approved Pipeline preflight now requires both. Values are never copied into the retained run plan or evidence manifest.

The DB URL value is retrieved only after exact-release validation, prerequisite evidence validation and explicit Pipeline authorization pass. The Fabric token is acquired by the existing `EnvironmentAccessTokenProvider` when the REST call occurs.

## Command

```bash
fabric-framework integration-pipeline-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/prerequisites-merged.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --check-id fabric.pipeline \
  --dataset-id crm.customer \
  --evidence-reference artifact:pipeline-run \
  --output evidence/pipeline-partial.json \
  --allow-pipeline-execution
```

`--allow-pipeline-execution` is mandatory. Without it the runner performs no remote mutation.

## Durable framework outcome requirement

Before invoking Fabric, the runner creates the parent `PipelineRunAudit` row. This is required by the real relational foreign-key path: the child dataset run references the framework pipeline run.

The existing `FabricPipelineBackend` generates the exact `dataset_run_id` and passes it to the child Pipeline through framework parameters. After Fabric returns `Completed`, the backend reads:

```text
SqlAlchemyControlPlaneRepository.get_dataset_outcome(dataset_run_id)
```

PASS requires:

```text
remote status = Completed
exact durable outcome exists
outcome.dataset_run_id == invocation.dataset_run_id
outcome is terminal
outcome.status == SUCCEEDED for approved evidence PASS
native item/job/root IDs match the exact invocation
```

Therefore provider `Completed` with no child framework outcome becomes retained `FAIL`, not PASS.

Provider failure/cancel/dedupe or a durable framework failure also becomes `FAIL` with safe framework/native correlation where available.

## Evidence accumulation

After a successful stage:

```bash
fabric-framework integration-evidence-merge \
  --spec evidence-spec.json \
  --input evidence/prerequisites-merged.json \
  --input evidence/pipeline-partial.json \
  --output evidence/after-pipeline.json
```

Strict merge conflict rules remain unchanged. Source partial manifests must remain retained.

## Current Microsoft Fabric API context

The framework continues to reuse its existing tested Pipeline transport in this slice. Microsoft currently documents both the Data Factory on-demand Pipeline job route and newer DataPipeline-specific execute-job routes. API migration/equivalence certification is a separate concern from this approved-runner semantic gate and should not be silently mixed into the same change.

## Evidence language

Deterministic CI for this runner proves only:

```text
IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT
```

`FABRIC PIPELINE PROVEN` requires a retained exact-release approved tenant run with native job/root correlation and the exact durable framework dataset outcome.
