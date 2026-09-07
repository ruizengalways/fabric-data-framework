# fabric-data-framework

Reusable Microsoft Fabric data engineering framework for source capture, Bronze/Silver processing, data quality, orchestration, recovery, evidence, and package certification.

The framework keeps **data semantics** separate from **Fabric execution mechanics**. A project describes what the source delivers and what the target must preserve; the framework validates those semantics, builds an execution plan, runs through approved Fabric adapters, and records durable evidence/recovery state.

## Repository boundary

```text
fabric-infra
  Fabric capacity / workspace / permission infrastructure

fabric-customer
  Fabric-native, framework-agnostic source-system simulator
  deterministic source facts + expected business truth

fabric-data-framework
  reusable framework + package lifecycle + framework certification

implementation/domain repo
  project DatasetConfig + mappings + DQ policy + environment bindings + deployment content
  may depend on an approved framework wheel
```

`fabric-customer` does not depend on this framework. Real projects such as `fabric-health` consume an approved/released framework wheel from their own implementation repository.

## Quick start

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check src tests

python -m build --wheel
```

For a real consuming project:

```bash
fabric-framework project-init ./fabric-health --domain health
fabric-framework project-validate ./fabric-health
```

Stable Fabric environments should consume immutable wheel bytes through a published Fabric Environment rather than an editable checkout.

## Certification boundary

Source tests, installed-wheel acceptance, real Fabric certification, and release authorization are separate gates:

```text
source tests
-> build exact wheel
-> install exact wheel
-> attest installed package bytes
-> framework semantic smoke
-> real Fabric certification
-> release readiness
```

Minimal Fabric entry point:

```python
from fabric_data_framework.certification import certify_installed, print_certification_summary

report = certify_installed(
    spark=spark,
    certification_root="/lakehouse/default/Files/framework_cert",
)
print_certification_summary(report)
```

Real Fabric capabilities are never marked PASS from local CI alone.

## Documentation

Start at [`docs/README.md`](docs/README.md).

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — repo ownership, semantic model, Control Plane/Data Plane topology.
- [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) — local development, wheel build, Fabric consumption.
- [`docs/IMPLEMENTATION_PROJECT.md`](docs/IMPLEMENTATION_PROJECT.md) — bootstrap a real framework-consuming domain repo.
- [`docs/DATA_PATTERNS.md`](docs/DATA_PATTERNS.md) — choose FULL, watermark, CDC, Bronze, SCD1/SCD2, delete semantics.
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — runtime failure isolation, DQ, retry, replay, backfill and recovery.
- [`docs/TESTING_AND_CERTIFICATION.md`](docs/TESTING_AND_CERTIFICATION.md) — source tests through exact-wheel real Fabric certification.
- [`docs/RELEASE.md`](docs/RELEASE.md) — candidate identity, evidence and immutable promotion.

Current engineering/release state lives only in [`docs/internal/STATE.md`](docs/internal/STATE.md).

## Release status

- Latest public release: `v0.3.0`.
- `0.4.0` remains development/unreleased until exact-byte Fabric evidence and release-readiness gates are satisfied.
