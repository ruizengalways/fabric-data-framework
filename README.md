# fabric-data-framework

Reusable Microsoft Fabric data engineering framework for source capture, Bronze/Silver processing, data quality, reconciliation, orchestration, recovery, evidence, and package certification.

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
  project DatasetConfig + mappings + DQ/reconciliation policy + environment bindings + deployment content
  project-specific provider observation adapters / business controls when required
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

## Maintainer path

If you are joining the framework team or doing secondary development, use this order:

```text
ARCHITECTURE.md
-> CODE_READING_GUIDE.md
-> DEVELOPMENT_GUIDE.md
-> focused owner-module tests
-> CONTRIBUTING.md workflow
```

`CODE_READING_GUIDE.md` explains **how the current framework works**. `DEVELOPMENT_GUIDE.md` explains **how to change it safely** without breaking repository ownership, dependency direction, fail-closed semantics, durable identities, or candidate provenance.

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

Start at [`docs/README.md`](docs/README.md). Framework contributors should also read [`CONTRIBUTING.md`](CONTRIBUTING.md).

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — repo ownership, semantic model, Control Plane/Data Plane topology.
- [`docs/CODE_READING_GUIDE.md`](docs/CODE_READING_GUIDE.md) — current end-to-end code reading order and runtime call flow.
- [`docs/DEVELOPMENT_GUIDE.md`](docs/DEVELOPMENT_GUIDE.md) — safe framework modification, extension boundaries, change-impact map, testing, debugging and review checklist.
- [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) — local development, wheel build, Fabric consumption.
- [`docs/IMPLEMENTATION_PROJECT.md`](docs/IMPLEMENTATION_PROJECT.md) — bootstrap a real framework-consuming domain repo.
- [`docs/DATA_PATTERNS.md`](docs/DATA_PATTERNS.md) — choose FULL, watermark/lookback, CDC, APPEND, Bronze, SCD1/SCD2, and delete semantics.
- [`docs/RECONCILIATION.md`](docs/RECONCILIATION.md) — configure reconciliation checks, tolerance, partitioning, WARN/FAIL semantics, provider observations, and state-gate authority.
- [`docs/CURRENT_PROJECTIONS.md`](docs/CURRENT_PROJECTIONS.md) — derive stable current objects from authoritative SCD2 history using VIEW, materialized, or incremental Delta projection modes.
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — transient runtime failure isolation, retry, replay, backfill, unknown commit, and dependency recovery.
- [`docs/REPAIR_AND_REBUILD.md`](docs/REPAIR_AND_REBUILD.md) — data-correctness repair, FULL_REBUILD scope, contaminated dependency impact, v1/v2 cutover, UAT, rollback, and retention.
- [`docs/TESTING_AND_CERTIFICATION.md`](docs/TESTING_AND_CERTIFICATION.md) — source tests through exact-wheel real Fabric certification.
- [`docs/RELEASE.md`](docs/RELEASE.md) — candidate identity, evidence and immutable promotion.

Current engineering/release state lives only in [`docs/internal/STATE.md`](docs/internal/STATE.md).

## Release status

- Latest public release: `v0.3.0`.
- `0.4.0` remains development/unreleased until exact-byte Fabric evidence and release-readiness gates are satisfied.
