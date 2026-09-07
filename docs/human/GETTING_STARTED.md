# Getting Started

## 1. Decide which repository you need

Use this repository when you are developing or consuming reusable framework capability. Use `fabric-customer` when you need the independent Fabric-native source-system simulator/testbed. Use `fabric-infra` for capacity/workspace/permission infrastructure lifecycle.

A real business implementation project should normally be its own repository and may depend on the framework wheel. `fabric-customer` itself must not depend on the framework.

See `ARCHITECTURE_BOUNDARIES.md` before creating a new repo.

## 2. Local framework development

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check src tests
```

Editable mode is intentionally a **source-test** path.

## 3. Build an immutable wheel

```bash
python -m pip install build
python -m build --wheel
```

Production/shared environments should consume immutable wheel bytes, normally through a Fabric Environment custom library. Do not use an editable checkout or `%pip install git+...` as a stable production artifact.

## 4. Prove the wheel install independently from source

```bash
python -m venv .cert-venv
.cert-venv/bin/python -m pip install dist/fabric_data_framework-*.whl
.cert-venv/bin/python certification/smoke_installed_wheel.py --wheel dist/fabric_data_framework-*.whl
```

This interpreter must not put the repository `src/` on its import path.

## 5. Fabric consumption

Recommended stable pattern:

```text
GitHub Release / approved CI candidate wheel
  -> Fabric Environment custom library
  -> Publish Environment
  -> Notebook / Spark Job / Pipeline child
```

Then normal runtime code imports `fabric_data_framework` from the installed Environment.

## 6. Framework certification

Framework certification belongs to this repository. Follow `CERTIFICATION_LIFECYCLE.md` and `FRAMEWORK_DEVELOPER_CERTIFICATION.md`. The normal command is:

```bash
fabric-framework certify --certification-root /lakehouse/default/Files/framework_cert
```

It first attests that the active package payload equals the candidate wheel bytes, then runs framework-owned semantic and Fabric checks.

## 7. New implementation project

If you need a source-controlled application/domain project that uses the framework:

```bash
fabric-framework project-init ./fabric-health --domain health
fabric-framework project-validate ./fabric-health
```

Author business DatasetConfig/framework metadata in that consuming project, not in the `fabric-customer` source simulator.

Use `IMPLEMENTATION_PROJECT_BOOTSTRAP.md` for the complete repo/layout/runbook. The older filename `CUSTOMER_PROJECT_BOOTSTRAP.md` is retained only as a compatibility pointer because the phrase "customer repo" is now ambiguous.

## 8. New dataset

Understand source fidelity first: full snapshot, incremental watermark, ordered/net changes, CDC/business events, delete visibility and schema behavior. Then select the framework capture/apply strategy in the consuming project. See `DATASET_ONBOARDING.md`.

## 9. Realistic regression workload

For v1/v2 behavior comparisons, `fabric-customer` can generate one frozen framework-neutral workload with a `workload_digest`. Keep project config/adapters in the implementation repo; keep source/truth generation in the simulator.

## 10. Real Fabric evidence

Start with lower-risk checks and increase mutation scope deliberately. Do not run fault/admin operations by default. Real Fabric status must be reported separately from local status.
