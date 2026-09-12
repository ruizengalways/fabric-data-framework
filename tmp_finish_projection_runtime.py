from pathlib import Path
import re

ROOT = Path('.')

def replace_once(path, old, new, label):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 match, found {count}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

schema = ROOT / 'src/fabric_data_framework/control_plane/schema.py'
text = schema.read_text(encoding='utf-8')
text = text.replace('CONTROL_PLANE_SCHEMA_VERSION = 7', 'CONTROL_PLANE_SCHEMA_VERSION = 8', 1)
text = text.replace(
    '    (7, "current_projection_semantics"),\n)',
    '    (7, "current_projection_semantics"),\n    (8, "projection_runtime_recovery_and_transition_governance"),\n)',
    1,
)
lease_block = '''dataset_lease = Table(\n    "dataset_lease",\n    metadata,\n    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),\n    Column("lease_owner", String(255), nullable=False),\n    Column("dataset_run_id", String(36), nullable=False),\n    Column("lease_version", Integer, nullable=False),\n    Column("acquired_at", DateTime(timezone=True), nullable=False),\n    Column("expires_at", DateTime(timezone=True), nullable=False),\n)\n'''
extra = lease_block + '''\ndataset_lease_recovery_event = Table(\n    "dataset_lease_recovery_event",\n    metadata,\n    Column("event_id", String(36), primary_key=True),\n    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), nullable=False),\n    Column("lease_owner", String(255), nullable=False),\n    Column("dataset_run_id", String(36), nullable=False),\n    Column("lease_version", Integer, nullable=False),\n    Column("recovered_by", String(255), nullable=False),\n    Column("reason", Text, nullable=False),\n    Column("proof_reference", String(2048), nullable=False),\n    Column("review_deadline", DateTime(timezone=True), nullable=False),\n    Column("recovered_at", DateTime(timezone=True), nullable=False),\n)\n\ncurrent_projection_transition_event = Table(\n    "current_projection_transition_event",\n    metadata,\n    Column("event_id", String(36), primary_key=True),\n    Column("transition_id", String(36), nullable=False),\n    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), nullable=False),\n    Column("from_mode", String(64), nullable=False),\n    Column("to_mode", String(64), nullable=False),\n    Column("status", String(32), nullable=False),\n    Column("actor", String(255), nullable=False),\n    Column("reason", Text, nullable=False),\n    Column("ticket_reference", String(1024), nullable=True),\n    Column("checkpoint_version_before", Integer, nullable=True),\n    Column("checkpoint_reset", Boolean, nullable=False),\n    Column("detail", Text, nullable=True),\n    Column("occurred_at", DateTime(timezone=True), nullable=False),\n)\n'''
if text.count(lease_block) != 1:
    raise SystemExit('dataset lease block mismatch')
text = text.replace(lease_block, extra, 1)
text = text.replace(
    '        "dataset_lease",\n        "pipeline_run",',
    '        "dataset_lease",\n        "dataset_lease_recovery_event",\n        "current_projection_transition_event",\n        "pipeline_run",',
    1,
)
old_migration_tail = '''    if version == 5:\n        _add_column_if_missing(connection, pipeline_run, "error_code")\n        _add_column_if_missing(connection, pipeline_run, "error_message")\n\n\ndef apply_baseline_schema(engine: Engine) -> int:\n    """Idempotently create additive schema and execute/record missing migrations."""\n\n    metadata.create_all(engine, checkfirst=True)\n    current = current_schema_version(engine)\n    pending = [item for item in CONTROL_PLANE_MIGRATIONS if item[0] > current]\n    if pending:\n        now = datetime.now(timezone.utc)\n        with engine.begin() as connection:\n            for version, name in pending:\n                _apply_migration(connection, version)\n                connection.execute(\n                    schema_migration_history.insert().values(\n                        version=version,\n                        name=name,\n                        applied_at=now,\n                    )\n                )\n    return CONTROL_PLANE_SCHEMA_VERSION\n'''
new_migration_tail = '''    if version == 5:\n        _add_column_if_missing(connection, pipeline_run, "error_code")\n        _add_column_if_missing(connection, pipeline_run, "error_message")\n        return\n\n    if version == 8:\n        # v7 was already released with current-projection semantics. Durable lease\n        # recovery/transition tables are therefore an explicit additive v8 contract.\n        dataset_lease.create(connection, checkfirst=True)\n        dataset_lease_recovery_event.create(connection, checkfirst=True)\n        current_projection_transition_event.create(connection, checkfirst=True)\n\n\ndef _assert_latest_schema_shape(engine: Engine) -> None:\n    inspector = inspect(engine)\n    actual = set(inspector.get_table_names())\n    missing = set(metadata.tables) - actual\n    if missing:\n        raise RuntimeError(\n            "Control Plane schema version claims latest but required tables are missing: "\n            + ", ".join(sorted(missing))\n        )\n\n\ndef apply_baseline_schema(engine: Engine) -> int:\n    """Create/upgrade the additive schema while preserving migration-version meaning.\n\n    Fresh databases are created at the latest shape and receive the full migration\n    history. Legacy pre-v7 databases retain the historical create-all upgrade behavior.\n    From v7 onward, new physical state is introduced only by explicit migrations; a\n    database claiming the latest version but missing tables fails closed.\n    """\n\n    inspector = inspect(engine)\n    if not inspector.has_table(schema_migration_history.name):\n        metadata.create_all(engine, checkfirst=True)\n        now = datetime.now(timezone.utc)\n        with engine.begin() as connection:\n            for version, name in CONTROL_PLANE_MIGRATIONS:\n                connection.execute(\n                    schema_migration_history.insert().values(\n                        version=version, name=name, applied_at=now\n                    )\n                )\n        _assert_latest_schema_shape(engine)\n        return CONTROL_PLANE_SCHEMA_VERSION\n\n    current = current_schema_version(engine)\n    if current > CONTROL_PLANE_SCHEMA_VERSION:\n        raise RuntimeError(\n            f"Control Plane schema version {current} is newer than supported "\n            f"{CONTROL_PLANE_SCHEMA_VERSION}"\n        )\n\n    # Historical migrations 1-6 relied on create_all before individual migration\n    # markers. Preserve that path only for genuinely old installations.\n    if current < 7:\n        metadata.create_all(engine, checkfirst=True)\n\n    pending = [item for item in CONTROL_PLANE_MIGRATIONS if item[0] > current]\n    if pending:\n        now = datetime.now(timezone.utc)\n        with engine.begin() as connection:\n            for version, name in pending:\n                _apply_migration(connection, version)\n                connection.execute(\n                    schema_migration_history.insert().values(\n                        version=version,\n                        name=name,\n                        applied_at=now,\n                    )\n                )\n    _assert_latest_schema_shape(engine)\n    return CONTROL_PLANE_SCHEMA_VERSION\n'''
if text.count(old_migration_tail) != 1:
    raise SystemExit('migration function block mismatch')
text = text.replace(old_migration_tail, new_migration_tail, 1)
text = text.replace(
    '    "current_projection_policy",\n    "dataset_lease",',
    '    "current_projection_policy",\n    "current_projection_transition_event",\n    "dataset_lease",\n    "dataset_lease_recovery_event",',
    1,
)
schema.write_text(text, encoding='utf-8')

# Projection schemas must carry the key used by distributed MERGE/deletes.
replace_once(
    'src/fabric_data_framework/deployment/current_projection.py',
    '''            projection_fields = {field.name: field for field in config.schema_contract.fields}\n            unknown = sorted(set(projection_fields) - set(history_fields))\n''',
    '''            projection_fields = {field.name: field for field in config.schema_contract.fields}\n            missing_keys = sorted(set(config.load.business_key) - set(projection_fields))\n            if missing_keys:\n                raise ValueError(\n                    f"current projection {config.dataset_id!r} schema must include business key fields: "\n                    + ", ".join(missing_keys)\n                )\n            unknown = sorted(set(projection_fields) - set(history_fields))\n''',
    'projection business key schema validation',
)
