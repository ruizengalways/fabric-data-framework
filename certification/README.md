# Installed-wheel certification

This directory is intentionally separate from `tests/`.

- `tests/` validates framework source code and contracts.
- `certification/` builds/uses framework-owned certification fixtures and validates a **built and installed wheel** before/inside real Microsoft Fabric.

Lifecycle:

```text
source tests
-> build exact wheel
-> install exact wheel
-> attest active installed package bytes
-> semantic smoke
-> discover/review exact DEV physical bindings when integration gates are needed
-> build framework-owned integration inputs
-> real Fabric certification
```

Do not add the repository `src/` directory to the certification interpreter path.

Local installed-wheel smoke:

```bash
python -m build --wheel
python -m venv .cert-venv
.cert-venv/bin/python -m pip install dist/fabric_data_framework-*.whl
.cert-venv/bin/python certification/smoke_installed_wheel.py \
  --wheel dist/fabric_data_framework-*.whl
```

The smoke proves the active package payload matches the candidate wheel package bytes. It does **not** claim real Fabric success.

Framework-owned integration-input construction lives with this certification surface. Use the read-only `discover_certification_bindings_from_names(...)` API or `fabric-framework discover-certification-bindings` before producing environment-dependent integration inputs. The complete binding discovery, review, execution and evidence rules are documented once in `docs/TESTING_AND_CERTIFICATION.md`.
