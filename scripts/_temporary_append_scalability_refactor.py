from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/fabric_data_framework"


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _ensure_import(text: str, import_line: str) -> str:
    if import_line in text:
        return text
    future = "from __future__ import annotations\n"
    if future in text:
        return text.replace(future, future + "\n" + import_line + "\n", 1)
    match = re.match(r'(?s)(""".*?"""\n)', text)
    if match:
        return text[: match.end()] + "\n" + import_line + "\n" + text[match.end() :]
    return import_line + "\n" + text


def _remove_imported_name(text: str, module_pattern: str, name: str) -> str:
    multiline = re.compile(
        rf"from (?P<module>{module_pattern}) import \((?P<body>.*?)\)\n",
        re.S,
    )

    def replace_multiline(match: re.Match[str]) -> str:
        lines = match.group("body").splitlines()
        kept = [
            line
            for line in lines
            if line.strip().rstrip(",") != name
        ]
        if not any(line.strip() for line in kept):
            return ""
        return f"from {match.group('module')} import (" + "\n".join(kept) + ")\n"

    text = multiline.sub(replace_multiline, text)
    single = re.compile(rf"from (?P<module>{module_pattern}) import (?P<body>[^\n]+)\n")

    def replace_single(match: re.Match[str]) -> str:
        names = [part.strip() for part in match.group("body").split(",")]
        kept = [part for part in names if part != name]
        if len(kept) == len(names):
            return match.group(0)
        if not kept:
            return ""
        return f"from {match.group('module')} import {', '.join(kept)}\n"

    return single.sub(replace_single, text)


def _migrate_hash_owner() -> None:
    config_path = SRC / "metadata/config.py"
    config = config_path.read_text(encoding="utf-8")
    canonical_block = '''\n\ndef canonical_hash(payload: Any) -> str:\n    encoded = json.dumps(\n        payload,\n        sort_keys=True,\n        separators=(",", ":"),\n        ensure_ascii=False,\n        default=str,\n    ).encode("utf-8")\n    return hashlib.sha256(encoded).hexdigest()\n'''
    if canonical_block not in config:
        raise SystemExit("metadata canonical_hash definition anchor missing")
    config = config.replace(canonical_block, "", 1)
    _write(config_path, config)

    for path in ROOT.rglob("*.py"):
        if ".git" in path.parts or path == SRC / "contracts/hashing.py":
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        text = _remove_imported_name(
            text,
            r"(?:fabric_data_framework\.)?metadata\.config|(?:\.\.?)+metadata\.config",
            "canonical_hash",
        )
        if "canonical_hash(" in text and "def canonical_hash(" not in text:
            text = _ensure_import(
                text,
                "from fabric_data_framework.contracts.hashing import canonical_hash",
            )
        if text != original:
            _write(path, text)

    schema_path = SRC / "contracts/schema.py"
    schema = schema_path.read_text(encoding="utf-8")
    old_schema_hash = '''        encoded = json.dumps(\n            self.canonical_definition(),\n            sort_keys=True,\n            separators=(",", ":"),\n            ensure_ascii=False,\n        ).encode("utf-8")\n        return hashlib.sha256(encoded).hexdigest()'''
    if old_schema_hash not in schema:
        raise SystemExit("schema fingerprint anchor missing")
    schema = schema.replace(
        old_schema_hash,
        "        return canonical_hash(self.canonical_definition())",
        1,
    )
    schema = _ensure_import(
        schema,
        "from fabric_data_framework.contracts.hashing import canonical_hash",
    )
    _write(schema_path, schema)

    impact_path = SRC / "contracts/rebuild_impact.py"
    impact = impact_path.read_text(encoding="utf-8")
    old_impact_hash = '''        payload = self.model_dump(mode="json")\n        encoded = json.dumps(\n            payload,\n            sort_keys=True,\n            separators=(",", ":"),\n            ensure_ascii=False,\n        ).encode("utf-8")\n        return hashlib.sha256(encoded).hexdigest()'''
    if old_impact_hash not in impact:
        raise SystemExit("rebuild impact hash anchor missing")
    impact = impact.replace(
        old_impact_hash,
        '        return canonical_hash(self.model_dump(mode="json"))',
        1,
    )
    impact = _ensure_import(
        impact,
        "from fabric_data_framework.contracts.hashing import canonical_hash",
    )
    _write(impact_path, impact)


def _migrate_temporal_owner() -> None:
    local_now = re.compile(
        r"\n\ndef _utcnow\(\) -> datetime:\n    return datetime\.now\(timezone\.utc\)\n"
    )
    local_aware = re.compile(
        r"\n\ndef _require_aware\(value: datetime, field_name: str\) -> None:\n"
        r"    if value\.tzinfo is None or value\.utcoffset\(\) is None:\n"
        r"        raise ValueError\(f\"\{field_name\} must be timezone-aware\"\)\n"
    )
    public_cert_now = re.compile(
        r"\n\ndef utcnow\(\) -> datetime:\n    return datetime\.now\(timezone\.utc\)\n"
    )

    cert_models = SRC / "certification/models.py"
    models_text = cert_models.read_text(encoding="utf-8")
    models_text, count = public_cert_now.subn("", models_text, count=1)
    if count != 1:
        raise SystemExit("certification utcnow anchor missing")
    models_text = models_text.replace('    "utcnow",\n', "")
    _write(cert_models, models_text)

    for path in ROOT.rglob("*.py"):
        if ".git" in path.parts or path == SRC / "contracts/temporal.py":
            continue
        text = path.read_text(encoding="utf-8")
        original = text

        if "utcnow" in text:
            text = _remove_imported_name(
                text,
                r"fabric_data_framework\.certification\.models|\.models",
                "utcnow",
            )
            text = re.sub(r"(?<![A-Za-z0-9_])utcnow\(", "utc_now(", text)

        text = local_now.sub("", text)
        text = text.replace("_utcnow(", "utc_now(")
        text = local_aware.sub("", text)
        text = text.replace("_require_aware(", "require_aware_datetime(")
        text = text.replace("datetime.now(timezone.utc)", "utc_now()")

        needs_now = "utc_now(" in text
        needs_aware = "require_aware_datetime(" in text
        if needs_now or needs_aware:
            names = []
            if needs_aware:
                names.append("require_aware_datetime")
            if needs_now:
                names.append("utc_now")
            text = _ensure_import(
                text,
                "from fabric_data_framework.contracts.temporal import " + ", ".join(names),
            )

        if text != original:
            _write(path, text)


def _refactor_append_reference() -> None:
    path = SRC / "apply/append.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '"""Append-once apply semantics with explicit immutable record identity.\n',
        '"""Reference APPEND semantics with explicit immutable record identity.\n',
        1,
    )
    text = text.replace(
        'source-controlled identity so retries/backfills/replays can distinguish an exact\nre-observation from a conflicting reuse of an already-published identity.\n"""',
        'source-controlled identity so retries/backfills/replays can distinguish an exact\nre-observation from a conflicting reuse of an already-published identity.\n\nThis module is the deterministic in-memory semantic oracle used by tests/reference\nexecution. Production Fabric APPEND must use the distributed Spark/Delta adapter and\nmust never materialize the complete target table in Python.\n"""',
        1,
    )
    text = text.replace(
        "from fabric_data_framework.contracts.hashing import canonical_hash\n",
        "",
    )
    text = _ensure_import(
        text,
        "from fabric_data_framework.contracts.append import (\n"
        "    APPEND_IDENTITY_HASH,\n"
        "    APPEND_PAYLOAD_HASH,\n"
        "    RESERVED_APPEND_FIELDS,\n"
        "    append_identity_fingerprint,\n"
        "    append_payload_fingerprint,\n"
        "    business_payload,\n"
        ")",
    )
    constants = '''\n\nAPPEND_IDENTITY_HASH = "_framework_append_identity_hash"\nAPPEND_PAYLOAD_HASH = "_framework_append_payload_hash"\n_RESERVED_APPEND_FIELDS = frozenset({APPEND_IDENTITY_HASH, APPEND_PAYLOAD_HASH})\n'''
    if constants not in text:
        raise SystemExit("append constants anchor missing")
    text = text.replace(constants, "", 1)
    helper_block = '''\n\ndef _business_payload(row: Mapping[str, Any]) -> dict[str, Any]:\n    """Return source/business payload while excluding framework-owned volatile evidence."""\n\n    return {key: value for key, value in row.items() if not key.startswith("_framework_")}\n\n\ndef _incoming_fingerprint(row: Mapping[str, Any]) -> str:\n    return canonical_hash(_business_payload(row))\n'''
    if helper_block not in text:
        raise SystemExit("append payload helper anchor missing")
    text = text.replace(helper_block, "", 1)
    text = text.replace("_business_payload(", "business_payload(")
    text = text.replace("_incoming_fingerprint(", "append_payload_fingerprint(")
    text = text.replace("canonical_hash(identity)", "append_identity_fingerprint(identity)")
    text = text.replace("_RESERVED_APPEND_FIELDS", "RESERVED_APPEND_FIELDS")
    _write(path, text)


def _share_spark_protocols() -> None:
    path = SRC / "adapters/fabric/current_projection.py"
    text = path.read_text(encoding="utf-8")
    protocol_block = '''\n\nclass SparkFrameLike(Protocol):\n    def collect(self): ...\n    def createOrReplaceTempView(self, name: str) -> None: ...\n\n\nclass SparkReaderLike(Protocol):\n    def format(self, value: str) -> "SparkReaderLike": ...\n    def option(self, key: str, value: object) -> "SparkReaderLike": ...\n    def table(self, name: str) -> SparkFrameLike: ...\n\n\nclass SparkCatalogLike(Protocol):\n    def tableExists(self, name: str) -> bool: ...\n\n\nclass SparkSessionLike(Protocol):\n    @property\n    def read(self) -> SparkReaderLike: ...\n\n    @property\n    def catalog(self) -> SparkCatalogLike: ...\n\n    def sql(self, query: str) -> SparkFrameLike: ...\n'''
    if protocol_block not in text:
        raise SystemExit("current projection Spark protocol anchor missing")
    text = text.replace(protocol_block, "", 1)
    text = _ensure_import(
        text,
        "from fabric_data_framework.adapters.fabric.spark_protocols import (\n"
        "    SparkCatalogLike,\n"
        "    SparkFrameLike,\n"
        "    SparkReaderLike,\n"
        "    SparkSessionLike,\n"
        ")",
    )
    _write(path, text)


def _update_ci() -> None:
    path = ROOT / ".github/workflows/ci.yml"
    text = path.read_text(encoding="utf-8")
    anchor = "            src/fabric_data_framework/adapters/fabric/current_projection.py\n"
    addition = (
        anchor
        + "            src/fabric_data_framework/adapters/fabric/append.py \\\n"
        + "            src/fabric_data_framework/execution/backends/fabric_spark_append.py \\\n"
        + "            src/fabric_data_framework/execution/backends/fabric_spark_dataset.py\n"
    )
    if anchor not in text:
        raise SystemExit("CI complexity anchor missing")
    text = text.replace(anchor, addition, 1)
    _write(path, text)


def _update_docs_and_state() -> None:
    implementation_path = ROOT / "docs/internal/IMPLEMENTATION_MAP.md"
    implementation = implementation_path.read_text(encoding="utf-8")
    implementation = implementation.replace(
        "contracts/       provider-neutral immutable runtime/semantic contracts + deterministic contract invariants",
        "contracts/       provider-neutral immutable runtime/semantic contracts + deterministic hash/temporal/invariant primitives",
        1,
    )
    old_flow = '''capture/watermark.py\n-> execution/append.py\n-> apply/append.py\n-> quality/reconciliation/append.py\n-> quality/reconciliation/engine.py'''
    new_flow = '''capture/watermark.py\n-> distributed accepted/staged relation\n-> execution/backends/fabric_spark_append.py\n-> adapters/fabric/append.py\n-> quality/reconciliation/append.py\n-> quality/reconciliation/engine.py\n\napply/append.py remains the deterministic in-memory reference/oracle; it is not the\nproduction large-target physical path.'''
    if old_flow not in implementation:
        raise SystemExit("implementation APPEND flow anchor missing")
    implementation = implementation.replace(old_flow, new_flow, 1)
    implementation = implementation.replace(
        "execution/append.py           capture-neutral APPEND batch coordination\napply/append.py               append identity, idempotent replay, conflict fail-closed rules",
        "execution/append.py           capture-neutral in-memory/reference APPEND coordination\napply/append.py               deterministic semantic oracle for identity/replay/conflict rules\nexecution/backends/fabric_spark_append.py distributed accepted-batch coordination + reconciliation/audit\nadapters/fabric/append.py      Spark/Delta DISTINCT/JOIN/MERGE/verification; never collects the target",
        1,
    )
    _write(implementation_path, implementation)

    capabilities_path = ROOT / "docs/internal/CAPABILITIES.md"
    capabilities = capabilities_path.read_text(encoding="utf-8")
    old_capability = "| APPEND stable identity / exact replay no-op / conflicting identity fail-closed | `execution/append.py` + `apply/append.py` + `quality/reconciliation/append.py` | IMPLEMENTED + source contract |"
    new_capability = "| APPEND stable identity / exact replay no-op / conflicting identity fail-closed | `apply/append.py` reference oracle + `execution/backends/fabric_spark_append.py` + `adapters/fabric/append.py` + `quality/reconciliation/append.py` | IMPLEMENTED distributed Spark/Delta path + source contract; live Fabric proof remains candidate-specific |"
    if old_capability not in capabilities:
        raise SystemExit("capabilities APPEND anchor missing")
    capabilities = capabilities.replace(old_capability, new_capability, 1)
    _write(capabilities_path, capabilities)

    architecture_path = ROOT / "docs/ARCHITECTURE.md"
    architecture = architecture_path.read_text(encoding="utf-8")
    anchor = "Bronze may legitimately retain repeated source observations caused by bounded lookback. Silver APPEND may deduplicate those observations under a declared stable `append_identity`."
    addition = anchor + "\n\nFor production Fabric APPEND, target comparison is a distributed physical operation. The framework stages/deduplicates the accepted incoming relation in Spark, joins only inside the engine, fails closed on identity/payload conflicts, and uses Delta `MERGE` for new identities. The production path must not `collect()`, convert to pandas, or otherwise materialize the complete target table in Python. `apply/append.py` is the deterministic semantic reference, not the large-table physical runtime."
    if anchor not in architecture:
        raise SystemExit("architecture APPEND anchor missing")
    architecture = architecture.replace(anchor, addition, 1)
    _write(architecture_path, architecture)

    reading_path = ROOT / "docs/CODE_READING_GUIDE.md"
    reading = reading_path.read_text(encoding="utf-8")
    anchor = "Raw/Event Bronze may retain repeated source observations from lookback. Silver APPEND deduplicates under `append_identity`. Exact replay is a no-op; same identity with different business payload fails closed. If two legitimate events are indistinguishable at source, the framework cannot invent event fidelity."
    addition = anchor + "\n\nWhen reading APPEND code, distinguish semantics from physical scale: `apply/append.py` is the in-memory reference oracle, while `adapters/fabric/append.py` owns the production Spark/Delta DISTINCT/JOIN/MERGE path. Production APPEND never reads the complete existing target into Python memory."
    if anchor not in reading:
        raise SystemExit("code reading APPEND anchor missing")
    reading = reading.replace(anchor, addition, 1)
    _write(reading_path, reading)

    state_path = ROOT / "docs/internal/STATE.md"
    state = state_path.read_text(encoding="utf-8")
    state = state.replace(
        "not_selected_after_architecture_readability_refactor",
        "not_selected_after_append_scalability_refactor",
    )
    stale_next = "  - merge the architecture/readability refactor only after exact PR-head CI and installed-wheel acceptance pass\n  - keep release blocked and leave current_source_candidate_git_sha unselected during this refactor task\n  - select exact post-merge main source + wheel bytes only in a separate explicit candidate-selection task"
    new_next = "  - keep release blocked and leave current_source_candidate_git_sha unselected after the APPEND scalability/foundation refactor\n  - select exact post-merge main source + wheel bytes only in a separate explicit candidate-selection task"
    if stale_next not in state:
        raise SystemExit("state next-boundary anchor missing")
    state = state.replace(stale_next, new_next, 1)
    cert_anchor = "certification:\n  source_tests: required"
    append_state = "append_runtime:\n  in_memory_apply_role: deterministic_reference_only\n  fabric_spark_delta_distributed_path: implemented_source_proven\n  production_target_materialization_in_python_allowed: false\n  live_fabric_proof: not_run_for_current_unselected_source\n\ncertification:\n  source_tests: required"
    if cert_anchor not in state:
        raise SystemExit("state certification anchor missing")
    state = state.replace(cert_anchor, append_state, 1)
    _write(state_path, state)

    consistency_path = ROOT / "tests/test_current_docs_consistency.py"
    consistency = consistency_path.read_text(encoding="utf-8")
    consistency = consistency.replace(
        "not_selected_after_architecture_readability_refactor",
        "not_selected_after_append_scalability_refactor",
    )
    _write(consistency_path, consistency)


def main() -> None:
    _migrate_hash_owner()
    _migrate_temporal_owner()
    _refactor_append_reference()
    _share_spark_protocols()
    _update_ci()
    _update_docs_and_state()


if __name__ == "__main__":
    main()
