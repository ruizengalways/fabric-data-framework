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

`fabric-framework certify` is a real-Fabric acceptance command and performs installed-wheel attestation first. Lakehouse/Spark checks require a Fabric runtime. Warehouse/Control Plane/Pipeline/provider checks require their real resources and explicit mutation permissions.

Never translate a local PASS into a Fabric PASS. Report separately:

```text
LOCAL PASS
CI PASS
FABRIC CERTIFICATION REQUIRED
```

## 5. Implementation project validation

`fabric-framework project-validate` checks a real implementation/domain repo's source-controlled framework configuration. It is neither package certification nor end-to-end Fabric execution.

Keep project-specific DatasetConfig, mappings, bindings and adapters in that implementation repo, not in `fabric-customer`.

## 6. Production scenario validation

This is not framework certification. Use the independent `fabric-customer` workload, process the same source bytes with the implementation under test, normalize outputs and compare them with customer expected business truth.

For trustworthy v1/v2 comparisons, record at least:

```text
customer workload_digest
framework release/Git SHA
framework wheel SHA256
implementation project Git SHA
Fabric environment/workspace identity
scenario day / replay action
normalized result
```

Both v1 and v2 must use the same verified customer `workload_digest`; otherwise the result is not a controlled regression comparison.

## 7. Recommended evidence ladder

```text
source unit/component PASS
-> package build PASS
-> installed-wheel acceptance PASS
-> real Fabric framework certification PASS
-> implementation project validation PASS
-> frozen customer workload end-to-end PASS
```

Each gate answers a different question. Do not collapse them into one generic "tests passed" statement.
