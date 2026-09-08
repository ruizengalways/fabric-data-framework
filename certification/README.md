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
-> bootstrap/read back framework-owned DEV Fabric assets
-> build framework-owned integration inputs from exact physical IDs
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

For a first-time dedicated DEV workspace, use `fabric-framework bootstrap-certification-assets`. It creates/updates the framework-owned Environment, Spark Job Definition, Copy Job and Data Pipeline only when `--allow-item-mutation` is explicit, publishes the Environment using the stable `beta=false` API, and verifies definitions by provider read-back. Without the mutation flag it is read-back-only.

The bootstrap does not create capacity, workspace, networking, Lakehouse, Control Plane or Warehouse infrastructure. Those remain environment/infra prerequisites. `fabric-framework discover-certification-bindings` remains an optional read-only audit tool, not the first-time provisioning path.

The complete bootstrap, binding, dependency-wheel, execution and evidence rules are documented once in `docs/TESTING_AND_CERTIFICATION.md`.
