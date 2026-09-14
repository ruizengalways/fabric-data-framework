from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/fabric_data_framework"


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


def main() -> None:
    for path in ROOT.rglob("*.py"):
        if ".git" in path.parts or path in {
            SRC / "contracts/temporal.py",
            Path(__file__).resolve(),
        }:
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        text = re.sub(r"\b_utcnow\b", "utc_now", text)
        text = re.sub(r"\b_require_aware\b", "require_aware_datetime", text)

        needs_now = re.search(r"\butc_now\b", text) is not None
        needs_aware = re.search(r"\brequire_aware_datetime\b", text) is not None
        if needs_now or needs_aware:
            names: list[str] = []
            if needs_aware:
                names.append("require_aware_datetime")
            if needs_now:
                names.append("utc_now")
            text = _ensure_import(
                text,
                "from fabric_data_framework.contracts.temporal import " + ", ".join(names),
            )

        if (
            path == SRC / "apply/append.py"
            and "canonical_hash(" in text
            and "from fabric_data_framework.contracts.hashing import canonical_hash" not in text
        ):
            text = _ensure_import(
                text,
                "from fabric_data_framework.contracts.hashing import canonical_hash",
            )

        if text != original:
            path.write_text(text, encoding="utf-8")

    # metadata/config consumes the canonical primitive internally but must not re-export
    # it as metadata.config.canonical_hash after the hard cut.
    config_path = SRC / "metadata/config.py"
    config = config_path.read_text(encoding="utf-8")
    config = config.replace(
        "from fabric_data_framework.contracts.hashing import canonical_hash\n",
        "from fabric_data_framework.contracts.hashing import canonical_hash as _canonical_hash\n",
        1,
    )
    config = re.sub(r"\bcanonical_hash\(", "_canonical_hash(", config)
    config_path.write_text(config, encoding="utf-8")

    # The temporal migration intentionally rewrites executable references, not the
    # literal legacy spellings asserted by this anti-regression source scan.
    foundation_path = ROOT / "tests/test_foundation_primitives.py"
    foundation = foundation_path.read_text(encoding="utf-8")
    foundation = foundation.replace(
        'if "def utc_now(" in text or "utc_now()" in text:',
        'if "def _utcnow(" in text or "datetime.now(timezone.utc)" in text:',
        1,
    )
    foundation_path.write_text(foundation, encoding="utf-8")

    # This fixture exercises the physical APPEND path, not watermark capture policy.
    append_test_path = ROOT / "tests/test_append_spark_runtime.py"
    append_test = append_test_path.read_text(encoding="utf-8")
    append_test = append_test.replace(
        "capture_strategy=CaptureStrategy.WATERMARK,",
        "capture_strategy=CaptureStrategy.FULL,",
        1,
    )
    append_test_path.write_text(append_test, encoding="utf-8")

    leftovers: list[str] = []
    for path in SRC.rglob("*.py"):
        if path.name == "temporal.py":
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\b_utcnow\b|\b_require_aware\b", text):
            leftovers.append(path.relative_to(ROOT).as_posix())
    if leftovers:
        raise SystemExit("legacy temporal references remain: " + ", ".join(leftovers))


if __name__ == "__main__":
    main()
