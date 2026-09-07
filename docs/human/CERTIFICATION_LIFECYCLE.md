# Installed-wheel certification lifecycle

## WHY

Source tests prove source code. They do not prove that the released wheel contains the intended files, installs correctly, imports from site-packages/Fabric Environment, or works against real Fabric services.

Certification therefore has a hard artifact boundary:

```text
source
  -> build wheel
  -> freeze candidate identity
  -> install exact wheel
  -> attest installed package bytes
  -> run framework semantic acceptance
  -> run real Fabric acceptance
```

## WHAT runs where

### Source-level `tests/`

Unit/component/integration tests run against the repository source tree. They may use `src/` on `PYTHONPATH`. They are not certification.

### Top-level `certification/`

`certification/smoke_installed_wheel.py` runs under an interpreter where the exact wheel is installed. It verifies every file under the installed `fabric_data_framework` package against the same file in the candidate wheel, then runs self-contained metadata/incremental/CDC probes.

### Real Fabric bounded suite

After installed-wheel attestation passes, `certify_installed()` runs the existing bounded suite against an active Fabric Spark session and attached Lakehouse. It covers:

- exact candidate manifest/wheel identity
- Lakehouse Delta write/read
- full snapshot + replace guard
- watermark/SCD1 semantics
- watermark/SCD2 semantics
- retry/rerun idempotency
- fail-closed reconciliation

### Environment-dependent integration suite

Warehouse, Control Plane, Pipeline/Copy/Spark provider and fault-injection checks require real resources and explicit authorization. They cannot be truthfully marked PASS by local CI. Existing approved unified/integration runners remain framework code. The historical `--customer-inputs` option is retained only as a backward-compatible name for an optional integration-input bundle; new automation should treat that bundle as framework certification input, not as a responsibility of `fabric-customer`.

## HOW: local installed-wheel smoke

```bash
python -m pip install build
python -m build --wheel
python -m venv .cert-venv
.cert-venv/bin/python -m pip install dist/fabric_data_framework-*.whl
.cert-venv/bin/python -m pip check
.cert-venv/bin/python certification/smoke_installed_wheel.py --wheel dist/fabric_data_framework-*.whl
```

Expected status: `LOCAL PASS` when CI/local execution succeeds.

This does not prove Fabric access.

## HOW: Fabric certification

1. Use a dedicated DEV certification workspace/Lakehouse/Warehouse.
2. Put exactly one candidate wheel plus matching `CANDIDATE.json` under `/lakehouse/default/Files/framework_cert/`.
3. Install that wheel in the Fabric Environment and publish/restart the runtime as required.
4. Run:

```python
from fabric_data_framework.certification import certify_installed, print_certification_summary

report = certify_installed(
    spark=spark,
    certification_root="/lakehouse/default/Files/framework_cert",
)
print_certification_summary(report)
```

5. For environment-dependent integrations, provide the approved framework certification input bundle and runtime-only credentials/URLs, then explicitly authorize only the mutations required by that run.
6. Retain the unified report with candidate Git SHA and wheel SHA256.

Until those real calls succeed, status is `FABRIC CERTIFICATION REQUIRED`.

## Failure behavior

If the candidate wheel is not installed, the installed version differs, or any active installed package file differs from the wheel, certification stops before Fabric mutation. This prevents an editable/source checkout from being mistaken for wheel acceptance.
