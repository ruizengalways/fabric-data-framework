# Testing strategy

## 1. Unit/component tests

Run from source:

```bash
pytest -q
```

These cover deterministic framework contracts and may use in-memory targets/adapters.

## 2. Package build checks

```bash
python -m build --wheel
python -m pip check
```

The wheel build is a packaging gate, not yet runtime acceptance.

## 3. Installed-wheel acceptance

Run the built wheel in a clean interpreter using `certification/smoke_installed_wheel.py`. CI workflow `.github/workflows/wheel-certification.yml` enforces this independently from the source test path.

The smoke confirms package install/import bytes, metadata/config loading, deterministic incremental watermark behavior and CDC duplicate normalization.

## 4. Real Fabric certification

`fabric-framework certify` is a real-Fabric acceptance command and now performs installed-wheel attestation first. Lakehouse/Spark checks require a Fabric runtime. Warehouse/Control Plane/Pipeline checks require their real resources and explicit mutation permissions.

Never translate a local PASS into a Fabric PASS. Report separately:

```text
LOCAL PASS
FABRIC CERTIFICATION REQUIRED
```

## 5. Production scenario validation

This is not framework certification. Use the independent `fabric-customer` workload, process the same source bytes with the implementation under test, normalize outputs and compare them with customer expected business truth.
