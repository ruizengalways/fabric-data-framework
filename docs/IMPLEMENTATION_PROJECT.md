# Implementation project

This is the canonical runbook for a real framework-consuming business/domain repository such as `fabric-health`. It is not the `fabric-customer` simulator.

## 1. Ownership

```text
fabric-data-framework
  reusable framework + framework certification

fabric-customer
  independent source-system simulator/testbed
  no framework dependency

fabric-health / fabric-finance / ...
  real implementation/domain repo
  may depend on an approved/released framework wheel
```

The implementation repo owns:

```text
DatasetConfig
source-to-target mappings
business DQ / reconciliation policy
execution groups / dependencies
environment bindings
project Fabric item/deployment definitions
project-specific bounded adapters
```

## 2. Where the CLI runs

`fabric-framework` normally runs on a developer machine, jumpbox, CI/CD runner or controlled operator environment. Daily Fabric Pipelines do not require a human to open a terminal in Fabric.

For a consumer project, install an approved/released wheel into a normal Python environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install fabric-data-framework
```

Use editable install only while developing the framework itself.

## 3. Initialize the repository

```bash
fabric-framework project-init ./fabric-health --domain health
cd fabric-health
```

Typical skeleton:

```text
fabric-health/
├─ fabric-project.json
├─ README.md
├─ config/
│  ├─ datasets/
│  ├─ capture/
│  ├─ execution-groups/
│  └─ environments/
├─ deploy/
├─ docs/
├─ src/
└─ tests/
```

For an existing repository:

```bash
fabric-framework project-init . --domain health --allow-existing
```

The initializer fills missing scaffold only; it must not overwrite existing business content.

## 4. Keep one business domain together

A domain with 100 tables can normally remain one repo even when the technical patterns differ:

```text
50 full snapshot
20 watermark + SCD2
20 watermark + SCD1
10 CDC
```

Do not split repositories by ingestion technology alone. Prefer business ownership, release cadence, access boundary and data-product boundary as repo boundaries.

Technical differences belong in each dataset contract and execution-group policy.

## 5. Onboard each dataset from source facts

Before writing config, identify:

- source delivery shape;
- stable key;
- ordering/watermark evidence;
- delete visibility;
- late/back-dated behavior;
- provider collapse/net-change behavior;
- current-state vs history requirement and required fidelity.

Then choose capture/Bronze/apply semantics using [`DATA_PATTERNS.md`](DATA_PATTERNS.md).

## 6. Static validation

```bash
fabric-framework project-validate .
```

This validates source-controlled project contracts. It does not prove:

```text
source connectivity
Fabric permissions
Pipeline/Copy/Spark execution
real target commit
real environment configuration
```

Those require environment execution.

## 7. Source-controlled vs environment-local values

Commit logical definitions:

```text
DatasetConfig
execution groups
DQ/reconciliation rules
logical item names/templates
non-secret binding declarations
```

Keep these environment-local:

```text
credentials/tokens
physical Fabric UUIDs when resolved at runtime/deploy time
watermarks/checkpoints
pipeline/dataset run rows
business data
```

DEV/UAT/PROD should use the same logical architecture even though physical IDs differ.

## 8. Use the independent source simulator when useful

`fabric-customer` can materialize deterministic source facts and expected truth for regression tests:

```text
fabric-customer verified workload
  -> implementation-owned landing
  -> fabric-health framework config/runtime
  -> normalized business output
  -> compare with expected truth
```

For comparisons between framework versions, keep the same verified `workload_digest` so both implementations consume identical source bytes.

The simulator workload identity is not the framework wheel identity and is not part of framework certification.

## 9. Fabric delivery sequence

Recommended project flow:

```text
approved framework wheel
-> project-validate
-> deploy/publish DEV environment and project items
-> resolve DEV physical bindings and credentials
-> source connectivity / test workload
-> DEV end-to-end validation
-> UAT promotion
-> PROD promotion
```

Framework certification is separate: it proves the framework artifact. Project validation proves the implementation config. End-to-end project validation proves the combination in a real environment.

## 10. When the project should request a framework enhancement

Move behavior into `fabric-data-framework` only when it is genuinely reusable across domains.

Good framework candidates:

```text
new provider-neutral delete semantic
new bounded cursor/checkpoint contract
new generic apply/recovery primitive
```

Keep project-specific behavior local:

```text
special field rename
one source API payload translation
one table exception
business-specific SQL/mapping
```
