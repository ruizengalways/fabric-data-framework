# fabric-data-framework

Reusable Microsoft Fabric data-engineering framework for capture semantics, execution planning, apply semantics, recovery, evidence, and release controls.

This repository is **framework code**, not a business-domain repository. A normal new dataset should be onboarded in `fabric-customer`; you only change this repository when the reusable framework itself needs a new capability.

## Repo model

```text
fabric-data-framework
  reusable Python package, semantics, runtime, adapters, recovery, evidence

fabric-customer
  business datasets, DatasetConfig, Fabric item definitions, bounded extensions

fabric-infra
  optional capacity/workspace/infrastructure lifecycle
```

For an initial enterprise Fabric evaluation, `fabric-data-framework` + `fabric-customer` are enough. `fabric-infra` can be added later without changing the semantic model.

## Mental model

```text
source semantics
  -> capture / delivery
  -> verified capture evidence
  -> Bronze meaning
  -> normalize / DQ / apply
  -> target commit proof / recovery
  -> downstream semantic checkpoint
  -> retained release evidence
```

The important rule is:

```text
capture fidelity is the ceiling of truthful downstream history fidelity
```

An SCD2 target cannot reconstruct history the source/capture path never provided.

## How the framework is consumed

Stable environments should consume an **immutable wheel** from a release, normally through a Fabric Environment custom library.

```text
GitHub release wheel
      |
      v
Fabric Environment -> Publish
      |
      +-> Notebook
      +-> Spark Job Definition
      +-> Pipeline child execution
```

The wheel is not edited inside Fabric. Source code remains in Git.

The CLI is mainly for local development, validation, packaging, deployment/evidence preparation, and approved operational checks. You do not need an interactive Fabric terminal to use the framework at runtime.

## Start here

Human documentation is intentionally small and task-oriented:

- [`docs/human/README.md`](docs/human/README.md) — reading order and document purpose.
- [`docs/human/CONCEPTS.md`](docs/human/CONCEPTS.md) — how to understand the framework.
- [`docs/human/REPOSITORY_GUIDE.md`](docs/human/REPOSITORY_GUIDE.md) — what each important file/folder is for.
- [`docs/human/GETTING_STARTED.md`](docs/human/GETTING_STARTED.md) — install, test, package, and use the framework.
- [`docs/human/DATASET_ONBOARDING.md`](docs/human/DATASET_ONBOARDING.md) — what to do when a new dataset arrives, with concrete examples.
- [`docs/human/OPERATIONS.md`](docs/human/OPERATIONS.md) — release/evidence/operational CLI workflow.

Machine/recovery documentation is separate under [`docs/machine/`](docs/machine/README.md). It contains exact CI baselines, evidence levels, current gaps, recovery invariants, and implementation history needed to continue engineering work safely.

## Local development

```bash
python -m pip install -e '.[dev]'
pytest
```

Useful discovery commands:

```bash
fabric-framework --help
fabric-framework capture-semantic-onboarding-validate --help
fabric-framework integration-run-preflight --help
```

## Release status

- latest public release: `v0.3.0`
- `main` currently contains `0.4.0` development work and is **not yet a public release**

Exact development baseline, CI counts, evidence labels, and remaining release gates belong in `docs/machine/STATE.md`, not in this human landing page.
