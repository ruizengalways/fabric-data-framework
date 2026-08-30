"""Integration-evidence contracts, preflight and explicitly approved run executors.

The reusable data semantics/runtime remain outside this package. ``evidence`` owns the
retained evidence model and the environment-facing executors that prove those existing
contracts without creating a second semantic truth.
"""

from .integration_evidence import (
    INTEGRATION_EVIDENCE_SCHEMA_VERSION,
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceCheckRunner,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
    load_integration_evidence_manifest,
    load_integration_evidence_spec,
    run_integration_evidence,
    validate_integration_evidence_manifest,
    write_integration_evidence_manifest,
)
from .integration_runner import (
    ApprovedIntegrationRunPlan,
    ApprovedIntegrationRunnerConfig,
    IntegrationCheckPhysicalBinding,
    RuntimeEnvironmentRequirement,
    build_approved_integration_run_plan,
    load_approved_integration_runner_config,
)

__all__ = [
    "INTEGRATION_EVIDENCE_SCHEMA_VERSION",
    "ApprovedIntegrationRunPlan",
    "ApprovedIntegrationRunnerConfig",
    "IntegrationCheckPhysicalBinding",
    "IntegrationEvidenceCheckKind",
    "IntegrationEvidenceCheckResult",
    "IntegrationEvidenceCheckRunner",
    "IntegrationEvidenceCheckSpec",
    "IntegrationEvidenceManifest",
    "IntegrationEvidenceSpec",
    "IntegrationEvidenceStatus",
    "RuntimeEnvironmentRequirement",
    "build_approved_integration_run_plan",
    "load_approved_integration_runner_config",
    "load_integration_evidence_manifest",
    "load_integration_evidence_spec",
    "run_integration_evidence",
    "validate_integration_evidence_manifest",
    "write_integration_evidence_manifest",
]
