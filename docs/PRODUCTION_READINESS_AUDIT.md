# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit
Last updated: 2026-08-29

## Evidence model

This audit separates:

1. portable semantic implementation;
2. deterministic CI/reference proof;
3. real provider/Fabric execution evidence;
4. external enterprise controls.

Green CI proves levels 1/2 only. Executable HTTP/SQL code is not real Fabric/production-database evidence until approved service runs are retained.

## Current assessment

```text
Portable semantic implementation             STRONG / broad core product slice
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
Real Fabric/Kafka/Delta execution             NOT YET PROVEN
Real production SQL backend                   NOT YET PROVEN
External enterprise controls                  EXTERNAL / NOT PROVEN BY THIS REPO
```

Latest validated merged implementation:

```text
67562e4312dc9c37e8b7fb8d79535bb621bd573f
PR #28 validation: GitHub Actions 33247800732
372 tests
Python 3.11 + 3.13 + wheel/static checks green
Fabric Warehouse target mutation + atomic marker proof + durable journal reconciliation
```

Previous provider/runtime baselines:

```text
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
| Provider-neutral target commit probe | Yes | Yes | Provider-specific Warehouse implementation now exists | IMPLEMENTED contract |
| Control-plane v4 + backend certification | Yes | Yes | No real production candidate run | IMPLEMENTED/CI PROVEN contract |
| SQLAlchemy `ControlPlaneRepository` | Yes | Yes | No real Fabric/Azure SQL | IMPLEMENTED/CI PROVEN relational runtime |
| Fabric REST Job Scheduler | Yes | Yes | No live Fabric call | IMPLEMENTED/CI PROVEN transport |
| Fabric Data Pipeline backend | Yes | Yes | No live Pipeline job | IMPLEMENTED/CI PROVEN backend |
| Copy Job REST capture transport | Yes | Yes | No live Copy Job | IMPLEMENTED/CI PROVEN transport contract |
| Spark Job Definition REST capture transport | Yes | Yes | No live SJD | IMPLEMENTED/CI PROVEN transport contract |
| Mandatory Copy/Spark post-run observation | Yes | Yes | No real observer | IMPLEMENTED/CI PROVEN contract |
| Warehouse target-side marker table contract | Yes | Yes | No real Warehouse table | IMPLEMENTED/CI PROVEN provider contract |
| Warehouse target mutation + marker same transaction | Yes | SQLite/reference transaction proof | No real Warehouse transaction | IMPLEMENTED/CI PROVEN provider contract |
| Existing committed marker prevents re-execution | Yes | Yes | No real Warehouse | IMPLEMENTED/CI PROVEN |
| Marker absence defaults to `UNRESOLVED` | Yes | Yes | N/A | IMPLEMENTED/CI PROVEN |
| Independently certified absence may yield `NOT_COMMITTED` | Yes | Yes | No approved real certifier | IMPLEMENTED contract |
| Query Insights only secondary correlation | Yes | Yes | No real query history | IMPLEMENTED guardrail |
| UNKNOWN journal + committed Warehouse marker -> SUCCEEDED | Yes | Yes | No real Warehouse | IMPLEMENTED/CI PROVEN integration |
| Approved DEV end-to-end execution | No | No | No | P0 GAP |

## Fabric Warehouse target commit readiness

Canonical runbook: `docs/FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md`.

### Primary proof

The target mutation and framework target-side marker are executed through the same target transaction:

```text
BEGIN TRAN
  target mutation
  operation marker
COMMIT TRAN
```

This design is based on the current Fabric Warehouse ACID explicit transaction model. The marker repeats the stable `TargetOperationIntent` semantic identity and retains optional native statement/label evidence.

The marker table is not auto-created by runtime. Its persisted columns use a Warehouse-safe logical type contract based on varchar/integer/datetime2 semantics.

### Concurrency authority

The target marker is not the distributed execution lock. Existing target-operation CAS in the framework control plane remains the authority for `EXECUTE` vs `RECONCILE_REQUIRED`.

This is deliberate because Warehouse constraints can use `NOT ENFORCED` semantics; portable exactly-once behavior must not depend on a target uniqueness constraint that might not be enforced.

### Probe rules

```text
matching committed marker -> COMMITTED
marker absent              -> UNRESOLVED
marker absent + certified independent no-late-commit proof -> NOT_COMMITTED
```

Marker absence alone never grants retry.

### Query Insights

`distributed_statement_id`, label and command history can be useful secondary diagnostics. Current product documentation warns that completed query history can lag by up to roughly 15 minutes under load, so Query Insights presence/absence is not immediate commit truth.

### Journal integration

CI proves:

```text
framework EXECUTE claim
  -> target mutation + marker commit
  -> simulated lost acknowledgement
  -> framework UNKNOWN
  -> FabricWarehouseTargetCommitProbe
  -> durable SUCCEEDED
  -> future claim SKIP_SUCCEEDED
```

Correct label: `IMPLEMENTED + CI PROVEN PROVIDER COMMIT CONTRACT`, not `FABRIC WAREHOUSE PROVEN`.

## Concrete Fabric capture readiness

Canonical runbook: `docs/FABRIC_CAPTURE_REST_TRANSPORTS.md`.

Copy Job and Spark Job Definition now have concrete item-specific REST transports. Provider `Completed` does not itself prove rows/landing/bounds/native checkpoint; successful capture requires post-run observation before `CaptureReceipt`.

Copy Job remains provider-native progress owned; framework bounds are rejected. Current Copy Job CDC fidelity is treated as net-change constrained.

Spark bounded capture requires an explicit resolver into the selected released SJD `executionData` contract.

Correct label: `IMPLEMENTED + CI PROVEN TRANSPORT CONTRACT`, not `FABRIC PROVEN`.

## Relational runtime / control plane readiness

`SqlAlchemyControlPlaneRepository` validates released immutable config against deployed SQL `config_hash` and persists runtime/evidence state. It requires an explicitly migrated exact schema.

Production candidates remain:

```text
fabric_sql_database_v1
azure_sql_database_v1
```

Portable runtime and certification code now exist. The remaining control-plane gate is a real selected backend run plus retained backend identity/IAM/network/backup/DR/monitoring/governance evidence.

## Remaining release-significant work

### P0 approved DEV evidence harness

1. provide a repeatable environment binding/authentication/evidence-manifest workflow that executes the already-implemented Fabric transports without embedding credentials in config or evidence;
2. retain framework IDs, native Fabric job/root IDs, target marker references and provider error/retry evidence in one auditable run bundle;
3. make the harness fail closed when expected evidence is missing.

### P0 real service evidence

1. execute real Fabric Pipeline, Copy Job and Spark Job Definition paths in an approved DEV workspace;
2. execute real Fabric Warehouse mutation + marker transactions;
3. drill ambiguous network/client failure around Warehouse COMMIT and certify any marker-absence behavior only from the observed driver/session semantics;
4. run control-plane certification against the selected real SQL backend;
5. exercise live Kafka/Delta paths only if included in the `0.4.0` product promise;
6. retain auth/network/capacity and enterprise-control evidence.

### Release decision

Only after exact-candidate code/tests/docs and retained real evidence agree may `0.4.0` be considered for public release.

## External evidence this repo must not fake

Capacity/SKU/throttling, tenant settings, workspace/domain provisioning, Entra/RBAC, gateway/private networking, secret authority, source CDC/CDF enablement/retention, broker/database/API access, backup/restore, monitoring/on-call, privacy/retention and enterprise change controls remain external evidence.

## Release gate

Current decision: **release remains blocked. PR #28 closes the portable Fabric Warehouse target-commit proof gap. The next implementation gate is a repeatable approved-DEV evidence harness and then retained real service execution/certification.**
