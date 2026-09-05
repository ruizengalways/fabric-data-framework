import pytest

from fabric_data_framework.control_plane.enterprise import (
    ENTERPRISE_ENVIRONMENT_NAMES,
    ENTERPRISE_FABRIC_CONTROL_PLANE_PROFILE_NAME,
    assert_enterprise_fabric_control_plane_profile,
    get_enterprise_fabric_control_plane_profile,
)


def test_enterprise_fabric_uses_same_sql_database_profile_in_dev_uat_prod():
    assert ENTERPRISE_ENVIRONMENT_NAMES == ("DEV", "UAT", "PROD")
    assert ENTERPRISE_FABRIC_CONTROL_PLANE_PROFILE_NAME == "fabric_sql_database_v1"
    profile = get_enterprise_fabric_control_plane_profile()
    assert profile.profile_name == "fabric_sql_database_v1"
    assert profile.production_eligible is True
    assert profile.allowed_sqlalchemy_dialects == ("mssql",)


def test_enterprise_fabric_topology_rejects_reference_or_environment_specific_substitution():
    assert_enterprise_fabric_control_plane_profile("fabric_sql_database_v1")

    for profile_name in (
        "sqlite_reference_v1",
        "azure_sql_database_v1",
        "lakehouse_delta_v1",
    ):
        with pytest.raises(ValueError, match="enterprise Fabric DEV/UAT/PROD requires"):
            assert_enterprise_fabric_control_plane_profile(profile_name)
