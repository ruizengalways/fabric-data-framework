from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement target, found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


sql_path = "src/fabric_data_framework/control_plane/sqlalchemy_repository.py"
replace_once(
    sql_path,
    "from sqlalchemy import Engine, select\n",
    "from sqlalchemy import Engine, select\nfrom sqlalchemy.exc import IntegrityError\n",
)
replace_once(
    sql_path,
    "from fabric_data_framework.contracts.runtime import WatermarkPosition\n",
    "from fabric_data_framework.contracts.runtime import (\n"
    "    WatermarkConflictError,\n"
    "    WatermarkPosition,\n"
    "    WatermarkState,\n"
    "    compare_watermark_positions,\n"
    ")\n"
    "from fabric_data_framework.contracts.typed_values import (\n"
    "    TypedValueError,\n"
    "    decode_legacy_or_typed_scalar,\n"
    "    encode_typed_value,\n"
    ")\n",
)
replace_once(
    sql_path,
    '''def _assert_semantic_identity(\n    existing: dict[str, object],\n    expected: dict[str, object],\n    *,\n    label: str,\n) -> None:\n    changed = [key for key, value in expected.items() if existing[key] != value]\n    if changed:\n        raise ValueError(\n            f"{label} semantic identity cannot change: {', '.join(sorted(changed))}"\n        )\n\n\n''',
    '''def _assert_semantic_identity(\n    existing: dict[str, object],\n    expected: dict[str, object],\n    *,\n    label: str,\n) -> None:\n    changed = [key for key, value in expected.items() if existing[key] != value]\n    if changed:\n        raise ValueError(\n            f"{label} semantic identity cannot change: {', '.join(sorted(changed))}"\n        )\n\n\ndef _decode_watermark_tie_breaker(payload: object) -> tuple[str | int | float, ...]:\n    if payload is None:\n        return ()\n    raw_items = payload if isinstance(payload, (list, tuple)) else [payload]\n    decoded: list[str | int | float] = []\n    for item in raw_items:\n        value = decode_legacy_or_typed_scalar(item)\n        if type(value) is bool or type(value) not in {str, int, float}:\n            raise TypedValueError(\n                "persisted watermark tie-breaker contains an unsupported value type"\n            )\n        decoded.append(value)\n    return tuple(decoded)\n\n\ndef _watermark_state_from_row(row: object | None) -> WatermarkState:\n    if row is None:\n        return WatermarkState()\n    mapping = dict(row)\n    try:\n        value = decode_legacy_or_typed_scalar(mapping["committed_value"])\n        tie_breaker = _decode_watermark_tie_breaker(mapping["committed_tie_breaker"])\n        position = WatermarkPosition(value=value, tie_breaker=tie_breaker)\n        return WatermarkState(position=position, version=int(mapping["version"]))\n    except (KeyError, TypeError, ValueError, TypedValueError) as exc:\n        raise RuntimeError("persisted watermark state is malformed or unsupported") from exc\n\n\n''',
)
old_watermark = '''    def get_watermark(self, dataset_id: str) -> WatermarkPosition | None:\n        with self.engine.connect() as connection:\n            row = connection.execute(\n                select(watermark).where(watermark.c.dataset_id == dataset_id)\n            ).mappings().first()\n        if row is None:\n            return None\n        return WatermarkPosition(\n            value=row["committed_value"],\n            tie_breaker=tuple(row["committed_tie_breaker"] or ()),\n        )\n\n    def commit_watermark(self, dataset_id: str, position: WatermarkPosition) -> None:\n        # Compatibility method for the older repository Protocol. Stateful execution\n        # should use the dedicated gated/CAS state primitives for commit decisions.\n        self._deployed_dataset_row(dataset_id)\n        now = _utcnow()\n        with self.engine.begin() as connection:\n            existing = connection.execute(\n                select(watermark).where(watermark.c.dataset_id == dataset_id)\n            ).mappings().first()\n            if existing is None:\n                connection.execute(\n                    watermark.insert().values(\n                        dataset_id=dataset_id,\n                        committed_value=position.value,\n                        committed_tie_breaker=list(position.tie_breaker),\n                        committed_dataset_run_id=None,\n                        version=1,\n                        created_at=now,\n                        updated_at=None,\n                    )\n                )\n                return\n            connection.execute(\n                watermark.update()\n                .where(watermark.c.dataset_id == dataset_id)\n                .values(\n                    committed_value=position.value,\n                    committed_tie_breaker=list(position.tie_breaker),\n                    version=int(existing["version"]) + 1,\n                    updated_at=now,\n                )\n            )\n\n'''
new_watermark = '''    def get_watermark_state(self, dataset_id: str) -> WatermarkState:\n        self._deployed_dataset_row(dataset_id)\n        with self.engine.connect() as connection:\n            row = connection.execute(\n                select(watermark).where(watermark.c.dataset_id == dataset_id)\n            ).mappings().first()\n        return _watermark_state_from_row(row)\n\n    def get_watermark(self, dataset_id: str) -> WatermarkPosition | None:\n        return self.get_watermark_state(dataset_id).position\n\n    def commit_watermark(\n        self,\n        dataset_id: str,\n        position: WatermarkPosition,\n        *,\n        expected_version: int,\n    ) -> WatermarkState:\n        if position.value is None:\n            raise ValueError("committed watermark value cannot be null")\n        if expected_version < 0:\n            raise ValueError("expected watermark version cannot be negative")\n        self._deployed_dataset_row(dataset_id)\n        now = _utcnow()\n        encoded_value = encode_typed_value(position.value)\n        encoded_tie_breaker = [encode_typed_value(item) for item in position.tie_breaker]\n\n        try:\n            with self.engine.begin() as connection:\n                existing = connection.execute(\n                    select(watermark).where(watermark.c.dataset_id == dataset_id)\n                ).mappings().first()\n                current = _watermark_state_from_row(existing)\n                if current.version != expected_version:\n                    raise WatermarkConflictError(\n                        f"stale watermark writer for {dataset_id}: "\n                        f"expected_version={expected_version}, current_version={current.version}"\n                    )\n                if current.position is not None:\n                    ordering = compare_watermark_positions(position, current.position)\n                    if ordering < 0:\n                        raise ValueError("committed watermark cannot move backwards")\n                    if ordering == 0:\n                        return current\n\n                next_state = WatermarkState(\n                    position=position,\n                    version=expected_version + 1,\n                )\n                if existing is None:\n                    connection.execute(\n                        watermark.insert().values(\n                            dataset_id=dataset_id,\n                            committed_value=encoded_value,\n                            committed_tie_breaker=encoded_tie_breaker,\n                            committed_dataset_run_id=None,\n                            version=next_state.version,\n                            created_at=now,\n                            updated_at=None,\n                        )\n                    )\n                    return next_state\n\n                result = connection.execute(\n                    watermark.update()\n                    .where(watermark.c.dataset_id == dataset_id)\n                    .where(watermark.c.version == expected_version)\n                    .values(\n                        committed_value=encoded_value,\n                        committed_tie_breaker=encoded_tie_breaker,\n                        version=next_state.version,\n                        updated_at=now,\n                    )\n                )\n                if result.rowcount != 1:\n                    raise WatermarkConflictError(\n                        f"watermark compare-and-set lost a concurrent race for {dataset_id}"\n                    )\n                return next_state\n        except IntegrityError as exc:\n            raise WatermarkConflictError(\n                f"watermark compare-and-set lost a concurrent insert race for {dataset_id}"\n            ) from exc\n\n'''
replace_once(sql_path, old_watermark, new_watermark)

execution_path = "src/fabric_data_framework/execution/watermark_scd2.py"
replace_once(
    execution_path,
    "from fabric_data_framework.contracts.runtime import StateCommitGate, WatermarkPosition, WatermarkTransition\n",
    "from fabric_data_framework.contracts.runtime import (\n"
    "    StateCommitGate,\n"
    "    WatermarkPosition,\n"
    "    WatermarkTransition,\n"
    "    compare_watermark_positions,\n"
    ")\n",
)
replace_once(
    execution_path,
    "    before = repository.get_watermark(dataset_id)\n\n    capture: WatermarkBatch = plan_watermark_batch(source_rows, config.load.watermark, before)\n",
    "    watermark_state = repository.get_watermark_state(dataset_id)\n"
    "    before = watermark_state.position\n\n"
    "    capture: WatermarkBatch = plan_watermark_batch(source_rows, config.load.watermark, before)\n",
)
replace_once(
    execution_path,
    '''        target.replace(proposed.rows)\n        if capture.after is not None:\n            WatermarkTransition(before=before, after=capture.after, gate=gate)\n            repository.commit_watermark(dataset_id, capture.after)\n        status = DatasetStatus.SUCCEEDED\n''',
    '''        target.replace(proposed.rows)\n        if capture.after is not None:\n            WatermarkTransition(before=before, after=capture.after, gate=gate)\n            changed = before is None or compare_watermark_positions(capture.after, before) > 0\n            if changed:\n                repository.commit_watermark(\n                    dataset_id,\n                    capture.after,\n                    expected_version=watermark_state.version,\n                )\n        status = DatasetStatus.SUCCEEDED\n''',
)
