# fabric-data-framework

Reusable Microsoft Fabric Data Engineering Framework.

This repository owns reusable processing semantics and its own package lifecycle: ingestion, Bronze/Silver behavior, full refresh, incremental watermark, SCD1, SCD2, CDC/Debezium normalization, metadata/configuration, audit/observability, retry/idempotency, Fabric runtime abstractions, Lakehouse/Warehouse integration and **lightweight installed-wheel certification**.

## Repository boundary

```text
fabric-infra
  Fabric capacity/workspace/permissions/infrastructure lifecycle

fabric-customer
  Fabric-native, framework-agnostic source-system simulator
  deterministic source changes + expected business truth

fabric-data-framework
  reusable processing framework + framework-owned certification
```

Important invariant: `fabric-customer` may use Fabric capabilities but must not depend on this framework implementation. A real application/consumer project may depend on a released framework wheel; the customer simulator does not.

See `docs/human/ARCHITECTURE_BOUNDARIES.md`.

## Source tests vs certification

These are different lifecycle gates:

```text
tests/
  source-level unit/component/integration tests

certification/
  built + installed wheel acceptance
  real Fabric environment validation
```

The certification lifecycle is deliberately:

```text
source -> build wheel -> install exact wheel -> attest installed bytes -> certify in Fabric
```

The `fabric-framework certify` command now refuses to proceed unless the active installed `fabric_data_framework` package payload matches the candidate wheel byte-for-byte. It does not silently certify `../src`.

See `docs/human/CERTIFICATION_LIFECYCLE.md`.

## Local development

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check src tests
```

Editable install is for development only.

## Build and locally prove the wheel install

```bash
python -m pip install build
python -m build --wheel
python -m venv .cert-venv
.cert-venv/bin/python -m pip install dist/fabric_data_framework-*.whl
.cert-venv/bin/python certification/smoke_installed_wheel.py --wheel dist/fabric_data_framework-*.whl
```

The smoke checks exact installed package bytes plus framework-owned metadata, incremental watermark and CDC contracts. GitHub Actions repeats this in a clean interpreter.

## Real Fabric certification

Place one exact candidate wheel plus `CANDIDATE.json` under the attached Lakehouse path:

```text
/lakehouse/default/Files/framework_cert/
```

Install that exact wheel in the Fabric Environment/runtime, then run:

```bash
fabric-framework certify --certification-root /lakehouse/default/Files/framework_cert --require-complete
```

or inside a notebook:

```python
from fabric_data_framework.certification import certify_installed, print_certification_summary

report = certify_installed(
    spark=spark,
    certification_root="/lakehouse/default/Files/framework_cert",
)
print_certification_summary(report)
```

The bounded real-Fabric suite covers exact candidate identity, Lakehouse Delta read/write, full replace, SCD1, SCD2, retry/idempotency and fail-closed reconciliation. The installed semantic preflight covers metadata/config, incremental watermark and CDC normalization. Warehouse/control-plane/provider checks remain environment-dependent and run only when explicitly configured/authorized; they are never claimed locally.

## How consumers use the framework

Stable environments consume an immutable wheel, normally through a published Fabric Environment. Framework code stays in Git; the wheel is not edited inside Fabric.

For a real implementation project, the existing project tooling remains available:

```bash
fabric-framework project-init ./my-fabric-project --domain health
fabric-framework project-validate ./my-fabric-project
```

Do not use `fabric-customer` as the framework application repository; it is the independent production-source testbed.

## Documentation

Start with:

- `docs/human/README.md`
- `docs/human/ARCHITECTURE_BOUNDARIES.md`
- `docs/human/GETTING_STARTED.md`
- `docs/human/DATASET_ONBOARDING.md`
- `docs/human/CERTIFICATION_LIFECYCLE.md`
- `docs/human/FRAMEWORK_DEVELOPER_CERTIFICATION.md`
- `docs/human/TESTING_STRATEGY.md`
- `docs/human/OPERATIONS.md`

Machine/recovery evidence remains under `docs/machine/`.

## Release status

- latest public release: `v0.3.0`
- `main` currently contains `0.4.0` development work and is not yet a public release
