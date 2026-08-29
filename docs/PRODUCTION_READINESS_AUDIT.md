# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-29

## Evidence model

This audit separates:

1. portable semantic implementation;
2. deterministic CI/reference proof;
3. real provider/Fabric execution evidence;
4. external enterprise controls.

Green CI proves levels 1/2 only. Executable HTTP/SQL/evidence code is not real Fabric/production-database evidence until approved service runs are retained for the exact environment and release hash.

## Current assessment

```text
Portable semantic implementation             STRONG / broad reusable product slice
Deterministic certification                   STRONG for implemented slices
Source-fidelity onboarding                    IMPLEMENTED / CI PROVEN reference
Target-operation journal                      IMPLEMENTED / CI PROVEN reference
Provider-native recovery contracts            IMPLEMENTED / CI PROVEN reference
Control-plane certification framework         IMPLEMENTED / CI PROVEN contract
Fabric Data Pipeline backend                  IMPLEMENTED / CI PROVEN backend
SQLAlchemy runtime repository                 IMPLEMENTED / CI PROVEN relational runtime
Copy Job REST capture transport               IMPLEMENTED / CI PROVEN transport contract
Spark Job Definition capture transport        IMPLEMENTED / CI PROVEN transport contract
Fabric Warehouse target commit proof          IMPLEMENTED / CI PROVEN provider contract
Approved-environment evidence harness         IMPLEMENTED / CI PROVEN contract
Approved-run preflight                        IMPLEMENTED / CI PROVEN contract
Read-only Fabric item smoke runner            IMPLEMENTED / CI PROVEN runner contract
Real approved DEV Fabric execution            NOT YET PROVEN
Real production SQL backend                   NOT YET PROVEN
External enterprise controls                  EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest validated merged implementation:

```text
e42dee86db3d4102c7264bc0d1f01f83fb8aade2
PR #32 validation: GitHub Actions 33251177339
407 tests
Python 3.11 + 3.13 + wheel/static checks green
Approved DEV exact-release preflight + staged read-only Fabric item smoke runner
```

Previous evidence/provider baselines:

```text
PR #30 -> 732920e214ccdead20c632f7e70c0eb8f1267f0d
395 tests
approved DEV integration evidence harness + native capture evidence retention

PR #28 -> 67562e4312dc9c37e8b7fb8d79535bb621bd573f
372 tests
Fabric Warehouse target mutation + atomic marker proof + durable journal reconciliation

PR #26 -> 8f23942acd5b03d817e42b97d9f490acc6bee89f
362 tests
Copy Job + Spark Job Definition concrete capture REST transports

PR #24 -> 2fa8e2c4bc6875b529a4968694722d4108a635ff
350 tests
SQLAlchemy runtime repository + durable Fabric child/parent outcome handoff
```

`v0.3.0` remains the latest public release. **Do not publish v0.4.0 yet.**

## Capability assessment

| Capability | Code | CI/reference proof | Real service | Assessment |
|---|---:|---:|---:|---|
| Typed metadata/effective config | Yes | Yes | N/A | IMPLEMENTED |
| 14-pattern source-fidelity catalog | Yes | Yes | N/A | IMPLEMENTED reference |
| APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF | Yes | Yes | No | IMPLEMENTED reference |
| Canonical CDC + downstream checkpoint | Yes | Yes | No | IMPLEMENTED reference |
| Kafka cursor coordination/retention safety | Yes | Yes | No live broker | IMPLEMENTED/CI PROVEN reference |
| Delta CDF normalization/resume safety | Yes | Yes | No live Lakehouse CDF | IMPLEMENTED/CI PROVEN reference |
| Durable target-operation identity/CAS | Yes | Yes | No live target | IMPLEMENTED/CI PROVEN reference |
| Provider-neutral target commit probe | Yes | Yes | Warehouse provider implementation exists | IMPLEMENTED contract |
| Control-plane v4 + backend certification | Yes | Yes | No real production candidate run | IMPLEMENTED/CI PROVEN contract |
| SQLAlchemy `ControlPlaneRepository` | Yes | Yes | No real Fabric/Azure SQL | IMPLEMENTED/CI PROVEN relational runtime |
| Fabric REST Job Scheduler | Yes | Yes | No live Fabric call | IMPLEMENTED/CI PROVEN transport |
| Fabric Data Pipeline backend | Yes | Yes | No live Pipeline job | IMPLEMENTED/CI PROVEN backend |
| Copy Job REST capture transport | Yes | Yes | No live Copy Job | IMPLEMENTED/CI PROVEN transport contract |
| Spark Job Definition REST capture transport | Yes | Yes | No live SJD | IMPLEMENTED/CI PROVEN transport contract |
| Copy/Spark verified receipt + native evidence result | Yes | Yes | No live native IDs | IMPLEMENTED/CI PROVEN contract |
| Mandatory Copy/Spark post-run observation | Yes | Yes | No real observer | IMPLEMENTED/CI PROVEN contract |
| Warehouse target mutation + marker same transaction | Yes | Reference transaction proof | No real Warehouse transaction | IMPLEMENTED/CI PROVEN provider contract |
| UNKNOWN journal + committed Warehouse marker -> SUCCEEDED | Yes | Yes | No real Warehouse | IMPLEMENTED/CI PROVEN integration |
| Ephemeral Fabric token-provider boundary | Yes | Yes | No approved tenant identity run | IMPLEMENTED/CI PROVEN contract |
| Integration evidence spec/manifest/hash | Yes | Yes | No retained real bundle | IMPLEMENTED/CI PROVEN contract |
| Secret-bearing retained evidence rejection | Yes | Yes | N/A | IMPLEMENTED/CI PROVEN guardrail |
| Exact release/env/check evidence validation | Yes | Yes | No real bundle | IMPLEMENTED/CI PROVEN contract |
| Exact-release approved runner config | Yes | Yes | No real tenant config exercised | IMPLEMENTED/CI PROVEN contract |
| Runtime-secret presence-only preflight | Yes | Yes | No real env run | IMPLEMENTED/CI PROVEN guardrail |
| Mutating-check explicit authorization gate | Yes | Yes | N/A | IMPLEMENTED/CI PROVEN guardrail |
| Staged read-only item preflight | Yes | Yes | No live workspace/item | IMPLEMENTED/CI PROVEN contract |
| Read-only item smoke CLI + partial manifest | Yes | Fake HTTP provider proof | No live workspace/item | IMPLEMENTED/CI PROVEN runner contract |
| CLI `--require-certified` evidence gate | Yes | Yes | No real bundle | IMPLEMENTED/CI PROVEN contract |
| Approved DEV end-to-end execution | Runner/harness ready | No provider execution | No | P0 REAL-EVIDENCE GAP |

## Approved DEV runner readiness

Canonical runbook: `docs/DEV_INTEGRATION_EVIDENCE.md`.

PR #32 adds `ApprovedIntegrationRunnerConfig` and `ApprovedIntegrationRunPlan` so source control contains only exact release identity, check IDs, workspace/item UUIDs, profile names and **environment-variable names**. Runtime token/database values are inspected only for presence and are never serialized into the plan.

Preflight enforces:

```text
config/spec environment match
config/spec domain match
config/spec framework version match
config/spec release_hash match
selected check IDs declared in spec
Fabric checks have explicit workspace/item bindings
bindings do not reference undeclared checks
required runtime values exist
mutating checks explicitly authorized
```

The runner supports staged subsets. Therefore the first enterprise step can be only:

```text
fabric.item.read
```

without requiring control-plane/Warehouse DB credentials and without authorizing mutating checks.

PR #32 also adds the first live-capable CLI path:

```text
integration-item-smoke-run
```

It performs the current read-only Fabric item GET, verifies returned item identity, and writes a partial `IntegrationEvidenceManifest`. Other required checks remain `NOT_RUN`, so one successful item read cannot accidentally certify the release.

Provider/identity errors are retained only as sanitized FAIL evidence. The runtime access token is not written to the plan or manifest.

Correct label: `IMPLEMENTED + CI PROVEN APPROVED-RUN PREFLIGHT / READ-ONLY RUNNER CONTRACT`, not `FABRIC PROVEN`.

## Approved DEV evidence readiness

PR #30 provides the exact-release evidence spec/result/manifest layer. Required checks certify only on `PASS`; missing runners become `NOT_RUN`, runner exceptions become sanitized `FAIL`, and undeclared runner IDs fail closed.

The intended real DEV order is now:

```text
exact-release runner config + evidence spec
  -> staged read-only preflight
  -> live item authorization smoke
  -> real control-plane certification
  -> real Pipeline handoff
  -> real Copy Job capture
  -> real bounded Spark capture
  -> real Warehouse target + marker
  -> required failure drills
  -> complete IntegrationEvidenceManifest
  -> integration-evidence-validate --require-certified
```

Pipeline evidence requires framework run/dataset IDs and native workspace/item/job/root correlation and does not replace the Pipeline backend's semantic outcome requirement.

Copy/Spark use `execute_with_evidence()` so one provider invocation yields both verified `CaptureReceipt` and native diagnostics.

Warehouse evidence is based on the same-transaction operation marker, not Query Insights history.

Control-plane evidence reuses the existing certification report rather than inventing a second database certification path.

## Fabric Warehouse target commit readiness

Canonical runbook: `docs/FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md`.

Primary proof remains:

```text
BEGIN TRAN
  target mutation
  operation marker
COMMIT TRAN
```

Framework control-plane target-operation CAS remains the execution/retry authority. The Warehouse marker is independent target-side commit proof, not a distributed concurrency lock.

Probe rules remain:

```text
matching committed marker -> COMMITTED
marker absent              -> UNRESOLVED
marker absent + certified independent no-late-commit proof -> NOT_COMMITTED
```

Marker absence alone never grants retry. Query Insights/labels remain secondary correlation because query history visibility can lag.

Correct label: `IMPLEMENTED + CI PROVEN PROVIDER COMMIT CONTRACT`, not `FABRIC WAREHOUSE PROVEN`.

## Concrete Fabric capture readiness

Canonical runbook: `docs/FABRIC_CAPTURE_REST_TRANSPORTS.md`.

Copy Job and Spark Job Definition have concrete item-specific REST transports. Provider `Completed` does not prove rows/landing/bounds/native checkpoint; successful capture requires post-run observation before `CaptureReceipt`.

Copy Job remains provider-native progress owned; framework source bounds are rejected. Current Copy Job CDC fidelity remains net-change constrained.

Spark bounded capture requires an explicit resolver into the selected released SJD `executionData` contract.

Correct label: `IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT`, not `FABRIC PROVEN`.

## Relational runtime / control-plane readiness

`SqlAlchemyControlPlaneRepository` validates released immutable config against deployed SQL `config_hash` and persists runtime/evidence state. It requires an explicitly migrated exact schema.

Production candidates remain:

```text
fabric_sql_database_v1
azure_sql_database_v1
```

Portable runtime and certification code now exist. The remaining control-plane gate is a real selected backend run plus retained backend identity/IAM/network/backup/DR/monitoring/governance evidence.

## Remaining release-significant work

### P0 real approved DEV execution

1. replace placeholder release hash and UUIDs in a DEV runner config with the exact candidate release and real DEV items;
2. authenticate through the enterprise-approved identity path without persisting credentials;
3. run staged read-only preflight and pass the real Fabric item identity smoke;
4. accumulate the resulting partial evidence without rerunning already-proven checks;
5. run real control-plane certification through runtime-only database credentials;
6. execute representative real Pipeline, Copy Job and bounded Spark paths and retain framework/native correlation;
7. execute real Warehouse mutation + marker transaction;
8. run the approved failure drills and retain provider errors/retry/ambiguous-outcome evidence;
9. assemble a sanitized complete `IntegrationEvidenceManifest` and pass the exact `--require-certified` gate.

### P0 real control-plane / enterprise evidence

1. run certification against the chosen real Fabric SQL Database or Azure SQL Database instance;
2. retain backend service identity and IAM evidence;
3. retain network security evidence;
4. retain backup/restore and availability/recovery evidence;
5. retain monitoring/alerting and retention/governance evidence.

### Provider scope decision

Kafka and Delta CDF already have deterministic recovery contracts. Wire and exercise live clients only if those provider profiles are part of the `0.4.0` public product promise; otherwise explicitly defer them rather than blocking unrelated Fabric release evidence.

### Release decision

Only after exact-candidate code/tests/docs and retained real evidence agree may `0.4.0` be considered for public release.

## External evidence this repo must not fake

Capacity/SKU/throttling, tenant settings, workspace/domain provisioning, Entra/RBAC, gateway/private networking, secret authority, source CDC/CDF enablement/retention, broker/database/API access, backup/restore, monitoring/on-call, privacy/retention and enterprise change controls remain external evidence.

## Release gate

Current decision: **release remains blocked. PR #32 closes the environment-facing preflight and safe first-call runner gap. The next gate is actual exact-release DEV evidence: live item authorization first, then real SQL certification and explicitly authorized provider executions/failure drills.**
