"""Installed-wheel attestation for real Fabric certification.

Source-level tests may import from ``src``. Release certification may not: it must prove
that the active package bytes are the bytes contained in the candidate wheel.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
import re
from zipfile import ZipFile, is_zipfile


_WHEEL_VERSION = re.compile(r"^fabric_data_framework-(?P<version>[^-]+)-.+\.whl$")


@dataclass(frozen=True)
class InstalledWheelAttestation:
    wheel_path: Path
    framework_version: str
    installed_root: Path
    checked_package_files: int
    wheel_sha256: str


def _candidate_version(wheel: Path) -> str:
    match = _WHEEL_VERSION.match(wheel.name)
    if match is None:
        raise ValueError(f"unexpected framework wheel filename: {wheel.name}")
    return match.group("version")


def attest_installed_wheel(wheel_path: str | Path) -> InstalledWheelAttestation:
    """Prove that the active installed package code matches the candidate wheel bytes.

    Pip may legitimately rewrite installation metadata and console-script wrappers, so
    attestation compares every regular file under the ``fabric_data_framework`` package
    payload rather than mutable ``.dist-info`` files.
    """

    wheel = Path(wheel_path).resolve()
    if not wheel.is_file() or not is_zipfile(wheel):
        raise ValueError(f"candidate wheel is not a readable wheel archive: {wheel}")
    expected_version = _candidate_version(wheel)

    try:
        installed = distribution("fabric-data-framework")
    except PackageNotFoundError as exc:
        raise ValueError(
            "fabric-data-framework is not installed; install the candidate wheel before certification"
        ) from exc
    if installed.version != expected_version:
        raise ValueError(
            "installed framework version does not match candidate wheel: "
            f"installed={installed.version!r}, candidate={expected_version!r}"
        )

    checked = 0
    with ZipFile(wheel) as archive:
        package_files = sorted(
            name
            for name in archive.namelist()
            if name.startswith("fabric_data_framework/") and not name.endswith("/")
        )
        if not package_files:
            raise ValueError("candidate wheel does not contain the fabric_data_framework package")
        for name in package_files:
            expected = hashlib.sha256(archive.read(name)).digest()
            installed_path = Path(installed.locate_file(name)).resolve()
            if not installed_path.is_file():
                raise ValueError(f"installed candidate package file is missing: {name}")
            observed = hashlib.sha256(installed_path.read_bytes()).digest()
            if observed != expected:
                raise ValueError(
                    "active installed package does not match candidate wheel bytes: "
                    f"{name}"
                )
            checked += 1

    wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    installed_root = Path(installed.locate_file("")).resolve()
    return InstalledWheelAttestation(
        wheel_path=wheel,
        framework_version=expected_version,
        installed_root=installed_root,
        checked_package_files=checked,
        wheel_sha256=wheel_sha256,
    )


def certify_installed(
    *,
    spark,
    certification_root,
    **kwargs,
):
    """Attest the installed candidate wheel, then run the existing Fabric suite."""

    root = Path(certification_root)
    wheels = sorted(root.glob("fabric_data_framework-*.whl"))
    if len(wheels) != 1:
        raise ValueError(
            "certification root must contain exactly one fabric_data_framework-*.whl; "
            f"observed={len(wheels)}"
        )
    attest_installed_wheel(wheels[0])

    # Late import keeps this module independent from the existing certification runner
    # and avoids a circular import through the package public surface.
    from .simple import certify

    return certify(
        spark=spark,
        certification_root=root,
        **kwargs,
    )


__all__ = [
    "InstalledWheelAttestation",
    "attest_installed_wheel",
    "certify_installed",
]
