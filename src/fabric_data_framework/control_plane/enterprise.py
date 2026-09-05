"""Enterprise control-plane topology contracts.

The Enterprise Fabric reference topology is environment-parity first: DEV, UAT and
PROD use the same control-plane backend class and differ only in physical bindings,
credentials, capacity and data. The canonical Microsoft Fabric control plane is a
Fabric SQL Database. Lakehouse/Delta remains a data-plane technology and is not a
canonical enterprise operational-state backend.
"""

from __future__ import annotations

from typing import Final

from .certification import (
    FABRIC_SQL_DATABASE_V1,
    ControlPlaneBackendProfile,
    get_control_plane_backend_profile,
)

ENTERPRISE_FABRIC_CONTROL_PLANE_PROFILE_NAME: Final[str] = "fabric_sql_database_v1"
ENTERPRISE_ENVIRONMENT_NAMES: Final[tuple[str, ...]] = ("DEV", "UAT", "PROD")


def get_enterprise_fabric_control_plane_profile() -> ControlPlaneBackendProfile:
    """Return the canonical control-plane profile for Fabric DEV/UAT/PROD."""

    profile = get_control_plane_backend_profile(
        ENTERPRISE_FABRIC_CONTROL_PLANE_PROFILE_NAME
    )
    if profile != FABRIC_SQL_DATABASE_V1:
        raise RuntimeError("enterprise Fabric control-plane profile registry drift")
    if not profile.production_eligible:
        raise RuntimeError("enterprise Fabric control-plane profile must be production eligible")
    return profile


def assert_enterprise_fabric_control_plane_profile(profile_name: str) -> None:
    """Fail closed when an enterprise Fabric environment uses a different profile.

    This is intentionally stricter than generic backend certification. Framework can
    qualify other relational backends (for example Azure SQL Database), but the
    canonical Microsoft Fabric reference topology uses Fabric SQL Database in DEV,
    UAT and PROD so CI/CD promotes the same architecture rather than migrating state
    stores between environments.
    """

    if profile_name != ENTERPRISE_FABRIC_CONTROL_PLANE_PROFILE_NAME:
        raise ValueError(
            "enterprise Fabric DEV/UAT/PROD requires control_plane_profile="
            f"{ENTERPRISE_FABRIC_CONTROL_PLANE_PROFILE_NAME!r}; observed={profile_name!r}"
        )


__all__ = [
    "ENTERPRISE_ENVIRONMENT_NAMES",
    "ENTERPRISE_FABRIC_CONTROL_PLANE_PROFILE_NAME",
    "assert_enterprise_fabric_control_plane_profile",
    "get_enterprise_fabric_control_plane_profile",
]
