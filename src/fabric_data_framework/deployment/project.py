"""Developer-time customer project scaffolding.

The scaffold deliberately creates source-controlled structure only. It does not infer
source semantics, generate DatasetConfig values from table names, create Fabric items,
or mutate a live environment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from pydantic import Field

from ..contracts.base import FrozenModel


_PROJECT_DOMAIN_PATTERN = r"^[a-z][a-z0-9-]*$"
_PROJECT_MANIFEST = "fabric-project.json"


class CustomerProjectLayout(FrozenModel):
    """Stable source-controlled layout contract for one customer/domain repository."""

    schema_version: int = Field(default=1, ge=1)
    domain: str = Field(min_length=1, pattern=_PROJECT_DOMAIN_PATTERN)
    dataset_config_dir: str = "config/datasets"
    capture_selection_dir: str = "config/capture"
    environment_binding_dir: str = "config/environments"
    deployment_dir: str = "deploy"
    documentation_dir: str = "docs"
    source_dir: str = "src"
    tests_dir: str = "tests"


class CustomerProjectInitResult(FrozenModel):
    """Deterministic summary of a project initialization operation."""

    root: str
    domain: str
    manifest_path: str
    created_paths: tuple[str, ...]
    existing_paths: tuple[str, ...]


_DATASET_INVENTORY_HEADER = (
    "dataset_id,source_system,source_object,business_key,change_shape,ordering_signal,"
    "delete_signal,late_or_backdated_changes,history_requirement,capture_semantics,"
    "bronze_meaning,apply_strategy,execution_group,notes\n"
)


def _project_readme(domain: str) -> str:
    return f"""# {domain} Fabric data project

This repository is the source-controlled customer/domain layer that consumes
`fabric-data-framework` as an immutable dependency.

## Repository rule

Use one repository for this business/domain boundary. Do not create separate repos
for FULL, SCD1, SCD2, watermark, or CDC tables. Those are per-dataset semantics.

A large project can therefore contain, for example:

- 50 full-refresh datasets;
- 20 SCD2 datasets;
- 20 SCD1 datasets;
- 10 CDC datasets;

under the same `config/datasets/` directory. Use `orchestration.execution_group` and
per-dataset execution policy to group and schedule workloads.

## Onboarding flow

1. Fill `docs/dataset-inventory.csv` with the source facts you have verified.
2. Create one valid DatasetConfig JSON file per dataset in `config/datasets/`.
3. Record source/Bronze/history semantic selections under `config/capture/`.
4. Validate all datasets before deployment.
5. Keep DEV/UAT/PROD physical bindings under `config/environments/`; do not put secret
   values in Git.
6. Build immutable release artifacts and deploy through CI/CD or an approved operator
   environment.

Example validation command:

```bash
fabric-framework capture-semantic-onboarding-validate \\
  --config-dir config/datasets \\
  --selections config/capture/semantic-selections.json \\
  --require-all
```

The CLI is a local/CI/operator tool. It is not a requirement to open a terminal inside
Microsoft Fabric for normal scheduled execution.
"""


def _template_files(layout: CustomerProjectLayout) -> Mapping[str, str]:
    return {
        "README.md": _project_readme(layout.domain),
        f"{layout.dataset_config_dir}/README.md": """# DatasetConfig files

Store one `DatasetConfig` JSON file per logical dataset/table here.

Recommended naming:

```text
<dataset_id>.json
```

Do not group files by SCD1/SCD2/CDC folders unless the business domain itself requires
that boundary. Capture and apply strategies belong inside each DatasetConfig.
""",
        f"{layout.capture_selection_dir}/README.md": """# Capture semantic selections

Store source/capture/Bronze/history onboarding decisions here and validate them against
the DatasetConfig bundle. These files describe semantic claims; they are not secrets.
""",
        f"{layout.capture_selection_dir}/semantic-selections.example.json": "[]\n",
        f"{layout.environment_binding_dir}/README.md": """# Environment bindings

Store environment-local physical IDs and non-secret binding metadata here.

Keep credentials and access tokens outside Git. Source-controlled files may reference
environment-variable names or secret-store references, never secret values.
""",
        f"{layout.deployment_dir}/README.md": """# Deployment content

Keep domain-owned Fabric item definitions, deployment manifests, and related delivery
content here. Runtime package code stays in the released framework wheel.
""",
        f"{layout.documentation_dir}/README.md": """# Domain documentation

Document source contracts, operational ownership, SLAs, recovery notes, and business
semantics that are specific to this domain.
""",
        f"{layout.documentation_dir}/dataset-inventory.csv": _DATASET_INVENTORY_HEADER,
        f"{layout.source_dir}/README.md": """# Bounded domain extensions

Add customer-specific Python only when the framework cannot express a requirement
through metadata or a supported extension point. Do not copy framework source code
into this repository.
""",
        f"{layout.tests_dir}/README.md": """# Domain tests

Keep customer-specific metadata, extension, contract, and deployment tests here.
Framework implementation tests remain in the framework repository.
""",
    }


def load_customer_project_layout(path: str | Path) -> CustomerProjectLayout:
    """Load a project layout manifest from a file or project root."""

    candidate = Path(path)
    manifest = candidate / _PROJECT_MANIFEST if candidate.is_dir() else candidate
    return CustomerProjectLayout.model_validate_json(manifest.read_text(encoding="utf-8"))


def initialize_customer_project(
    root: str | Path,
    *,
    domain: str,
    allow_existing: bool = False,
) -> CustomerProjectInitResult:
    """Create a non-destructive customer project skeleton.

    By default the target must be absent or empty. ``allow_existing`` permits filling
    missing scaffold files in an existing repository, but existing files are never
    overwritten. If an existing project manifest is present, its domain must match.
    """

    project_root = Path(root)
    if project_root.exists() and not project_root.is_dir():
        raise ValueError(f"project root is not a directory: {project_root}")

    if project_root.exists() and not allow_existing:
        try:
            next(project_root.iterdir())
        except StopIteration:
            pass
        else:
            raise ValueError(
                f"project root is not empty: {project_root}; use allow_existing only when intentional"
            )

    layout = CustomerProjectLayout(domain=domain)
    project_root.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    existing: list[str] = []

    directories = (
        layout.dataset_config_dir,
        layout.capture_selection_dir,
        layout.environment_binding_dir,
        layout.deployment_dir,
        layout.documentation_dir,
        layout.source_dir,
        layout.tests_dir,
    )
    for relative in directories:
        path = project_root / relative
        if path.exists() and not path.is_dir():
            raise ValueError(f"project scaffold path is not a directory: {path}")
        path.mkdir(parents=True, exist_ok=True)

    manifest_path = project_root / _PROJECT_MANIFEST
    if manifest_path.exists():
        if not manifest_path.is_file():
            raise ValueError(f"project manifest path is not a file: {manifest_path}")
        existing_layout = load_customer_project_layout(manifest_path)
        if existing_layout.domain != layout.domain:
            raise ValueError(
                "existing project manifest domain does not match requested domain: "
                f"{existing_layout.domain!r} != {layout.domain!r}"
            )
        existing.append(_PROJECT_MANIFEST)
    else:
        manifest_path.write_text(layout.model_dump_json(indent=2) + "\n", encoding="utf-8")
        created.append(_PROJECT_MANIFEST)

    for relative, content in _template_files(layout).items():
        path = project_root / relative
        if path.exists():
            if not path.is_file():
                raise ValueError(f"project scaffold path is not a file: {path}")
            existing.append(relative)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(relative)

    return CustomerProjectInitResult(
        root=str(project_root),
        domain=layout.domain,
        manifest_path=_PROJECT_MANIFEST,
        created_paths=tuple(sorted(created)),
        existing_paths=tuple(sorted(existing)),
    )


__all__ = [
    "CustomerProjectInitResult",
    "CustomerProjectLayout",
    "initialize_customer_project",
    "load_customer_project_layout",
]
