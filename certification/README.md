# Installed-wheel certification

This directory is intentionally separate from `tests/`.

- `tests/` validates framework source code with unit/component/integration tests.
- `certification/` validates a **built and installed wheel** and provides the entry into real Microsoft Fabric acceptance.

The lifecycle is:

```text
source -> build wheel -> install exact wheel -> attest installed bytes -> run Fabric certification
```

Do not add `../src` or the repository `src/` directory to the certification interpreter path.

Local installed-wheel smoke:

```bash
python -m build --wheel
python -m venv .cert-venv
.cert-venv/bin/python -m pip install dist/fabric_data_framework-*.whl
.cert-venv/bin/python certification/smoke_installed_wheel.py --wheel dist/fabric_data_framework-*.whl
```

On Windows use `.cert-venv\\Scripts\\python.exe`.

The smoke proves the active package payload matches the candidate wheel byte-for-byte. It does **not** claim Fabric runtime success. Real Fabric acceptance is described in `docs/human/CERTIFICATION_LIFECYCLE.md`.
