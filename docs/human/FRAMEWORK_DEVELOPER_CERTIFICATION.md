# Framework Developer Certification Runbook

Audience: engineers changing `fabric-data-framework` who must certify exact wheel bytes in Microsoft Fabric before release.

## 1. Never mix the gates

```text
source tests
  != installed-wheel acceptance
  != real Fabric certification
  != release authorization
```

A green source CI run does not prove the wheel installed in Fabric. A bounded Fabric PASS does not automatically authorize a release.

## 2. Development gate

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check src tests
```

Expected: `LOCAL PASS` for source-level verification.

## 3. Build/freeze candidate

Use the repository CI/release workflow to build the candidate wheel and retain exact Git SHA, wheel filename, wheel SHA256 and workflow run identity. For local feedback:

```bash
python -m build --wheel
```

## 4. Installed-wheel gate

Use a clean interpreter:

```bash
python -m venv .cert-venv
.cert-venv/bin/python -m pip install dist/fabric_data_framework-*.whl
.cert-venv/bin/python certification/smoke_installed_wheel.py --wheel dist/fabric_data_framework-*.whl
```

The smoke compares installed package payload files to the candidate wheel byte-for-byte. It also runs framework-owned metadata, incremental watermark and CDC checks.

## 5. Fabric preparation

In a dedicated certification workspace:

- attach a default Lakehouse to the certification Notebook;
- create `/lakehouse/default/Files/framework_cert/`;
- upload exactly one candidate wheel and matching `CANDIDATE.json` (and retained checksum if available);
- install that exact wheel in the Fabric Environment and publish/restart the runtime.

For Warehouse/Control Plane/provider stages, provision dedicated certification resources. These are framework certification resources; `fabric-customer` is no longer the owner of certification artifacts.

## 6. Run bounded Fabric certification

Inside a notebook:

```python
from fabric_data_framework.certification import certify_installed, print_certification_summary

report = certify_installed(
    spark=spark,
    certification_root="/lakehouse/default/Files/framework_cert",
)
print_certification_summary(report)
```

This runs the safest self-contained suite. The exact installed wheel, Lakehouse read/write, full replace guard, SCD1, SCD2, retry/idempotency and fail-closed reconciliation are checked. Metadata/incremental/CDC probes ran before Fabric mutation.

Expected until actually executed in Fabric: `FABRIC CERTIFICATION REQUIRED`.

## 7. Run environment-dependent checks only when configured

Full unified integration may additionally use a framework certification input bundle for real Control Plane, Pipeline/Copy/Spark and Warehouse providers. The old CLI spelling `--customer-inputs` remains for backward compatibility but must not be interpreted as ownership by the `fabric-customer` repository.

Use explicit mutation flags and dedicated DEV/UAT resources. Do not silently migrate a shared/production Control Plane or terminate Warehouse sessions to make certification green.

## 8. Retain evidence

Retain the unified report together with exact candidate Git SHA and wheel SHA256. If framework source or wheel bytes change, previous Fabric evidence belongs to the previous artifact and certification starts again.
