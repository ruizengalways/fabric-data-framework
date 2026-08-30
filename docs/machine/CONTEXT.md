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

## Cheatsheet acceptance model

Exact semantic presets exist for fourteen common patterns:

```text
1  Full Snapshot -> Current Bronze
2  Full Snapshot -> Snapshot Bronze
3  Watermark -> Current
4  Watermark + Lookback -> Current
5  Watermark + Lookback -> Raw Append
6  Watermark + Soft Delete -> Current
7  Watermark + Lookback + Soft Delete -> Raw Append
8  Net Changes -> Current
9  Net Changes -> Append
10 Full/All Changes -> Event
11 Full Changes -> Current Bronze, intentionally lossy
12 Business Events -> Event
13 Snapshot Diff -> Current
14 Snapshot Diff -> Append Changes
```

“All 14 supported” means semantic representation/onboarding acceptance, not live provider proof for every physical implementation.

## Watermark / bootstrap

Generic `updated_at` is not automatically a safe no-gap cursor.

Full-baseline -> WATERMARK requires:

```text
complete authoritative baseline
exact/frozen handoff boundary
post-boundary changes remain visible
deterministic ordering/dedup semantics
```

Snapshot -> CDC similarly requires a fenced no-gap/no-double-apply handoff.

Lookback improves late-observation/boundary safety; it does not create hard-delete visibility.

## Delete truth

Hard delete is invisible to current-state watermark extraction unless another signal exists.

Possible valid delete signals:

```text
soft-delete/tombstone retained long enough
CDC delete event
snapshot disappearance/diff
source-defined audit/delete feed
```

Never infer delete visibility from target behavior.

## Provider/native progress

Provider-native progress is transport/provider state unless explicitly defined otherwise.

Examples:

```text
Copy Job native cursor tracks provider capture progress
framework checkpoint advances only after framework semantic success
```

A failed provider run must not be described as semantic checkpoint advancement.

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

Framework preferred transaction:

```text
BEGIN TRAN
  bounded target mutation
  framework target-side operation marker
COMMIT TRAN
```

Primary probe semantics:

```text
matching marker -> COMMITTED
marker absent   -> UNRESOLVED
marker absent + independent no-late-commit proof -> NOT_COMMITTED
```

Marker table is commit evidence, not a distributed lock. Control-plane target-operation CAS remains retry/execution authority.

## Simulated ACK loss vs real fault

Normal approved Warehouse runner may deliberately simulate **framework ACK loss after transaction return** to prove recovery behavior.

That is not evidence that a real driver/network COMMIT disconnect occurred.

Real ambiguous-COMMIT evidence is a separate check kind and requires:

```text
actual execution exception
verified provider-specific fault identity
matching marker -> COMMITTED
journal -> SUCCEEDED
later claim -> SKIP_SUCCEEDED
```

Normal return can never PASS that check.

## Session-termination absence proof

A narrow Fabric-specific path can establish `NOT_COMMITTED` only when all facts hold:

```text
exact target connection_id + session_id captured before mutation
same exact session is still observable after ambiguity
open_transaction_count > 0
independent Admin-capable authority KILLs exact session
exact connection/session is no longer observable
marker is re-read after termination
marker remains absent
```

Fail closed:

```text
session already gone before inspection -> UNRESOLVED
open_transaction_count == 0            -> UNRESOLVED
identity mismatch                      -> UNRESOLVED
DMV/KILL/post-check exception           -> UNRESOLVED; exception type only
session remains visible                 -> UNRESOLVED
post-KILL marker read failure           -> UNRESOLVED
marker appears during race              -> NOT_COMMITTED forbidden
```

Query Insights is secondary correlation only; eventual completed-query visibility cannot prove immediate no-late-commit absence.

## Approved session-termination wiring

Admin authority is separate from ordinary Warehouse execution.

Required separation:

```text
ordinary Warehouse DB URL env-var name != Admin Warehouse DB URL env-var name
fault-injection authorization != session-termination authorization
```

Admin URL value may be read only on:

```text
actual execution exception
+ session binding captured
+ fault disarmed
+ fault verified
+ fault identity matched
+ first marker probe UNRESOLVED
+ journal UNKNOWN
```

If marker is already COMMITTED, do not read Admin credential and do not construct Admin authority.

If session termination proves safe absence:

```text
UNKNOWN -> NOT_COMMITTED
retry_eligible = true
```

Do not automatically re-claim/re-execute in the same runner.

This operational recovery does not PASS the committed ambiguous-COMMIT evidence check.

## Evidence system

Statuses:

```text
PASS
FAIL
NOT_RUN
EXTERNAL_REQUIRED
```

Required checks certify only on PASS.

Strict merge semantics:

```text
NOT_RUN = absence
one substantive result + NOT_RUNs -> retain substantive result
identical substantive duplicates -> allowed
different substantive reruns -> conflict
no latest/PASS/FAIL precedence
failed/conflicting merge must not clobber output
```

Exact spec/environment/domain/framework/release/check list must match.

## Release-readiness identity and scope

Release readiness is a separate aggregation layer over retained proof. It never executes Fabric and never invents missing evidence.

Exact identity chain:

```text
framework version
+ exact 40-character candidate source SHA
+ successful main candidate workflow run ID/attempt
+ exact inner candidate wheel SHA256
+ retained ReleaseReadinessProofBundle
+ retained IntegrationEvidenceManifest whose release_hash == exact wheel SHA256
```

Non-negotiable rules:

```text
missing proof -> NOT_RUN
required NOT_RUN or FAIL -> release blocker
required OUT_OF_SCOPE -> FAIL/blocker
optional OUT_OF_SCOPE -> allowed only when release scope explicitly excludes that capability
release_ready=true iff every required gate is PASS
integration-backed readiness gate cannot be satisfied by a generic/manual proof entry
proof from one candidate source SHA cannot certify another candidate
integration evidence from one wheel SHA cannot certify a rebuilt/different wheel
GitHub artifact archive digest is not the inner wheel SHA256
same source version or same git SHA does not authorize evidence reuse across different artifact bytes
provider Completed does not satisfy semantic/business-path readiness gates
```

The source-controlled 0.4 matrix currently keeps Debezium/Kafka optional. If the public 0.4 GA promise is changed to include live Debezium/Kafka certification, that gate must become required **before** final evidence review and release.

A green CI job that generates an intentionally blocked readiness report proves only the fail-closed aggregator contract. It does not make the candidate release-ready.

## Exact candidate artifact promotion

Release publication is promotion of already-certified bytes, not a second build.

Required invariant:

```text
main CI builds exact wheel
-> CANDIDATE.json binds source SHA + workflow run/attempt + inner wheel SHA256
-> certification consumes that exact wheel
-> IntegrationEvidenceManifest.release_hash == that exact inner wheel SHA256
-> release-readiness required blockers == 0
-> release workflow downloads and verifies that same wheel
-> immutable tag is created at the exact candidate source SHA
-> the same certified wheel bytes are published
```

Fail closed:

```text
release workflow must not rebuild the wheel
release workflow must not publish from tag-push alone
candidate must come from successful main push CI
candidate run head SHA must equal selected candidate SHA
candidate manifest run/SHA/version/hash mismatch -> refuse release
wheel byte/hash mismatch -> refuse release
missing/expired candidate artifact -> refuse release; never rebuild
missing/mismatched certified readiness artifact -> refuse release
release_ready != true or blockers != [] -> refuse release
any required readiness result != PASS -> refuse release
existing tag/release -> refuse overwrite/reuse
```

Candidate artifact verification is intentionally standard-library-only so downloaded bytes can be authenticated before installing/trusting the candidate wheel itself.

A main CI candidate artifact is only a releasable **input**. It is not a frozen candidate and is not evidence of live Fabric certification until it is explicitly selected and bound to retained certification evidence.

## Credential/evidence safety

Source-controlled approved-run config may store env-var **names**, never secret values.

Retained reports/manifests must reject credential-like material.

Provider/driver exceptions stored in durable evidence should retain exception type/stable code only, not arbitrary raw provider text.

## Production runtime

Runtime never silently migrates/provisions production control-plane schema or Warehouse marker schema.

Released immutable artifact remains complete DatasetConfig semantic truth.

SQL control plane stores deployed metadata/config identity plus runtime/evidence state; it does not replace source-controlled config.

## CLI/package dependency boundary

The command-line interface is a leaf presentation layer under:

```text
src/fabric_data_framework/cli/
```

Required dependency direction:

```text
CLI -> reusable framework core
reusable framework core -X-> CLI
```

Core semantics/runtime/provider/recovery/evidence/deployment modules must never import `fabric_data_framework.cli`.

Physical removal of the `cli/` directory is allowed to remove the console command, but must not make the reusable package core unimportable or unusable through Python APIs.

The removed root `src/fabric_data_framework/cli_router.py` compatibility path must remain absent. Do not reintroduce root-level CLI shims or command/business implementation.

New reusable logic belongs outside `cli/`; command handlers should only parse arguments, call reusable APIs, and render/write results.

## Evidence vocabulary discipline

Use CI/reference labels for deterministic implementation proof.

Only use live labels such as:

```text
FABRIC PROVEN
FABRIC WAREHOUSE PROVEN
PRODUCTION DB PROVEN
```

after retained approved real-service execution for the exact release candidate and exact certified artifact.
