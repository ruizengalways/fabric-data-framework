"""Microsoft Fabric SQL runtime authentication helpers.

The framework supports two SQL runtime lanes:

* ``database-url`` keeps the existing generic SQLAlchemy URL contract. The URL value
  remains runtime-only and may be supplied by any approved secret mechanism.
* ``fabric-user`` uses the signed-in Microsoft Fabric Notebook user identity. Only the
  non-secret SQL server and database names are supplied in configuration; a fresh
  Microsoft Entra access token is requested for every new DBAPI connection.

This module deliberately does not know about Azure Key Vault. Secret resolution is a
customer/runtime concern, while SQL authentication is a framework concern.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import re
import struct
from typing import Any, Literal

from sqlalchemy import Engine, create_engine


FABRIC_SQL_AUTH_MODE_ENV_VAR = "FABRIC_SQL_AUTH_MODE"
FABRIC_SQL_AUTH_MODE_DATABASE_URL = "database-url"
FABRIC_SQL_AUTH_MODE_USER = "fabric-user"
FABRIC_SQL_TOKEN_AUDIENCE = "https://database.windows.net/"
SQL_COPT_SS_ACCESS_TOKEN = 1256

CONTROL_PLANE_SQL_SERVER_ENV_VAR = "CONTROL_PLANE_SQL_SERVER"
CONTROL_PLANE_SQL_DATABASE_ENV_VAR = "CONTROL_PLANE_SQL_DATABASE"
WAREHOUSE_SQL_SERVER_ENV_VAR = "WAREHOUSE_SQL_SERVER"
WAREHOUSE_SQL_DATABASE_ENV_VAR = "WAREHOUSE_SQL_DATABASE"

SqlRuntimeRole = Literal["control-plane", "warehouse", "warehouse-admin"]
EngineFactory = Callable[[str], Engine]
TokenGetter = Callable[[str], str]

_DRIVER_RE = re.compile(r"^ODBC Driver (?P<version>\d+) for SQL Server$")
_SERVER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,253}[A-Za-z0-9])?(?:(?:,|:)1433)?$")


def _nonempty(environ: Mapping[str, str], name: str) -> str | None:
    value = environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def fabric_sql_auth_mode(environ: Mapping[str, str]) -> str:
    """Return the validated SQL runtime auth mode.

    Absence intentionally preserves the historical ``database-url`` behavior so older
    Customer bundles and generic relational backends remain compatible.
    """

    mode = _nonempty(environ, FABRIC_SQL_AUTH_MODE_ENV_VAR) or FABRIC_SQL_AUTH_MODE_DATABASE_URL
    if mode not in {FABRIC_SQL_AUTH_MODE_DATABASE_URL, FABRIC_SQL_AUTH_MODE_USER}:
        raise ValueError(
            f"unsupported {FABRIC_SQL_AUTH_MODE_ENV_VAR}={mode!r}; expected "
            f"{FABRIC_SQL_AUTH_MODE_DATABASE_URL!r} or {FABRIC_SQL_AUTH_MODE_USER!r}"
        )
    return mode


def _role_endpoint_env_vars(role: SqlRuntimeRole) -> tuple[str, str]:
    if role == "control-plane":
        return CONTROL_PLANE_SQL_SERVER_ENV_VAR, CONTROL_PLANE_SQL_DATABASE_ENV_VAR
    if role == "warehouse":
        return WAREHOUSE_SQL_SERVER_ENV_VAR, WAREHOUSE_SQL_DATABASE_ENV_VAR
    if role == "warehouse-admin":
        raise ValueError(
            "warehouse-admin authentication remains an explicit database-url lane; "
            "normal Fabric user identity is never promoted to session-control authority"
        )
    raise ValueError(f"unsupported SQL runtime role {role!r}")


def runtime_sql_env_requirements(
    *,
    role: SqlRuntimeRole,
    database_url_env_var: str | None,
    environ: Mapping[str, str],
) -> tuple[tuple[str, str], ...]:
    """Return non-secret environment requirements for preflight.

    The returned values are purpose/env-var-name pairs only. Runtime values are never
    copied into retained plans or evidence.
    """

    mode = fabric_sql_auth_mode(environ)
    if role == "warehouse-admin" or mode == FABRIC_SQL_AUTH_MODE_DATABASE_URL:
        if database_url_env_var is None:
            raise ValueError(f"{role} SQL runtime requires a database URL env-var name")
        return ((f"{role} database URL", database_url_env_var),)

    server_env, database_env = _role_endpoint_env_vars(role)
    return (
        (f"{role} Fabric SQL server", server_env),
        (f"{role} Fabric SQL database", database_env),
    )


def _validate_server(value: str) -> str:
    server = value.strip()
    if not _SERVER_RE.fullmatch(server):
        raise ValueError(
            "Fabric SQL server must be a plain hostname with optional port 1433; "
            "URLs, credentials, paths, query strings and connection-string fragments are rejected"
        )
    if server.endswith(",1433") or server.endswith(":1433"):
        server = server[:-5]
    return server


def _validate_database(value: str) -> str:
    database = value.strip()
    if not database or len(database) > 256:
        raise ValueError("Fabric SQL database name must contain 1-256 characters")
    if any(char in database for char in (";", "\r", "\n", "\x00", "{", "}")):
        raise ValueError("Fabric SQL database name contains unsafe connection-string characters")
    return database


def _select_odbc_driver(pyodbc_module: Any) -> str:
    candidates: list[tuple[int, str]] = []
    for name in pyodbc_module.drivers():
        match = _DRIVER_RE.fullmatch(str(name))
        if match is None:
            continue
        version = int(match.group("version"))
        if version >= 18:
            candidates.append((version, str(name)))
    if not candidates:
        raise RuntimeError(
            "Microsoft ODBC Driver 18 or newer for SQL Server is required for Fabric SQL runtime"
        )
    return max(candidates)[1]


def _default_token_getter(audience: str) -> str:
    try:
        from notebookutils import credentials  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on Fabric Notebook runtime
        raise RuntimeError(
            "fabric-user SQL authentication requires Microsoft Fabric notebookutils.credentials"
        ) from exc
    token = credentials.getToken(audience)
    if not isinstance(token, str) or not token.strip():
        raise RuntimeError("Fabric Notebook did not return a usable SQL access token")
    return token.strip()


def _fabric_user_engine(
    *,
    server: str,
    database: str,
    token_getter: TokenGetter | None = None,
    pyodbc_module: Any | None = None,
) -> Engine:
    try:
        pyodbc = pyodbc_module
        if pyodbc is None:
            import pyodbc as imported_pyodbc  # type: ignore

            pyodbc = imported_pyodbc
    except Exception as exc:  # pragma: no cover - depends on Fabric Notebook runtime
        raise RuntimeError("fabric-user SQL authentication requires pyodbc") from exc

    driver = _select_odbc_driver(pyodbc)
    safe_server = _validate_server(server)
    safe_database = _validate_database(database)
    get_token = token_getter or _default_token_getter
    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={safe_server},1433;"
        f"DATABASE={safe_database};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )

    def creator():
        # A token is acquired per physical connection so SQLAlchemy pool replacement and
        # long-running Notebook sessions do not reuse an expired token during reconnect.
        token = get_token(FABRIC_SQL_TOKEN_AUDIENCE)
        if not isinstance(token, str) or not token.strip():
            raise RuntimeError("Fabric SQL token getter returned an empty token")
        token_bytes = token.strip().encode("utf-16-le")
        packed_token = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
        return pyodbc.connect(
            connection_string,
            attrs_before={SQL_COPT_SS_ACCESS_TOKEN: packed_token},
            autocommit=False,
        )

    return create_engine("mssql+pyodbc://", creator=creator, pool_pre_ping=True)


def create_runtime_sql_engine(
    *,
    role: SqlRuntimeRole,
    environ: Mapping[str, str],
    database_url_env_var: str | None,
    database_url_engine_factory: EngineFactory = create_engine,
    token_getter: TokenGetter | None = None,
    pyodbc_module: Any | None = None,
) -> Engine:
    """Create a SQLAlchemy engine from the selected runtime authentication lane."""

    mode = fabric_sql_auth_mode(environ)
    if role == "warehouse-admin" or mode == FABRIC_SQL_AUTH_MODE_DATABASE_URL:
        if database_url_env_var is None:
            raise ValueError(f"{role} SQL runtime requires a database URL env-var name")
        database_url = _nonempty(environ, database_url_env_var)
        if database_url is None:
            raise ValueError(f"runtime prerequisite {database_url_env_var} is missing")
        return database_url_engine_factory(database_url)

    server_env, database_env = _role_endpoint_env_vars(role)
    server = _nonempty(environ, server_env)
    database = _nonempty(environ, database_env)
    missing = [
        name
        for name, value in ((server_env, server), (database_env, database))
        if value is None
    ]
    if missing:
        raise ValueError("missing Fabric SQL runtime env vars=" + ",".join(missing))
    return _fabric_user_engine(
        server=server,
        database=database,
        token_getter=token_getter,
        pyodbc_module=pyodbc_module,
    )


__all__ = [
    "CONTROL_PLANE_SQL_DATABASE_ENV_VAR",
    "CONTROL_PLANE_SQL_SERVER_ENV_VAR",
    "FABRIC_SQL_AUTH_MODE_DATABASE_URL",
    "FABRIC_SQL_AUTH_MODE_ENV_VAR",
    "FABRIC_SQL_AUTH_MODE_USER",
    "FABRIC_SQL_TOKEN_AUDIENCE",
    "SQL_COPT_SS_ACCESS_TOKEN",
    "WAREHOUSE_SQL_DATABASE_ENV_VAR",
    "WAREHOUSE_SQL_SERVER_ENV_VAR",
    "create_runtime_sql_engine",
    "fabric_sql_auth_mode",
    "runtime_sql_env_requirements",
]
