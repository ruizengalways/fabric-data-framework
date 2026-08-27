from sqlalchemy import create_engine, inspect

from fabric_data_framework.control_plane import (
    CONTROL_PLANE_SCHEMA_VERSION,
    ENVIRONMENT_LOCAL_STATE_TABLES,
    PROMOTABLE_DEFINITION_TABLES,
    apply_baseline_schema,
    current_schema_version,
    table_names,
)


def test_baseline_schema_is_idempotent_and_versioned():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    assert current_schema_version(engine) == 0
    assert apply_baseline_schema(engine) == CONTROL_PLANE_SCHEMA_VERSION
    assert apply_baseline_schema(engine) == CONTROL_PLANE_SCHEMA_VERSION
    assert current_schema_version(engine) == CONTROL_PLANE_SCHEMA_VERSION

    actual = set(inspect(engine).get_table_names())
    assert set(table_names()) <= actual


def test_promotable_definition_rows_are_separate_from_environment_local_state():
    assert PROMOTABLE_DEFINITION_TABLES.isdisjoint(ENVIRONMENT_LOCAL_STATE_TABLES)
    assert "dataset" in PROMOTABLE_DEFINITION_TABLES
    assert "load_policy" in PROMOTABLE_DEFINITION_TABLES
    assert "watermark" in ENVIRONMENT_LOCAL_STATE_TABLES
    assert "runtime_override" in ENVIRONMENT_LOCAL_STATE_TABLES
    assert "pipeline_run" in ENVIRONMENT_LOCAL_STATE_TABLES
    assert "deployment_history" in ENVIRONMENT_LOCAL_STATE_TABLES
    assert PROMOTABLE_DEFINITION_TABLES | ENVIRONMENT_LOCAL_STATE_TABLES == table_names()
