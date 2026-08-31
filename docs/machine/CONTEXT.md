# MACHINE CONTEXT — Non-negotiable invariants

This file contains stable engineering rules that must survive conversation/context resets.

## Semantic model

```text
data semantics -> capture/delivery -> cursor -> Bronze meaning -> Silver meaning -> fidelity/recovery
```

Core invariants:

```text
capture fidelity upper-bounds truthful history fidelity
SCD2 never upgrades source/capture fidelity
capture strategy != apply strategy
execution engine != data semantics
provider/native cursor != framework downstream semantic checkpoint
provider Completed != framework semantic success
```

## Capture / bootstrap / delete truth

Generic `updated_at` is not automatically a safe no-gap cursor.

Full-baseline -> WATERMARK requires a complete authoritative baseline, exact/frozen handoff boundary, continued visibility of post-boundary changes, and deterministic ordering/dedup semantics. Snapshot -> CDC similarly requires a fenced no-gap/no-double-apply handoff.

Lookback improves late-observation/boundary safety; it does not create hard-delete visibility.

Valid hard-delete truth requires an actual signal such as a retained soft-delete/tombstone, CDC delete event, snapshot disappearance/diff, or source-defined audit/delete feed. Never infer delete visibility from target behavior.

## Provider/native progress

Provider-native progress is transport/provider state unless explicitly defined otherwise. Framework downstream checkpoints advance only after framework semantic success.

A provider terminal success therefore cannot substitute for semantic reconciliation or durable framework outcome.

## Target-operation recovery

Logical target operation identity is attempt-independent.

Allowed durable behavior:

```text
new               -> EXECUTE
SUCCEEDED         -> SKIP_SUCCEEDED
IN_PROGRESS retry -> RECONCILE_REQUIRED
UNKNOWN retry     -> RECONCILE_REQUIRED
NOT_COMMITTED     -> CAS reopen -> EXECUTE
```

Unknown commit outcome never permits blind re-execution.

## Warehouse commit truth

Preferred target transaction:

```text
BEGIN TRAN
  bounded target mutation
  framework target-side operation marker
COMMIT TRAN
```

Probe semantics:

```text
matching marker -> COMMITTED
marker absent   -> UNRESOLVED
marker absent + independent no-late-commit proof -> NOT_COMMITTED
```

Marker table is commit evidence, not a distributed lock. Control-plane target-operation CAS remains retry/execution authority.

Normal approved Warehouse execution may simulate framework ACK loss after successful transaction return. That proves deterministic recovery logic only; it does not prove a real driver/network COMMIT disconnect.

Real ambiguous-COMMIT evidence requires an actual execution exception, verified provider-specific fault identity, matching marker COMMITTED, journal SUCCEEDED and later SKIP_SUCCEEDED.

## Session-termination absence proof

A Fabric-specific absence path can establish `NOT_COMMITTED` only when all facts hold:

```text
exact target connection_id + session_id captured before mutation
same exact session observable after ambiguity
open_transaction_count > 0
independent Admin-capable authority terminates exact session
exact connection/session no longer observable
marker re-read after termination
marker remains absent
```

Anything ambiguous remains `UNRESOLVED`. Session termination authorization is separate from ordinary Warehouse execution and fault-injection authorization.

If safe absence is proven:

```text
UNKNOWN -> NOT_COMMITTED
retry_eligible = true
```

Do not automatically re-execute in the same runner. This recovery result does not PASS the committed ambiguous-COMMIT evidence check.

## Evidence system

Statuses:

```text
PASS
FAIL
NOT_RUN
EXTERNAL_REQUIRED
```

Required checks certify only on PASS.

Strict integration merge semantics:

```text
NOT_RUN = absence
one substantive result + NOT_RUNs -> retain substantive result
identical substantive duplicates -> allowed
different substantive reruns -> conflict
no latest/PASS/FAIL precedence
failed/conflicting merge must not clobber output
```

Exact spec/environment/domain/framework/release/check list must match.

## Exact framework vs customer/domain release identity

Framework binary identity and customer/domain release identity are independent and must never be conflated:

```text
candidate_git_sha
  = exact framework source commit

framework wheel SHA256
  = IntegrationEvidence.release_hash
  = ApprovedIntegrationRunnerConfig.framework_artifact_sha256

customer/domain ReleaseManifest.bundle.release_hash
  = IntegrationEvidence.domain_release_hash
  = ApprovedIntegrationRunnerConfig.release_hash
```

A candidate integration manifest from one customer/domain release must not be merged, certified or reused for another domain release even when the framework candidate wheel is identical.

Before immutable 0.4 promotion, complete non-integration release proof must also be machine-bound to the same `domain_release_hash`; references alone are not sufficient.

## Customer owns representative physical business bindings

Framework owns execution/evidence HOW; the customer/domain repository owns business WHAT.

Therefore the exact candidate `fabric.pipeline` physical binding carries the customer-selected representative `dataset_id`. The framework candidate integration workflow may validate that binding, but it must not choose a business dataset via an ad hoc workflow input.

The same ownership principle applies to customer DatasetConfig, exact business-path plan/scenarios, run recipes and bounded extension artifacts.

## Candidate integration producer

`.github/workflows/candidate-integration-evidence.yml` is orchestration around existing approved runners. It may authenticate inputs, execute approved commands, strict-merge partial manifests, and validate an already-produced PASS.

It must never synthesize provider truth or construct `IntegrationEvidenceCheckResult(PASS)` directly.

Required staged order:

```text
read-only item identity
-> production control-plane certification
-> base prerequisite merge
-> Pipeline / Copy / Spark
-> normal Warehouse target+marker
-> fault prerequisite merge
-> real ambiguous-COMMIT drill
-> strict certified merge
-> certified validation
-> upload
```

General live mutation permission and Admin-level Warehouse session-termination permission remain separate.

A merged/green producer workflow is not live Fabric evidence.

## Release-readiness identity and scope

Release readiness is a separate aggregation layer over retained proof. It never executes Fabric and never invents missing evidence.

Exact identity chain:

```text
framework version
+ exact 40-character candidate source SHA
+ successful main candidate workflow run ID/attempt
+ exact inner candidate wheel SHA256
+ exact customer/domain release hash
+ retained ReleaseReadinessProofBundle
+ retained IntegrationEvidenceManifest
```

Non-negotiable rules:

```text
missing proof -> NOT_RUN
required NOT_RUN or FAIL -> release blocker
required OUT_OF_SCOPE -> FAIL/blocker
optional OUT_OF_SCOPE -> allowed only when release scope explicitly excludes that capability
release_ready=true iff every required gate is PASS
integration-backed readiness gate cannot be satisfied by generic/manual proof
proof from one candidate source/wheel cannot certify another candidate
integration evidence from one framework wheel or domain release cannot certify another
GitHub artifact archive digest is not the inner wheel SHA256
provider Completed does not satisfy semantic/business-path readiness gates
```

Debezium/Kafka remains optional in the 0.4 matrix unless explicitly promoted into GA scope before final evidence review.

A green ordinary CI job that generates an intentionally blocked readiness report proves only the fail-closed aggregator contract.

## Exact candidate artifact promotion

Release publication is promotion of already-certified bytes, not a second build.

Required invariant:

```text
main CI builds exact wheel
-> CANDIDATE.json binds source SHA + workflow run/attempt + inner wheel SHA256
-> certification consumes that exact wheel
-> integration evidence binds exact wheel SHA256 + exact domain release hash
-> release-readiness required blockers == 0
-> release workflow downloads/verifies same wheel
-> immutable tag is created at exact candidate source SHA
-> same certified wheel bytes are published
```

Fail closed on candidate provenance mismatch, byte/hash mismatch, missing/expired artifact, missing/mismatched certified readiness, non-zero blockers, any required gate not PASS, or existing immutable tag/release.

The release workflow must never rebuild the wheel.

A main CI candidate artifact is only a releasable input. It is not automatically selected/frozen or live-certified.

## Credential/evidence safety

Source-controlled approved-run config may store env-var **names**, never secret values. Retained reports/manifests must reject credential-like material. Provider exceptions retained as evidence should keep stable type/code, not arbitrary secret-bearing raw text.

## Production runtime

Runtime never silently migrates/provisions production control-plane schema or Warehouse marker schema.

Released immutable artifact remains complete DatasetConfig semantic truth. SQL control plane stores deployed metadata/config identity plus runtime/evidence state; it does not replace source-controlled config.

## CLI/package dependency boundary

The CLI is a leaf presentation layer under `src/fabric_data_framework/cli/`:

```text
CLI -> reusable framework core
reusable framework core -X-> CLI
```

Core semantics/runtime/provider/recovery/evidence/deployment modules must never import the CLI. Removed root compatibility shims must remain absent.

## Evidence vocabulary discipline

Use CI/reference labels for deterministic implementation proof. Only use `FABRIC PROVEN`, `FABRIC WAREHOUSE PROVEN`, `PRODUCTION DB PROVEN`, or equivalent live labels after retained approved real-service execution for the exact framework candidate and exact customer/domain release.
