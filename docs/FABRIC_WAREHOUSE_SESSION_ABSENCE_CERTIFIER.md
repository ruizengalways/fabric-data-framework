# Fabric Warehouse Session-Termination Absence Certifier

Status: provider-specific contract implemented; approved live certification is still required.

## Purpose

The normal Fabric Warehouse recovery rule is intentionally conservative:

```text
matching target marker -> COMMITTED
marker absent           -> UNRESOLVED
```

Marker absence alone cannot mean `NOT_COMMITTED`, because a COMMIT acknowledgement can
be lost while the transaction is still completing.

This contract defines one narrow Fabric Warehouse-specific path that may prove that an
absent marker cannot arrive later:

```text
exact target connection/session identity retained before mutation
  -> same exact session is still observable after the ambiguous exception
  -> same exact session has open_transaction_count > 0
  -> independent Admin-capable connection KILLs that session
  -> exact connection/session is no longer observable
  -> target marker is read again after termination
  -> marker is still absent
  -> absence evidence may set safe_to_retry=true
  -> target probe may resolve NOT_COMMITTED
```

Every step is required. Failure or uncertainty at any step remains `UNRESOLVED`.

## Microsoft Fabric basis

Microsoft documents Fabric Warehouse query-lifecycle DMVs including:

```text
sys.dm_exec_connections
sys.dm_exec_sessions
sys.dm_exec_requests
```

and documents that only a workspace Admin can use `KILL <session_id>`. The documented
`KILL` behavior ends the session and rolls back work in that session's active
transaction.

References:

- https://learn.microsoft.com/en-us/fabric/data-warehouse/monitor-using-dmv
- https://learn.microsoft.com/en-us/fabric/data-warehouse/troubleshoot-query-blocking
- https://learn.microsoft.com/en-us/fabric/data-warehouse/transactions

The implementation uses the exact provider connection UUID as well as numeric session
ID. Numeric `session_id` alone is not sufficient because session IDs may later be reused.

## Why Query Insights is not an absence certifier

Query Insights is useful secondary correlation, not immediate commit truth. Microsoft
documents that completed query history can take up to approximately 15 minutes to become
visible depending on concurrent workload.

References:

- https://learn.microsoft.com/en-us/fabric/data-warehouse/query-insights
- https://learn.microsoft.com/en-us/fabric/data-warehouse/query-activity

Therefore:

```text
no Query Insights row != NOT_COMMITTED
completed-session history != immediate no-late-commit proof
```

## Session binding

`FabricWarehouseSessionBinding` retains only non-secret provider identity:

```text
session_id
connection_id
```

`capture_fabric_warehouse_session_binding(connection)` must run on the same SQLAlchemy
`Connection` that owns the target transaction. The reference implementation uses:

```sql
SELECT TOP (1)
    c.connection_id,
    c.session_id
FROM sys.dm_exec_connections AS c
WHERE c.session_id = @@SPID;
```

The session identity is evidence metadata, not a credential.

## Independent authority

`SqlAlchemyFabricWarehouseSessionAuthority` uses a separate connection to inspect the
bound session through `sys.dm_exec_connections` + `sys.dm_exec_sessions`.

The terminating identity must have the provider permission required by Fabric for
`KILL`; Microsoft currently documents this as workspace Admin.

That is intentionally stronger privilege than routine target mutation. Production use
should keep this authority separately controlled and explicitly authorized rather than
silently granting Admin to every normal data-engineering connection.

## Fail-closed conditions

The certifier returns `safe_to_retry=false` when any of the following occurs:

```text
exact session is already gone before it can be inspected
connection/session identity does not match the retained binding
open_transaction_count == 0
session observation fails
KILL fails
session remains observable after KILL
post-KILL session observation fails
post-KILL marker read fails
marker appears during the termination race
```

Provider/driver exception text is not retained. Only exception type is included in
framework evidence.

### Important race rule

A commit may win the race immediately before termination. Therefore the certifier must
read the target marker **again after session termination**.

```text
initial marker absent
  -> terminate exact open transaction session
  -> second marker read
       marker present -> safe_to_retry=false
       marker absent  -> eligible safe_to_retry=true
```

If the marker appears, this certifier deliberately does not claim `NOT_COMMITTED`. The
surrounding recovery flow may later re-probe and recognize `COMMITTED`; until then it
remains fail-closed.

## What this contract does not prove

Deterministic tests prove only the provider contract and fail-closed decision rules.
They do not prove that the selected Fabric tenant, identity, ODBC/SQL driver and
Warehouse accept every statement or permission path in a real approved environment.

Before calling this production-approved evidence, retain an exact-release real drill
that proves:

```text
same target connection/session binding captured
Admin DMV observation works
open transaction is observed for the ambiguous operation
KILL succeeds against that exact session
session disappearance is observed
post-termination marker remains absent
journal reconciles to NOT_COMMITTED
subsequent EXECUTE claim is allowed only after that durable reconciliation
```

## Evidence label

Until that real approved run exists, use:

```text
IMPLEMENTED + CI PROVEN FABRIC WAREHOUSE SESSION-TERMINATION ABSENCE CERTIFIER CONTRACT
```

Do not use `PRODUCTION-APPROVED MARKER-ABSENCE CERTIFIER`, `FABRIC WAREHOUSE PROVEN`, or
similar live-service labels based on CI alone.
