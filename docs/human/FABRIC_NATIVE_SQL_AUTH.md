# Fabric-native SQL authentication

## Purpose

The Framework supports Microsoft Fabric teams that have Fabric workspace permissions but do not administer Azure Key Vault or other Azure resources.

The SQL runtime has two explicit lanes:

```text
database-url   existing generic SQLAlchemy URL supplied at runtime
fabric-user    signed-in Fabric Notebook user identity + non-secret SQL endpoint identity
```

`database-url` remains the backward-compatible default when `FABRIC_SQL_AUTH_MODE` is absent. Customer/domain runtimes that want Fabric-native authentication must set:

```text
FABRIC_SQL_AUTH_MODE=fabric-user
```

## Fabric-user runtime inputs

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

These values are deployment identity, not credentials. Server validation accepts a plain hostname with optional port 1433 and rejects URLs, userinfo, paths, query strings and connection-string fragments. Database-name validation rejects connection-string injection characters.

The helper:

```python
from fabric_data_framework.adapters.fabric.sql_auth import prepare_fabric_user_sql_runtime

runtime = prepare_fabric_user_sql_runtime(runtime_environment)
```

creates compatible in-process values for:

```text
CONTROL_PLANE_DATABASE_URL
WAREHOUSE_DATABASE_URL
```

The generated URLs contain only server, database, driver, encryption settings and an internal Framework marker. They do not contain a password, bearer token or client secret.

## Entra token injection

The Fabric-native lane requires:

```text
pyodbc
Microsoft ODBC Driver 18 or newer for SQL Server
notebookutils.credentials
```

A fresh Microsoft Entra SQL access token is requested when a physical DBAPI connection is opened. The token audience is:

```text
https://database.windows.net/
```

The token is encoded for `SQL_COPT_SS_ACCESS_TOKEN` and supplied through the ODBC `attrs_before` connection attribute. It is never inserted into the SQLAlchemy URL or retained in evidence.

The token-aware SQLAlchemy hook acts only on Framework-marked `mssql+pyodbc` URLs. Other SQLAlchemy engines in the same process are not converted to Fabric-user authentication.

## Compatibility and preflight

Approved integration preflight is mode-aware:

- `database-url` requires the configured `*_DATABASE_URL` runtime variable.
- `fabric-user` requires the corresponding non-secret server/database variables.

The existing runner configuration still names `CONTROL_PLANE_DATABASE_URL` and `WAREHOUSE_DATABASE_URL` for backward compatibility. `prepare_fabric_user_sql_runtime` synthesizes those values before existing SQLAlchemy-based certification runners execute.

## Warehouse administrator boundary

Normal `fabric-user` authentication is **not** treated as Warehouse administrator/session-control authority.

The separate `warehouse_admin_database_url_env_var` contract remains explicit. Real ambiguous-COMMIT recovery that requires session termination must still have:

```text
separately approved admin/session-control runtime credential
authorized fault controller
explicit mutation/session-termination authorization
```

The Framework never promotes a normal signed-in Fabric user credential to this role merely because the user is a workspace Admin.

## Failure behavior

The Fabric-native lane fails closed when:

```text
server/database identity is missing or malformed
pyodbc is unavailable
ODBC Driver 18+ is unavailable
notebookutils credentials are unavailable
SQL token acquisition returns no token
SQL connection/authentication fails
```

Do not work around these failures by embedding a password or token into source code, a Pipeline definition, retained evidence or a CLI argument.
