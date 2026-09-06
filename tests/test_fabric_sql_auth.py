from __future__ import annotations

import pytest

from fabric_data_framework.adapters.fabric.sql_auth import (
    CONTROL_PLANE_DATABASE_URL_ENV_VAR,
    CONTROL_PLANE_SQL_DATABASE_ENV_VAR,
    CONTROL_PLANE_SQL_SERVER_ENV_VAR,
    FABRIC_SQL_AUTH_MODE_DATABASE_URL,
    FABRIC_SQL_AUTH_MODE_ENV_VAR,
    FABRIC_SQL_AUTH_MODE_USER,
    WAREHOUSE_DATABASE_URL_ENV_VAR,
    WAREHOUSE_SQL_DATABASE_ENV_VAR,
    WAREHOUSE_SQL_SERVER_ENV_VAR,
    fabric_sql_auth_mode,
    fabric_user_sqlalchemy_url,
    prepare_fabric_user_sql_runtime,
    runtime_sql_env_requirements,
)


class _FakePyodbc:
    @staticmethod
    def drivers():
        return [
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 18 for SQL Server",
        ]


def test_database_url_mode_remains_default_for_backward_compatibility():
    environ = {CONTROL_PLANE_DATABASE_URL_ENV_VAR: "sqlite+pysqlite:///:memory:"}
    assert fabric_sql_auth_mode(environ) == FABRIC_SQL_AUTH_MODE_DATABASE_URL
    assert runtime_sql_env_requirements(
        role="control-plane",
        database_url_env_var=CONTROL_PLANE_DATABASE_URL_ENV_VAR,
        environ=environ,
    ) == (("control-plane database URL", CONTROL_PLANE_DATABASE_URL_ENV_VAR),)


def test_fabric_user_preflight_requires_only_non_secret_endpoint_identity():
    environ = {FABRIC_SQL_AUTH_MODE_ENV_VAR: FABRIC_SQL_AUTH_MODE_USER}
    assert runtime_sql_env_requirements(
        role="control-plane",
        database_url_env_var=CONTROL_PLANE_DATABASE_URL_ENV_VAR,
        environ=environ,
    ) == (
        ("control-plane Fabric SQL server", CONTROL_PLANE_SQL_SERVER_ENV_VAR),
        ("control-plane Fabric SQL database", CONTROL_PLANE_SQL_DATABASE_ENV_VAR),
    )
    assert runtime_sql_env_requirements(
        role="warehouse",
        database_url_env_var=WAREHOUSE_DATABASE_URL_ENV_VAR,
        environ=environ,
    ) == (
        ("warehouse Fabric SQL server", WAREHOUSE_SQL_SERVER_ENV_VAR),
        ("warehouse Fabric SQL database", WAREHOUSE_SQL_DATABASE_ENV_VAR),
    )


def test_prepare_fabric_user_runtime_synthesizes_non_secret_sqlalchemy_urls():
    runtime = prepare_fabric_user_sql_runtime(
        {
            CONTROL_PLANE_SQL_SERVER_ENV_VAR: "control.database.fabric.microsoft.com",
            CONTROL_PLANE_SQL_DATABASE_ENV_VAR: "framework_control",
            WAREHOUSE_SQL_SERVER_ENV_VAR: "warehouse.datawarehouse.fabric.microsoft.com",
            WAREHOUSE_SQL_DATABASE_ENV_VAR: "framework_cert",
        },
        pyodbc_module=_FakePyodbc,
    )

    assert runtime[FABRIC_SQL_AUTH_MODE_ENV_VAR] == FABRIC_SQL_AUTH_MODE_USER
    for env_var in (CONTROL_PLANE_DATABASE_URL_ENV_VAR, WAREHOUSE_DATABASE_URL_ENV_VAR):
        value = runtime[env_var]
        assert value.startswith("mssql+pyodbc://")
        assert "ODBC+Driver+18+for+SQL+Server" in value
        assert "FabricDataFrameworkFabricUser" in value
        assert "token" not in value.lower()
        assert "password" not in value.lower()
        assert "@" in value


def test_fabric_user_url_rejects_connection_string_injection():
    with pytest.raises(ValueError, match="plain hostname"):
        fabric_user_sqlalchemy_url(
            server="server.database.fabric.microsoft.com;UID=attacker",
            database="db",
            pyodbc_module=_FakePyodbc,
        )
    with pytest.raises(ValueError, match="unsafe"):
        fabric_user_sqlalchemy_url(
            server="server.database.fabric.microsoft.com",
            database="db;TrustServerCertificate=yes",
            pyodbc_module=_FakePyodbc,
        )


def test_warehouse_admin_never_inherits_normal_fabric_user_authority():
    with pytest.raises(ValueError, match="database URL env-var name"):
        runtime_sql_env_requirements(
            role="warehouse-admin",
            database_url_env_var=None,
            environ={FABRIC_SQL_AUTH_MODE_ENV_VAR: FABRIC_SQL_AUTH_MODE_USER},
        )


def test_unknown_auth_mode_fails_closed():
    with pytest.raises(ValueError, match="unsupported FABRIC_SQL_AUTH_MODE"):
        fabric_sql_auth_mode({FABRIC_SQL_AUTH_MODE_ENV_VAR: "magic"})
