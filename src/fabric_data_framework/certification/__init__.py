"""Public certification API for real Microsoft Fabric environments."""

from .bounded import run_bounded_certification
from .fabric.assets import (
    CertificationFabricAssetPlan,
    CertificationFabricBootstrapReport,
    FabricCertificationAssetClient,
    FabricDefinitionPart,
    FabricItemDefinition,
    assert_definition_read_back_matches,
    build_certification_fabric_asset_plan,
)
from .fabric.bindings import (
    CertificationBindingItem,
    CertificationIntegrationBindings,
    discover_certification_bindings,
    discover_certification_bindings_from_names,
)
from .installed import InstalledWheelAttestation, attest_installed_wheel, certify_installed
from .models import (
    CertificationCheckResult,
    CertificationCheckStatus,
    CertificationOverallStatus,
    UnifiedCertificationReport,
)
from .semantic import run_semantic_acceptance
from .simple import DEFAULT_CERTIFICATION_ROOT, certify
from .unified import print_certification_summary


__all__ = [
    "CertificationBindingItem",
    "CertificationCheckResult",
    "CertificationCheckStatus",
    "CertificationFabricAssetPlan",
    "CertificationFabricBootstrapReport",
    "CertificationIntegrationBindings",
    "CertificationOverallStatus",
    "DEFAULT_CERTIFICATION_ROOT",
    "FabricCertificationAssetClient",
    "FabricDefinitionPart",
    "FabricItemDefinition",
    "InstalledWheelAttestation",
    "UnifiedCertificationReport",
    "assert_definition_read_back_matches",
    "attest_installed_wheel",
    "build_certification_fabric_asset_plan",
    "certify",
    "certify_installed",
    "discover_certification_bindings",
    "discover_certification_bindings_from_names",
    "print_certification_summary",
    "run_bounded_certification",
    "run_semantic_acceptance",
]
