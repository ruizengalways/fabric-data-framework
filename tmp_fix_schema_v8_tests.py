from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "tests/test_append_metadata.py",
    "assert apply_baseline_schema(engine) == CONTROL_PLANE_SCHEMA_VERSION == 7",
    "assert apply_baseline_schema(engine) == CONTROL_PLANE_SCHEMA_VERSION == 8",
    "append metadata schema version",
)
replace_once(
    "tests/test_control_plane_certification.py",
    "assert report.schema_version == CONTROL_PLANE_SCHEMA_VERSION == 7",
    "assert report.schema_version == CONTROL_PLANE_SCHEMA_VERSION == 8",
    "control plane certification schema version",
)
replace_once(
    "tests/test_control_plane_certification_cli.py",
    'assert report["schema_version"] == CONTROL_PLANE_SCHEMA_VERSION == 7',
    'assert report["schema_version"] == CONTROL_PLANE_SCHEMA_VERSION == 8',
    "control plane certification CLI schema version",
)
replace_once(
    "tests/test_target_operation_journal.py",
    "assert CONTROL_PLANE_SCHEMA_VERSION == 7",
    "assert CONTROL_PLANE_SCHEMA_VERSION == 8",
    "target operation schema version",
)

projection = Path("tests/test_current_projection.py")
text = projection.read_text(encoding="utf-8")
old = "assert CONTROL_PLANE_SCHEMA_VERSION == 7"
if text.count(old) != 1:
    raise SystemExit(f"current projection schema version: expected 1 match, found {text.count(old)}")
text = text.replace(old, "assert CONTROL_PLANE_SCHEMA_VERSION == 8", 1)
text = text.replace(
    "def test_control_plane_v6_to_v7_adds_projection_definition_without_resetting_runtime(\n",
    "def test_control_plane_v6_to_latest_adds_projection_definition_without_resetting_runtime(\n",
    1,
)
old_delete = '''            schema_migration_history.delete().where(\n                schema_migration_history.c.version == 7\n            )\n'''
new_delete = '''            schema_migration_history.delete().where(\n                schema_migration_history.c.version >= 7\n            )\n'''
if text.count(old_delete) != 1:
    raise SystemExit("current projection migration marker reset mismatch")
text = text.replace(old_delete, new_delete, 1)
if text.count("    assert apply_baseline_schema(engine) == 7\n") != 1:
    raise SystemExit("current projection migration result assertion mismatch")
text = text.replace(
    "    assert apply_baseline_schema(engine) == 7\n",
    "    assert apply_baseline_schema(engine) == 8\n",
    1,
)
if text.count("    assert versions == list(range(1, 8))\n") != 1:
    raise SystemExit("current projection migration history assertion mismatch")
text = text.replace(
    "    assert versions == list(range(1, 8))\n",
    "    assert versions == list(range(1, 9))\n",
    1,
)
projection.write_text(text, encoding="utf-8")

# Guard against leaving stale explicit latest-version expectations behind.
stale = []
for path in Path("tests").glob("test_*.py"):
    body = path.read_text(encoding="utf-8")
    if "CONTROL_PLANE_SCHEMA_VERSION == 7" in body:
        stale.append(str(path))
if stale:
    raise SystemExit("stale schema-v7 expectations remain: " + ", ".join(stale))
