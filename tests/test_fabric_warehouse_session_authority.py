from __future__ import annotations

from uuid import UUID

import pytest

from fabric_data_framework.recovery.fabric_warehouse_session_absence import (
    FabricWarehouseSessionBinding,
    SqlAlchemyFabricWarehouseSessionAuthority,
    capture_fabric_warehouse_session_binding,
)


CONNECTION_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


class FakeMappings:
    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        return self.row


class FakeResult:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return FakeMappings(self.row)


class FakeAdminConnection:
    def __init__(self, *, row=None):
        self.row = row
        self.executed = []
        self.driver_sql = []
        self.execution_options_seen = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, parameters=None):
        self.executed.append((str(statement), parameters))
        return FakeResult(self.row)

    def execution_options(self, **kwargs):
        self.execution_options_seen.append(kwargs)
        return self

    def exec_driver_sql(self, statement):
        self.driver_sql.append(statement)


class FakeEngine:
    def __init__(self, connections):
        self.connections = list(connections)
        self.connect_calls = 0

    def connect(self):
        connection = self.connections[self.connect_calls]
        self.connect_calls += 1
        return connection


class FakeTargetConnection:
    def __init__(self, row):
        self.row = row
        self.executed = []

    def execute(self, statement, parameters=None):
        self.executed.append((str(statement), parameters))
        return FakeResult(self.row)


def _binding():
    return FabricWarehouseSessionBinding(
        session_id=91,
        connection_id=CONNECTION_ID,
    )


def test_sqlalchemy_session_authority_observes_exact_connection_and_session():
    connection = FakeAdminConnection(
        row={
            "connection_id": str(CONNECTION_ID),
            "session_id": 91,
            "open_transaction_count": 2,
        }
    )
    authority = SqlAlchemyFabricWarehouseSessionAuthority(FakeEngine([connection]))

    state = authority.observe(_binding())

    assert state is not None
    assert state.session_id == 91
    assert state.connection_id == CONNECTION_ID
    assert state.open_transaction_count == 2
    sql, parameters = connection.executed[0]
    assert "sys.dm_exec_connections" in sql
    assert "sys.dm_exec_sessions" in sql
    assert "c.connection_id = :connection_id" in sql
    assert "s.session_id = :session_id" in sql
    assert parameters == {
        "connection_id": str(CONNECTION_ID),
        "session_id": 91,
    }


def test_sqlalchemy_session_authority_kill_is_autocommit_and_integer_only():
    connection = FakeAdminConnection()
    authority = SqlAlchemyFabricWarehouseSessionAuthority(FakeEngine([connection]))

    authority.terminate(_binding())

    assert connection.execution_options_seen == [{"isolation_level": "AUTOCOMMIT"}]
    assert connection.driver_sql == ["KILL 91"]


def test_capture_session_binding_fails_when_same_connection_identity_is_unavailable():
    connection = FakeTargetConnection(None)

    with pytest.raises(RuntimeError, match="session identity could not be captured"):
        capture_fabric_warehouse_session_binding(connection)

    sql, parameters = connection.executed[0]
    assert "sys.dm_exec_connections" in sql
    assert "@@SPID" in sql
    assert parameters is None
