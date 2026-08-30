from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "fabric_data_framework"


def test_core_source_does_not_import_cli_package():
    offenders: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        relative = path.relative_to(PACKAGE_ROOT)
        if "cli" in relative.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if (
            "from .cli" in text
            or "from fabric_data_framework.cli" in text
            or "import fabric_data_framework.cli" in text
        ):
            offenders.append(str(relative))
    assert offenders == []


def test_core_package_imports_after_cli_directory_is_physically_removed(tmp_path: Path):
    copied_package = tmp_path / "fabric_data_framework"
    shutil.copytree(PACKAGE_ROOT, copied_package)
    shutil.rmtree(copied_package / "cli")

    code = "\n".join(
        [
            "import sys",
            f"sys.path.insert(0, {str(tmp_path)!r})",
            "import fabric_data_framework",
            "from fabric_data_framework.config import DatasetConfig, CaptureStrategy, ApplyStrategy",
            "import fabric_data_framework.capture",
            "import fabric_data_framework.apply",
            "import fabric_data_framework.execution",
            "import fabric_data_framework.recovery",
            "import fabric_data_framework.runtime",
            "assert DatasetConfig is not None",
            "assert CaptureStrategy is not None",
            "assert ApplyStrategy is not None",
            "assert not hasattr(fabric_data_framework, 'DatasetConfig')",
            "assert not hasattr(fabric_data_framework, '__version__')",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
