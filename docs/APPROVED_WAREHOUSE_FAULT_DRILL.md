# Approved Fabric Warehouse Ambiguous-COMMIT Fault Drill

Status: implemented runner contract; real provider/network/driver fault evidence is still required.

## Purpose

`integration-warehouse-fault-drill-run` is deliberately separate from the normal
`integration-warehouse-run` stage.

The normal Warehouse stage proves target mutation + framework marker atomicity and the
framework's UNKNOWN recovery contract. The fault-drill stage exists for the stronger
claim that an actual provider/session/network fault was observed and independently
verified.

Fault-drill PASS still means exactly:

```text
actual provider/driver exception observed
verified exact injected fault identity
matching target marker -> COMMITTED
journal -> SUCCEEDED
later re-entry -> SKIP_SUCCEEDED
```

A normal transaction return can never PASS.

## Optional session-termination recovery

The same approved runner can now optionally exercise the independent PR #51
session-termination absence contract when an actual fault leaves the marker unresolved.
This is an **operational recovery result**, not a second way to PASS the fault drill.

```text
verified fault + marker UNRESOLVED
  -> exact target connection/session binding exists
  -> separately authorized Admin authority observes open transaction
  -> KILL exact session
  -> exact session disappears
  -> post-termination marker remains absent
  -> target journal may reconcile to NOT_COMMITTED
  -> retry becomes eligible
  -> fault-drill check remains FAIL
```

This separation is intentional:

```text
fault-drill PASS        = prove ambiguous operation actually COMMITTED
NOT_COMMITTED recovery  = prove operation safely did not commit and can be retried later
```

Do not collapse these into one evidence claim.

## Prerequisites

The exact-spec prerequisite manifest must already contain:

```text
FABRIC_ITEM_READ                         PASS
CONTROL_PLANE_CERTIFICATION             PASS
FABRIC_WAREHOUSE_TARGET_COMMIT          PASS
FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL NOT_RUN
```

The normal Warehouse PASS is required before fault injection.

## Runtime credential separation

Source-controlled `ApprovedIntegrationRunnerConfig` may name:

```json
{
  "control_plane_database_url_env_var": "FABRIC_CONTROL_PLANE_DATABASE_URL",
  "warehouse_database_url_env_var": "FABRIC_WAREHOUSE_DATABASE_URL",
  "warehouse_admin_database_url_env_var": "FABRIC_WAREHOUSE_ADMIN_DATABASE_URL"
}
```

Only environment-variable **names** belong in source control.

The Admin env-var name must differ from the ordinary Warehouse env-var name. This creates
an explicit least-privilege boundary:

```text
ordinary Warehouse credential -> target mutation / marker path
Admin Warehouse credential    -> optional session DMV / KILL path only
```

Routine target execution must not silently inherit session-termination authority.

## Run config

Example: `examples/dev_warehouse_fault_drill_run.json`.

Safe default:

```json
{
  "enable_session_termination_recovery": false
}
```

To exercise the additional NOT_COMMITTED recovery branch, explicitly set:

```json
{
  "enable_session_termination_recovery": true
}
```

Changing this flag changes the exact run-config hash, but it does not change the semantic
target operation input fingerprint. The target mutation/fault case remains the same
logical operation; only the independently authorized recovery capability changes.

## Authorization

Normal fault drill:

```bash
fabric-framework integration-warehouse-fault-drill-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/warehouse-prerequisites-merged.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --fault-config evidence/warehouse-fault-drill.json \
  --evidence-reference artifact:warehouse-fault-provider-log \
  --report-output evidence/warehouse-fault-report.json \
  --output evidence/warehouse-fault-partial.json \
  --allow-warehouse-fault-injection
```

When `enable_session_termination_recovery=true`, a second independent flag is mandatory:

```bash
  --allow-warehouse-session-termination
```

`--allow-warehouse-fault-injection` never implies permission to `KILL` a Warehouse
session.

The runner rejects session-termination mode before reading any secret values when:

```text
separate authorization flag is missing
warehouse_admin_database_url_env_var is absent
Admin env-var is empty
Admin env-var name equals ordinary Warehouse env-var name
```

## Secret-access order

The Admin credential value is intentionally more tightly gated than ordinary runtime
credentials.

It is not read merely because the run config enables recovery. The runner reads it only
when all of these are already true:

```text
actual execute_atomic exception observed
fault disarm succeeded
fault verification succeeded
fault identity matched
initial marker probe = UNRESOLVED
journal remains UNKNOWN
exact target session binding was captured before mutation
```

Therefore:

```text
COMMITTED marker path -> Admin URL value is never read
normal return         -> Admin URL value is never read
fault not verified    -> Admin URL value is never read
missing session bind  -> Admin URL value is never read
```

## Exact session binding

When session recovery is enabled, the framework captures the provider
`connection_id + session_id` on the exact SQLAlchemy target connection **before the
customer mutation**.

No weak fallback is allowed. If binding capture fails, the runner retains only the
exception type and the recovery branch cannot use Admin session termination.

Canonical provider contract:

```text
docs/FABRIC_WAREHOUSE_SESSION_ABSENCE_CERTIFIER.md
```

## COMMITTED path

The existing PASS path is unchanged:

```text
claim EXECUTE
 -> arm exact fault
 -> target execute raises
 -> disarm
 -> journal UNKNOWN
 -> plain marker probe COMMITTED
 -> fault verify triggered + identity match
 -> journal SUCCEEDED
 -> later claim SKIP_SUCCEEDED
 -> PASS
```

Even when session recovery is configured and authorized, this path never constructs the
Admin session authority because the primary marker already proves commit.

## NOT_COMMITTED recovery path

Only after a verified fault remains `UNRESOLVED` does the runner construct the separate
Admin engine and invoke the session-termination absence certifier.

The certifier requires:

```text
exact connection_id + session_id
same exact session still observable
open_transaction_count > 0
Admin KILL exact session
same exact connection/session disappears
post-termination marker read succeeds
marker still absent
```

If safe absence is proven:

```text
UNKNOWN -> NOT_COMMITTED
retry_eligible = true
reentry_action = null
fault drill = FAIL / SAFE_NOT_COMMITTED_AFTER_SESSION_TERMINATION
```

The runner deliberately does **not** call `claim_target_operation()` after
`NOT_COMMITTED`, because that would reopen the durable operation to `IN_PROGRESS` without
actually performing the retry. A future intentional execution may claim it later.

## Termination race

A commit can win the race immediately before session termination. PR #51 therefore
requires a second marker read after termination.

If the absence certifier stays unresolved, the approved runner performs one additional
plain marker probe:

```text
marker appears -> COMMITTED may reconcile to SUCCEEDED
marker absent  -> still UNRESOLVED / UNKNOWN
```

That final probe can only recognize positive commit evidence; it never turns absence into
`NOT_COMMITTED` by itself.

## Fail-closed cases

```text
normal transaction return                         -> fault drill FAIL
injector triggered=true without observed exception -> FAIL
fault identity mismatch                           -> FAIL
binding capture failure                           -> FAIL / no Admin path
session not captured                              -> FAIL / no Admin path
Admin authority construction failure              -> FAIL / UNKNOWN
DMV/KILL/post-check failure                       -> FAIL / UNKNOWN
session already disappeared before inspection     -> FAIL / UNKNOWN
no observable open transaction                    -> FAIL / UNKNOWN
marker remains absent without certified rollback  -> FAIL / UNKNOWN
safe session rollback + marker absent              -> FAIL / NOT_COMMITTED / retry eligible
```

Raw provider/driver/Admin exception messages are never retained; exception types only.

## Report additions

The safe report may now retain:

```text
session_termination_recovery_enabled
session_termination_authorized
session_binding_captured
session_id
connection_id
session_binding_capture_exception_type
session_termination_recovery_attempted
session_recovery_exception_type
absence_safe_to_retry
retry_eligible
```

Session/connection IDs are provider correlation, not credentials. Database URLs and
credential values are never serialized.

## Evidence labels

COMMITTED real-fault runner contract:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT
```

Optional NOT_COMMITTED recovery wiring, once deterministic exact-head CI passes:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE SESSION-TERMINATION RECOVERY CONTRACT
```

Neither label proves a live Fabric fault or production-approved Admin KILL path. Stronger
claims require retained exact-release real execution using the selected enterprise
identity, SQL driver, Warehouse and separately controlled Admin authority.
