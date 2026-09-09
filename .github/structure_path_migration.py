from pathlib import Path

REPLACEMENTS = [
    ("fabric_data_framework.evidence.integration_evidence_merge", "fabric_data_framework.evidence.integration.merge"),
    ("fabric_data_framework.evidence.integration_evidence_rerun", "fabric_data_framework.evidence.integration.rerun"),
    ("fabric_data_framework.evidence.integration_evidence", "fabric_data_framework.evidence.integration.evidence"),
    ("fabric_data_framework.evidence.integration_checks", "fabric_data_framework.evidence.integration.checks"),
    ("fabric_data_framework.evidence.integration_runner", "fabric_data_framework.evidence.integration.runner"),
    ("fabric_data_framework.evidence.approved_capture_runner", "fabric_data_framework.evidence.integration.approved.capture"),
    ("fabric_data_framework.evidence.approved_control_plane_runner", "fabric_data_framework.evidence.integration.approved.control_plane"),
    ("fabric_data_framework.evidence.approved_pipeline_runner", "fabric_data_framework.evidence.integration.approved.pipeline"),
    ("fabric_data_framework.evidence.approved_warehouse_fault_runner", "fabric_data_framework.evidence.integration.approved.warehouse_fault"),
    ("fabric_data_framework.evidence.approved_warehouse_runner", "fabric_data_framework.evidence.integration.approved.warehouse"),
    ("fabric_data_framework.evidence.approved_business_path_runner", "fabric_data_framework.evidence.business_paths.approved_runner"),
    ("fabric_data_framework.evidence.business_path_release_proof", "fabric_data_framework.evidence.business_paths.release_proof"),
    ("fabric_data_framework.evidence.business_path_evidence", "fabric_data_framework.evidence.business_paths.evidence"),
    ("fabric_data_framework.evidence.business_path_driver", "fabric_data_framework.evidence.business_paths.driver"),
    ("fabric_data_framework.evidence.business_path_plan", "fabric_data_framework.evidence.business_paths.plan"),
    ("fabric_data_framework.evidence.release_readiness_merge", "fabric_data_framework.evidence.release.merge"),
    ("fabric_data_framework.evidence.release_readiness", "fabric_data_framework.evidence.release.readiness"),
    ("fabric_data_framework.evidence.candidate_certification", "fabric_data_framework.evidence.release.candidate_certification"),
    ("fabric_data_framework.certification.fabric_assets", "fabric_data_framework.certification.fabric.assets"),
    ("fabric_data_framework.certification.fabric_job", "fabric_data_framework.certification.fabric.fabric_job"),
    ("fabric_data_framework.certification.pipeline_child", "fabric_data_framework.certification.fabric.pipeline_child"),
    ("fabric_data_framework.certification.bindings", "fabric_data_framework.certification.fabric.bindings"),
    ("fabric_data_framework.quality.reconciliation_engine", "fabric_data_framework.quality.reconciliation.engine"),
    ("fabric_data_framework.quality.full_refresh", "fabric_data_framework.quality.reconciliation.full_replace"),
    ("fabric_data_framework.quality.append", "fabric_data_framework.quality.reconciliation.append"),
    ("fabric_data_framework.quality.snapshot_diff", "fabric_data_framework.quality.reconciliation.snapshot_diff"),
    ("fabric_data_framework.execution.dataset_runner", "fabric_data_framework.execution.watermark_scd2"),
    ("certification/build_integration_inputs.py", "certification_harness/build_integration_inputs.py"),
    ("certification/smoke_installed_wheel.py", "certification_harness/smoke_installed_wheel.py"),
    ("certification/integration_project", "certification_harness/integration_project"),
]

ROOTS = [Path("src"), Path("tests"), Path("docs"), Path(".github"), Path("certification_harness"), Path("examples"), Path("release")]
FILES = [Path("README.md"), Path("CONTRIBUTING.md"), Path("pyproject.toml")]
EXTENSIONS = {".py", ".md", ".yml", ".yaml", ".json", ".toml", ".txt"}
for root in ROOTS:
    if root.exists():
        FILES.extend(p for p in root.rglob("*") if p.is_file() and p.suffix in EXTENSIONS)

SELF = Path(".github/structure_path_migration.py")
TEMP_WORKFLOW = Path(".github/workflows/structure-path-migration.yml")
for path in sorted(set(FILES)):
    if path in {SELF, TEMP_WORKFLOW} or not path.exists():
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    updated = text
    for old, new in REPLACEMENTS:
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated, encoding="utf-8")

# Relative imports inside files that moved into deeper packages.
RELATIVE_REPLACEMENTS = {
    "src/fabric_data_framework/evidence/integration/merge.py": [
        ("from .integration_evidence import", "from .evidence import"),
    ],
    "src/fabric_data_framework/evidence/integration/rerun.py": [
        ("from .integration_evidence import", "from .evidence import"),
        ("from .integration_evidence_merge import", "from .merge import"),
    ],
    "src/fabric_data_framework/evidence/integration/checks.py": [
        ("from .integration_evidence import", "from .evidence import"),
    ],
    "src/fabric_data_framework/evidence/business_paths/evidence.py": [
        ("from .business_path_driver import", "from .driver import"),
        ("from .business_path_plan import", "from .plan import"),
    ],
    "src/fabric_data_framework/evidence/business_paths/approved_runner.py": [
        ("from .business_path_driver import", "from .driver import"),
        ("from .business_path_evidence import", "from .evidence import"),
        ("from .business_path_plan import", "from .plan import"),
    ],
    "src/fabric_data_framework/evidence/business_paths/release_proof.py": [
        ("from .business_path_evidence import", "from .evidence import"),
    ],
    "src/fabric_data_framework/evidence/release/merge.py": [
        ("from .release_readiness import", "from .readiness import"),
    ],
    "src/fabric_data_framework/certification/fabric/assets.py": [
        ("from .bindings import", "from .bindings import"),
        ("from .models import", "from ..models import"),
    ],
    "src/fabric_data_framework/certification/fabric/fabric_job.py": [
        ("from .models import", "from ..models import"),
    ],
    "src/fabric_data_framework/certification/fabric/pipeline_child.py": [
        ("from .models import", "from ..models import"),
        ("from .fixtures import", "from ..fixtures import"),
        ("from .bounded import", "from ..bounded import"),
    ],
}
for path_str, pairs in RELATIVE_REPLACEMENTS.items():
    path = Path(path_str)
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    updated = text
    for old, new in pairs:
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated, encoding="utf-8")

READMES = {
    "src/fabric_data_framework/capture/README.md": ("Capture", "Source-change semantics and capture planning.", "api.py, patterns.py, semantic_contracts.py", "Apply/target mutation semantics.", "../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/apply/README.md": ("Apply", "Provider-neutral target-state mutation semantics.", "current_state.py, scd1.py, scd2.py, cdc.py", "Capture transport or orchestration.", "../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/data_plane/README.md": ("Data Plane", "Source-faithful Bronze normalization and transient staging primitives.", "bronze.py, staging.py", "Durable control state or provider transport.", "../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/metadata/README.md": ("Metadata", "Typed DatasetConfig and capability validation.", "config.py, capabilities.py", "Runtime side effects.", "../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/quality/README.md": ("Quality", "Row quality, quarantine payload persistence, schema/temporal checks, and reconciliation.", "rules.py, quarantine_store.py, reconciliation/", "Business-specific cleansing logic.", "../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/quality/reconciliation/README.md": ("Reconciliation", "Framework-owned semantic reconciliation policy evaluation and strategy checks.", "engine.py, append.py, full_replace.py, scd2.py, snapshot_diff.py", "Provider observations as semantic authority.", "../../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/orchestration/README.md": ("Orchestration", "Plan and dispatch dataset work without owning provider execution details.", "planner.py, dispatcher.py", "Capture/apply semantics or provider APIs.", "../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/execution/README.md": ("Execution", "Reference dataset execution paths and backend dispatch contracts.", "watermark_scd2.py, append.py, full_replace.py, snapshot_diff.py, backends/", "Business-specific mappings.", "../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/adapters/README.md": ("Adapters", "Provider/source-specific implementations behind framework-owned contracts.", "fabric/, cdc/", "Framework semantic decisions.", "../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/recovery/README.md": ("Recovery", "Replay, rebuild, target probing, cutover, and unknown-outcome recovery.", "runtime.py, replay.py, rebuild.py, target_probe.py", "Ordinary happy-path execution.", "../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/certification/README.md": ("Certification", "Framework-owned bounded, installed-wheel, semantic, and Fabric certification logic.", "bounded.py, installed.py, unified.py, fabric/", "Customer/domain certification identity.", "../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/certification/fabric/README.md": ("Fabric Certification", "Microsoft Fabric-specific binding discovery, asset bootstrap, job and pipeline-child certification.", "bindings.py, assets.py, fabric_job.py, pipeline_child.py", "Provider-neutral certification semantics.", "../../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/evidence/integration/README.md": ("Integration Evidence", "Typed integration evidence, preflight, rerun/merge logic, and approved executors.", "evidence.py, runner.py, checks.py, approved/", "Release policy or business-path semantics.", "../../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/evidence/business_paths/README.md": ("Business Path Evidence", "Framework-owned business-path plans, drivers, retained evidence, and release proof composition.", "plan.py, driver.py, evidence.py, approved_runner.py", "Customer business identity.", "../../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/evidence/release/README.md": ("Release Evidence", "Candidate certification and release-readiness proof composition.", "candidate_certification.py, readiness.py, merge.py", "Artifact creation or Fabric execution.", "../../../../docs/DEVELOPMENT_GUIDE.md"),
    "src/fabric_data_framework/extensions/README.md": ("Extensions", "Explicit registered extension points for supported customization.", "registry.py", "Ad-hoc imports of framework internals.", "../../../docs/DEVELOPMENT_GUIDE.md"),
}
for path_str, (title, purpose, start, not_owns, dev_link) in READMES.items():
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {title}\n\n## Purpose\n\n{purpose}\n\n## Start here\n\n`{start}`\n\n## Does not own\n\n{not_owns}\n\n## Dependency rule\n\nKeep framework semantics provider-neutral; depend inward on contracts/metadata rather than on CLI or certification presentation layers. See [`docs/DEVELOPMENT_GUIDE.md`]({dev_link}) for the repository-wide change workflow.\n",
        encoding="utf-8",
    )
