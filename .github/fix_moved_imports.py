from pathlib import Path


def rewrite_dir(root: str, replacements: list[tuple[str, str]]) -> None:
    base = Path(root)
    if not base.exists():
        return
    for path in sorted(base.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in replacements:
            updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")


# Files in evidence/integration/approved moved three package levels below the
# framework root. Root-sibling imports therefore need four leading dots, while
# integration evidence helpers are now siblings in the parent package.
rewrite_dir(
    "src/fabric_data_framework/evidence/integration/approved",
    [
        ("from ..adapters.", "from ....adapters."),
        ("from ..capture.", "from ....capture."),
        ("from ..certification.", "from ....certification."),
        ("from ..contracts.", "from ....contracts."),
        ("from ..control_plane.", "from ....control_plane."),
        ("from ..data_plane.", "from ....data_plane."),
        ("from ..deployment.", "from ....deployment."),
        ("from ..execution.", "from ....execution."),
        ("from ..extensions", "from ....extensions"),
        ("from ..metadata.", "from ....metadata."),
        ("from ..orchestration.", "from ....orchestration."),
        ("from ..quality.", "from ....quality."),
        ("from ..recovery.", "from ....recovery."),
        ("from .integration_checks import", "from ..checks import"),
        ("from .integration_evidence import", "from ..evidence import"),
        ("from .integration_runner import", "from ..runner import"),
        ("from .integration_evidence_merge import", "from ..merge import"),
        ("from .safety import", "from ...safety import"),
    ],
)

# Files in evidence/integration moved one level deeper than their former
# evidence-root locations.
rewrite_dir(
    "src/fabric_data_framework/evidence/integration",
    [
        ("from ..adapters.", "from ...adapters."),
        ("from ..capture.", "from ...capture."),
        ("from ..certification.", "from ...certification."),
        ("from ..contracts.", "from ...contracts."),
        ("from ..control_plane.", "from ...control_plane."),
        ("from ..data_plane.", "from ...data_plane."),
        ("from ..deployment.", "from ...deployment."),
        ("from ..execution.", "from ...execution."),
        ("from ..extensions", "from ...extensions"),
        ("from ..metadata.", "from ...metadata."),
        ("from ..orchestration.", "from ...orchestration."),
        ("from ..quality.", "from ...quality."),
        ("from ..recovery.", "from ...recovery."),
        ("from .integration_checks import", "from .checks import"),
        ("from .integration_evidence import", "from .evidence import"),
        ("from .integration_runner import", "from .runner import"),
        ("from .integration_evidence_merge import", "from .merge import"),
        ("from .integration_evidence_rerun import", "from .rerun import"),
        ("from .safety import", "from ..safety import"),
    ],
)

# Business-path evidence is now grouped under evidence/business_paths.
rewrite_dir(
    "src/fabric_data_framework/evidence/business_paths",
    [
        ("from ..adapters.", "from ...adapters."),
        ("from ..capture.", "from ...capture."),
        ("from ..certification.", "from ...certification."),
        ("from ..contracts.", "from ...contracts."),
        ("from ..control_plane.", "from ...control_plane."),
        ("from ..deployment.", "from ...deployment."),
        ("from ..execution.", "from ...execution."),
        ("from ..extensions", "from ...extensions"),
        ("from ..metadata.", "from ...metadata."),
        ("from ..quality.", "from ...quality."),
        ("from ..recovery.", "from ...recovery."),
        ("from .business_path_driver import", "from .driver import"),
        ("from .business_path_evidence import", "from .evidence import"),
        ("from .business_path_plan import", "from .plan import"),
        ("from .approved_pipeline_runner import", "from ..integration.approved.pipeline import"),
        ("from .integration_evidence import", "from ..integration.evidence import"),
        ("from .integration_runner import", "from ..integration.runner import"),
        ("from .safety import", "from ..safety import"),
    ],
)

# Release proof composition is now grouped under evidence/release.
rewrite_dir(
    "src/fabric_data_framework/evidence/release",
    [
        ("from ..adapters.", "from ...adapters."),
        ("from ..certification.", "from ...certification."),
        ("from ..contracts.", "from ...contracts."),
        ("from ..deployment.", "from ...deployment."),
        ("from ..metadata.", "from ...metadata."),
        ("from .release_readiness import", "from .readiness import"),
        ("from .integration_evidence import", "from ..integration.evidence import"),
        ("from .integration_evidence_merge import", "from ..integration.merge import"),
        ("from .business_path_release_proof import", "from ..business_paths.release_proof import"),
        ("from .manual_certification import", "from ..manual_certification import"),
        ("from .safety import", "from ..safety import"),
    ],
)

# Fabric-specific certification moved from certification/ into
# certification/fabric. Provider-neutral certification modules remain one level up.
rewrite_dir(
    "src/fabric_data_framework/certification/fabric",
    [
        ("from ..adapters.", "from ...adapters."),
        ("from ..capture.", "from ...capture."),
        ("from ..contracts.", "from ...contracts."),
        ("from ..control_plane.", "from ...control_plane."),
        ("from ..data_plane.", "from ...data_plane."),
        ("from ..deployment.", "from ...deployment."),
        ("from ..execution.", "from ...execution."),
        ("from ..extensions", "from ...extensions"),
        ("from ..metadata.", "from ...metadata."),
        ("from ..quality.", "from ...quality."),
        ("from ..recovery.", "from ...recovery."),
        ("from .bounded import", "from ..bounded import"),
        ("from .fixtures import", "from ..fixtures import"),
        ("from .installed import", "from ..installed import"),
        ("from .models import", "from ..models import"),
        ("from .semantic import", "from ..semantic import"),
        ("from .simple import", "from ..simple import"),
        ("from .unified import", "from ..unified import"),
    ],
)
