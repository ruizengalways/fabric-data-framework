# Getting started

This document covers installation, local development, wheel creation and stable Fabric consumption. Architecture belongs in [`ARCHITECTURE.md`](ARCHITECTURE.md); release certification belongs in [`TESTING_AND_CERTIFICATION.md`](TESTING_AND_CERTIFICATION.md).

## 1. Choose the correct repository

Use `fabric-data-framework` when developing or consuming reusable framework behavior.

Use `fabric-customer` when you need the independent Fabric-native source-system simulator/testbed.

Use an implementation/domain repo such as `fabric-health` for a real project using the framework.

Use `fabric-infra` for Fabric capacity/workspace/permission infrastructure.

## 2. Local framework development

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check src tests
```

Editable installation is a source-development path only.

## 3. Build an immutable wheel

```bash
python -m pip install build
python -m build --wheel
```

Shared/stable environments should consume an immutable wheel. Do not treat `%pip install git+...` or an editable checkout as the production artifact.

## 4. Prove the installed wheel independently from source

```bash
python -m venv .cert-venv
.cert-venv/bin/python -m pip install dist/fabric_data_framework-*.whl
.cert-venv/bin/python -m pip check
.cert-venv/bin/python certification_harness/smoke_installed_wheel.py \
  --wheel dist/fabric_data_framework-*.whl
```

The clean interpreter must not rely on repository `src/` imports. The smoke attests the active package payload against the candidate wheel bytes and runs framework-owned semantic probes.

## 5. Consume the wheel in Fabric

Recommended stable path:

```text
approved CI / GitHub release wheel
  -> Fabric Environment custom library
  -> Publish Environment
  -> Notebook / Spark Job / Pipeline child
```

Runtime code imports `fabric_data_framework` from the published Environment.

## 6. Create a real implementation project

```bash
fabric-framework project-init ./fabric-health --domain health
cd fabric-health
fabric-framework project-validate .
```

The generated project is a source-controlled scaffold. It does not guess keys, watermarks, delete semantics, SCD strategy, secrets or physical Fabric resources.

Continue with [`IMPLEMENTATION_PROJECT.md`](IMPLEMENTATION_PROJECT.md).

## 7. Onboard a new dataset

Before choosing Copy, Spark or Pipeline, identify the actual source facts:

```text
full snapshot vs incremental vs CDC/events
stable primary key
ordering/watermark evidence
delete visibility
late/back-dated updates
provider change collapsing
required current/history fidelity
```

Use [`DATA_PATTERNS.md`](DATA_PATTERNS.md) for the decision tree.

## 8. Certification

Framework certification belongs to this repository. Minimal real-Fabric entry point:

```python
from fabric_data_framework.certification import certify_installed, print_certification_summary

report = certify_installed(
    spark=spark,
    certification_root="/lakehouse/default/Files/framework_cert",
)
print_certification_summary(report)
```

For the artifact layout, integration inputs, mutation authorization and evidence rules, read [`TESTING_AND_CERTIFICATION.md`](TESTING_AND_CERTIFICATION.md).

## 9. Current state

Do not infer current release/Fabric proof from an old runbook. Read [`internal/STATE.md`](internal/STATE.md).
