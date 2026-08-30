# MACHINE ARCHITECTURE BOUNDARIES

This file records source-layout dependency boundaries that are easy to lose during later refactors.

## CLI boundary

```text
CLI -> core
core -X-> CLI
```

`src/fabric_data_framework/cli/` is a leaf presentation package. Removing it may remove the console command but must not break reusable library imports.

## Evidence boundary

Canonical implementation owner:

```text
src/fabric_data_framework/evidence/
```

Responsibilities:

```text
integration_evidence.py       retained evidence vocabulary/spec/result/manifest
integration_checks.py         safe projections from existing provider/runtime outcomes
integration_evidence_merge.py strict staged evidence merge
integration_runner.py         credential-free exact-release preflight
approved_*_runner.py          explicitly authorized environment-facing evidence execution
```

Dependency direction:

```text
semantic/runtime/provider/recovery core
                 ↑
             evidence
                 ↑
                CLI
```

Rules:

```text
1. Evidence proves existing semantic/runtime contracts; it must not redefine them.
2. Provider terminal status alone never becomes semantic PASS unless the underlying contract explicitly requires sufficient framework evidence.
3. Root historical evidence module paths are compatibility aliases only; new implementation belongs under evidence/.
4. Compatibility aliases must resolve to the same canonical module object so legacy monkeypatch/import behavior does not create two implementations.
5. Do not combine evidence extraction with control-plane package extraction in the same refactor slice.
6. Moving files must not promote any live-service evidence claim.
```

## Future control-plane extraction

A future readability slice may group control-plane modules under `control_plane/`, but it must be independently tested and compatibility-preserving. Do not perform that extraction as incidental cleanup during evidence or CLI work.
