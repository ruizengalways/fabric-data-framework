from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from fabric_data_framework.certification import installed as installed_module


class FakeDistribution:
    version = "0.4.0"

    def __init__(self, root: Path):
        self.root = root

    def locate_file(self, name):
        return self.root / name


def _wheel(tmp_path: Path, content: bytes = b"candidate") -> Path:
    wheel = tmp_path / "fabric_data_framework-0.4.0-py3-none-any.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr("fabric_data_framework/example.py", content)
    return wheel


def test_attestation_accepts_exact_installed_package_bytes(monkeypatch, tmp_path):
    wheel = _wheel(tmp_path)
    installed_root = tmp_path / "site-packages"
    package = installed_root / "fabric_data_framework"
    package.mkdir(parents=True)
    (package / "example.py").write_bytes(b"candidate")
    monkeypatch.setattr(installed_module, "distribution", lambda _: FakeDistribution(installed_root))

    result = installed_module.attest_installed_wheel(wheel)

    assert result.framework_version == "0.4.0"
    assert result.checked_package_files == 1
    assert len(result.wheel_sha256) == 64


def test_attestation_rejects_source_or_other_install_bytes(monkeypatch, tmp_path):
    wheel = _wheel(tmp_path)
    installed_root = tmp_path / "site-packages"
    package = installed_root / "fabric_data_framework"
    package.mkdir(parents=True)
    (package / "example.py").write_bytes(b"different")
    monkeypatch.setattr(installed_module, "distribution", lambda _: FakeDistribution(installed_root))

    with pytest.raises(ValueError, match="does not match candidate wheel bytes"):
        installed_module.attest_installed_wheel(wheel)
