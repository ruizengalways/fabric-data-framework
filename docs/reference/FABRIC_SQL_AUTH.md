# Fabric SQL authentication reference

This reference describes the framework SQL authentication lanes. It is intentionally narrow; architecture belongs in [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

## Authentication lanes

```text
database-url
  generic SQLAlchemy URL supplied at runtime

fabric-user
  signed-in Fabric Notebook user identity + non-secret SQL endpoint identity
```

When using Fabric-native user authentication:

```text
FABRIC_SQL_AUTH_MODE=fabric-user
```

## Non-secret endpoint identity

Control Plane:

```text
CONTROL_PLANE_SQL_SERVER
CONTROL_PLANE_SQL_DATABASE
```

Warehouse:

```text
WAREHOUSE_SQL_SERVER
WAREHOUSE_SQL_DATABASE
```

These values identify the endpoint; they are not credentials. Validation rejects URLs, user-info, paths, query strings and connection-string fragments where only a server/database identity is expected.

## Runtime preparation

```python
from fabric_data_framework.adapters.fabric.sql_auth import prepare_fabric_user_sql_runtime

runtime = prepare_fabric_user_sql_runtime(runtime_environment)
```

The helper produces compatible in-process URL-shaped runtime handles such as:

```text
CONTROL_PLANE_DATABASE_URL
WAREHOUSE_DATABASE_URL
```

Generated handles contain endpoint/driver/encryption configuration and a framework marker, not password/token/client-secret values.

## Entra token injection

The Fabric-user lane expects:

```text
pyodbc
Microsoft ODBC Driver 18+ for SQL Server
notebookutils.credentials
```

A fresh Microsoft Entra SQL access token is obtained when a physical DBAPI connection opens, for audience:

```text
https://database.windows.net/
```

The token is supplied through the ODBC access-token connection attribute. It is not embedded in SQLAlchemy URLs and must not be retained in evidence.

The token hook applies only to framework-marked `mssql+pyodbc` URLs.

## Approved-run preflight boundary

Approved evidence runners keep their URL-env-name preflight contract. A project/runtime using `fabric-user` first prepares the non-secret runtime handles, then executes normal approved-run preflight.

This preserves fail-closed behavior: an unauthorized approved run does not probe additional authentication state before its authorization gate.

## Warehouse administrator boundary

Normal Fabric-user authentication does not imply session-control authority.

A recovery flow requiring exact-session termination still needs:

```text
separate approved admin/session-control credential
authorized fault controller
explicit session-termination authorization
```

The framework never promotes ordinary workspace/user access to this role automatically.

## Failure behavior

Fabric-user authentication fails closed when endpoint identity is invalid, required ODBC/runtime components are unavailable, token acquisition fails or SQL authentication fails.

Never work around these failures by embedding passwords, tokens or connection strings with credentials in source code, Pipeline definitions, CLI arguments or retained evidence.
