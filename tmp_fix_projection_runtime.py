from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Use valid DESCRIBE HISTORY command syntax and explicit named-version extraction.
replace_once(
    "src/fabric_data_framework/adapters/fabric/current_projection.py",
    '''    def latest_history_version(self, table_reference: str) -> int:\n        relation = quote_spark_relation(table_reference)\n        value = _first_scalar(\n            self.spark.sql(\n                f"SELECT version FROM (DESCRIBE HISTORY {relation}) ORDER BY version DESC LIMIT 1"\n            ),\n            label="Delta history version",\n        )\n        try:\n            version = int(value)\n        except (TypeError, ValueError) as exc:\n            raise CurrentProjectionExecutionError(\n                f"invalid Delta history version: {value!r}"\n            ) from exc\n        if version < 0:\n            raise CurrentProjectionExecutionError("Delta history version cannot be negative")\n        return version\n''',
    '''    def latest_history_version(self, table_reference: str) -> int:\n        relation = quote_spark_relation(table_reference)\n        rows = self.spark.sql(f"DESCRIBE HISTORY {relation} LIMIT 1").collect()\n        if not rows:\n            raise CurrentProjectionExecutionError("Delta history returned no commits")\n        row = rows[0]\n        if hasattr(row, "asDict"):\n            value = row.asDict().get("version")\n        elif isinstance(row, dict):\n            value = row.get("version")\n        else:\n            try:\n                value = row[0]\n            except Exception as exc:  # pragma: no cover - provider row wrapper guard\n                raise CurrentProjectionExecutionError(\n                    "Delta history version could not be read"\n                ) from exc\n        try:\n            version = int(value)\n        except (TypeError, ValueError) as exc:\n            raise CurrentProjectionExecutionError(\n                f"invalid Delta history version: {value!r}"\n            ) from exc\n        if version < 0:\n            raise CurrentProjectionExecutionError("Delta history version cannot be negative")\n        return version\n''',
    "describe history syntax",
)

# Compare the two multisets through valid subqueries rather than parenthesized set operands.
replace_once(
    "src/fabric_data_framework/adapters/fabric/current_projection.py",
    '''            if _has_rows(\n                self.spark,\n                "SELECT 1 FROM (("\n                + actual_sql\n                + ") EXCEPT ALL ("\n                + expected_sql\n                + ")) UNION ALL (("\n                + expected_sql\n                + ") EXCEPT ALL ("\n                + actual_sql\n                + ")) LIMIT 1 /* fdf:verify */",\n            ):\n                raise CurrentProjectionExecutionError(\n                    "current projection target does not equal authoritative current history for affected keys"\n                )\n''',
    '''            extra_sql = (\n                "SELECT 1 FROM (" + actual_sql + " EXCEPT ALL " + expected_sql\n                + ") fdf_extra LIMIT 1 /* fdf:verify_extra */"\n            )\n            missing_sql = (\n                "SELECT 1 FROM (" + expected_sql + " EXCEPT ALL " + actual_sql\n                + ") fdf_missing LIMIT 1 /* fdf:verify_missing */"\n            )\n            if _has_rows(self.spark, extra_sql) or _has_rows(self.spark, missing_sql):\n                raise CurrentProjectionExecutionError(\n                    "current projection target does not equal authoritative current history for affected keys"\n                )\n''',
    "projection verification SQL",
)

# Terminal audit timestamps must not be constructed backwards by model defaults.
replace_once(
    "src/fabric_data_framework/execution/backends/fabric_spark.py",
    '''                retryable=retryable,\n                completed_at=completed,\n            )\n''',
    '''                retryable=retryable,\n                started_at=completed,\n                completed_at=completed,\n            )\n''',
    "terminal audit timestamp",
)

# SQLite strips timezone info on DateTime; normalize persisted event timestamps on read.
transition = Path("src/fabric_data_framework/control_plane/current_projection_transition.py")
text = transition.read_text(encoding="utf-8")
old = '''    return tuple(\n        CurrentProjectionTransitionEvent(\n            event_id=UUID(str(row["event_id"])),\n            transition_id=UUID(str(row["transition_id"])),\n            dataset_id=str(row["dataset_id"]),\n            from_mode=CurrentProjectionMode(str(row["from_mode"])),\n            to_mode=CurrentProjectionMode(str(row["to_mode"])),\n            status=ProjectionTransitionStatus(str(row["status"])),\n            actor=str(row["actor"]),\n            reason=str(row["reason"]),\n            ticket_reference=(\n                str(row["ticket_reference"])\n                if row["ticket_reference"] is not None\n                else None\n            ),\n            checkpoint_version_before=(\n                int(row["checkpoint_version_before"])\n                if row["checkpoint_version_before"] is not None\n                else None\n            ),\n            checkpoint_reset=bool(row["checkpoint_reset"]),\n            detail=str(row["detail"]) if row["detail"] is not None else None,\n            occurred_at=row["occurred_at"],\n        )\n        for row in rows\n    )\n'''
new = '''    events = []\n    for row in rows:\n        occurred_at = row["occurred_at"]\n        if not isinstance(occurred_at, datetime):\n            raise RuntimeError("persisted projection transition timestamp is invalid")\n        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:\n            occurred_at = occurred_at.replace(tzinfo=timezone.utc)\n        events.append(\n            CurrentProjectionTransitionEvent(\n                event_id=UUID(str(row["event_id"])),\n                transition_id=UUID(str(row["transition_id"])),\n                dataset_id=str(row["dataset_id"]),\n                from_mode=CurrentProjectionMode(str(row["from_mode"])),\n                to_mode=CurrentProjectionMode(str(row["to_mode"])),\n                status=ProjectionTransitionStatus(str(row["status"])),\n                actor=str(row["actor"]),\n                reason=str(row["reason"]),\n                ticket_reference=(\n                    str(row["ticket_reference"])\n                    if row["ticket_reference"] is not None\n                    else None\n                ),\n                checkpoint_version_before=(\n                    int(row["checkpoint_version_before"])\n                    if row["checkpoint_version_before"] is not None\n                    else None\n                ),\n                checkpoint_reset=bool(row["checkpoint_reset"]),\n                detail=str(row["detail"]) if row["detail"] is not None else None,\n                occurred_at=occurred_at,\n            )\n        )\n    return tuple(events)\n'''
if text.count(old) != 1:
    raise SystemExit("transition read normalization mismatch")
transition.write_text(text.replace(old, new, 1), encoding="utf-8")

lease = Path("src/fabric_data_framework/control_plane/dataset_lease_recovery.py")
text = lease.read_text(encoding="utf-8")
old = '''    return tuple(\n        DatasetLeaseRecoveryEvent(\n            event_id=UUID(str(row["event_id"])),\n            dataset_id=str(row["dataset_id"]),\n            lease_owner=str(row["lease_owner"]),\n            dataset_run_id=UUID(str(row["dataset_run_id"])),\n            lease_version=int(row["lease_version"]),\n            recovered_by=str(row["recovered_by"]),\n            reason=str(row["reason"]),\n            proof_reference=str(row["proof_reference"]),\n            review_deadline=row["review_deadline"],\n            recovered_at=row["recovered_at"],\n        )\n        for row in rows\n    )\n'''
new = '''    events = []\n    for row in rows:\n        review_deadline = row["review_deadline"]\n        recovered_at = row["recovered_at"]\n        if not isinstance(review_deadline, datetime) or not isinstance(recovered_at, datetime):\n            raise RuntimeError("persisted dataset lease recovery timestamps are invalid")\n        if review_deadline.tzinfo is None or review_deadline.utcoffset() is None:\n            review_deadline = review_deadline.replace(tzinfo=timezone.utc)\n        if recovered_at.tzinfo is None or recovered_at.utcoffset() is None:\n            recovered_at = recovered_at.replace(tzinfo=timezone.utc)\n        events.append(\n            DatasetLeaseRecoveryEvent(\n                event_id=UUID(str(row["event_id"])),\n                dataset_id=str(row["dataset_id"]),\n                lease_owner=str(row["lease_owner"]),\n                dataset_run_id=UUID(str(row["dataset_run_id"])),\n                lease_version=int(row["lease_version"]),\n                recovered_by=str(row["recovered_by"]),\n                reason=str(row["reason"]),\n                proof_reference=str(row["proof_reference"]),\n                review_deadline=review_deadline,\n                recovered_at=recovered_at,\n            )\n        )\n    return tuple(events)\n'''
if text.count(old) != 1:
    raise SystemExit("lease recovery read normalization mismatch")
lease.write_text(text.replace(old, new, 1), encoding="utf-8")

# Remove obvious unused test imports before static checks.
replace_once(
    "tests/test_current_projection_production_runtime.py",
    "from sqlalchemy import create_engine, delete, select\n",
    "from sqlalchemy import create_engine, delete\n",
    "unused select import",
)
replace_once(
    "tests/test_current_projection_production_runtime.py",
    "    current_projection_transition_event,\n",
    "",
    "unused transition table import",
)
