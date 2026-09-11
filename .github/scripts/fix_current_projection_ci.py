from pathlib import Path


def replace_if_present(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old in text:
        target.write_text(text.replace(old, new), encoding="utf-8")


replace_if_present(
    "tests/test_current_projection.py",
    "from fabric_data_framework.contracts.runtime import StateCommitGate\n",
    "",
)
