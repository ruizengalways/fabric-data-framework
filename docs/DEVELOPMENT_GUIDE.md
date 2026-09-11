# Framework development guide

This is the canonical guide for **changing `fabric-data-framework` safely**. Use [`CODE_READING_GUIDE.md`](CODE_READING_GUIDE.md) to understand the existing runtime first; use this document when you are about to modify framework behavior, add a reusable capability, fix a framework bug, or review another maintainer's PR.

The goal is not to make every change look identical. The goal is to preserve ownership, dependency direction, fail-closed semantics, evidence identity, and testability while keeping changes easy for another engineer to read and extend.

## 1. Before coding: answer five questions

Write down these answers before opening an editor:

```text
1. Is this reusable framework behavior or project-specific behavior?
2. Which module owns the semantic truth?
3. Which invariant must remain true after the change?
4. Which durable identity/state/evidence can change?
5. Which tests prove the behavior rather than only the implementation?
```

If the first question is unclear, stop there and resolve repository ownership before designing an API.

## 2. Decide which repository owns the change

| Change | Correct owner |
|---|---|
| Reusable capture/apply/orchestration/recovery semantic | `fabric-data-framework` |
| Framework package/certification/release mechanics | `fabric-data-framework` |
| Real project's `DatasetConfig`, mappings, DQ, reconciliation configuration | implementation/domain repo |
| Project-specific provider observation adapter or business `CUSTOM` reconciliation logic | implementation/domain repo |
| Physical target version names / logical binding / UAT approval | implementation/domain repo |
| Deterministic production-like source behavior and expected truth | `fabric-customer` |
| Fabric capacity/workspace/permissions | `fabric-infra` / enterprise platform |

A table-specific exception, customer field rename, one-off SQL fragment, or one project's physical item ID is not a framework feature merely because it is technically possible to place it here.

The dependency invariant remains:

```text
implementation/domain repo -> approved fabric-data-framework wheel
fabric-customer -X-> fabric-data-framework
fabric-data-framework -X-> fabric-customer
```

## 3. Find the semantic owner before the call site

Do not start from the first place where a value happens to be used. Start from the layer that owns its meaning.

```text
Dataset semantic config              -> metadata/config.py
capture fidelity/history/delete      -> capture/
target transition semantics          -> apply/
provider-neutral immutable values    -> contracts/
DQ/reconciliation semantics          -> quality/ + reconciliation contracts
plan compilation                     -> execution/plan_compiler.py
dependency scheduling                -> orchestration/
provider transport/auth              -> adapters/
durable operational state            -> control_plane/
retry/replay/rebuild/cutover          -> recovery/
retained release/integration proof    -> evidence/
package/project materialization       -> deployment/
CLI presentation/composition         -> cli/
```

The detailed ownership map is [`internal/IMPLEMENTATION_MAP.md`](internal/IMPLEMENTATION_MAP.md).

## 4. Dependency guardrails

The package is deliberately layered. Preserve this direction unless an architecture change is explicitly justified and tested:

```text
semantic contracts/config
        |
        v
planning + orchestration + runtime
        |
        v
provider adapters / physical execution
        |
        v
operational evidence + deployment
        |
        v
CLI presentation
```

Important rules:

- `contracts/` contains stable immutable cross-layer values; it does not own planners or provider mechanics.
- `execution/plan_compiler.py` compiles plans; `contracts/execution_plan.py` only defines immutable plan values.
- `cli/` is a leaf. Reusable modules must not import CLI presentation code.
- provider `Completed` is an execution fact, never framework semantic success.
- `evidence/` proves existing contracts; it must not become a second semantic authority.
- package-root imports are intentionally unsupported. Import the owning submodule explicitly.
- capture and apply remain orthogonal. A downstream SCD strategy must never upgrade source fidelity.

## 5. Change-impact map

Use this table to identify the minimum mandatory review surface. "Review" means inspect for semantic impact; it does not mean every file must change.

| If you change... | Primary owner | Mandatory review surface |
|---|---|---|
| a `DatasetConfig` field | `metadata/config.py` | onboarding, capabilities, config identity/materialization, compiler, docs/tests |
| capture semantics | `capture/` | onboarding, capabilities, provider adapter evidence, relevant apply assumptions, certification |
| apply semantics | `apply/` | execution coordinator, strategy reconciliation, idempotency/commit rules, tests |
| `ExecutionPlan` structure | `contracts/execution_plan.py` | compiler, parent/child correlation, backends, persistence/evidence, tests |
| plan compilation | `execution/plan_compiler.py` | capability resolution, backends, remote child, plan-hash tests |
| orchestration/dependency scheduling | `orchestration/` | dispatcher/backend contract, fail-at-end behavior, recovery/tests |
| DQ/quarantine | `quality/` | execution gate, immutable evidence lifecycle, replay/recovery, operations docs |
| reconciliation policy/result | `metadata/config.py`, `contracts/reconciliation.py`, `quality/reconciliation/engine.py` | strategy invariants, execution state gate, persistence, provider observation boundary |
| Control Plane state/schema | `control_plane/` | migrations/schema version, repository CAS/transactions, recovery, certification |
| unknown-commit behavior | target-operation contract + `recovery/` | journal, target probe, physical adapter, no-blind-retry tests |
| rebuild/cutover | rebuild/target-version contracts + `recovery/` | impact planning, state cutover, UAT/approval gates, repair docs |
| Fabric/provider adapter | `adapters/` or backend owner | semantic owner, exact provider evidence, auth/secrets, live proof requirement |
| certification/evidence | `certification/` / `evidence/` | candidate identity, secret scan, readiness, release workflow |
| CLI command | `cli/` | reusable owner module, exit/failure semantics, docs; keep logic out of CLI |

## 6. Standard feature-development path

For a reusable framework capability, prefer this sequence:

```text
semantic contract
-> configuration / typed values
-> validation and capability resolution
-> immutable execution-plan impact
-> runtime implementation
-> durable state/evidence impact
-> focused unit/contract tests
-> cross-layer integration tests
-> docs
-> package boundary tests
-> live Fabric proof only when the changed boundary requires it
```

Do not begin by wiring a provider API and infer semantics afterward. Provider mechanics implement an already-defined contract.

### Example: adding or changing a reusable capture semantic

Inspect at least:

```text
src/fabric_data_framework/capture/
src/fabric_data_framework/metadata/config.py
src/fabric_data_framework/capture/onboarding.py
src/fabric_data_framework/metadata/capabilities.py
src/fabric_data_framework/execution/plan_compiler.py
```

Then ask:

```text
What source facts are actually observable?
What ordering/cursor is defensible?
Can delete be observed?
What is the maximum truthful history fidelity?
What Bronze shape is valid?
Which apply strategies are safe?
Which checkpoint may advance, and only after what proof?
```

A new provider API is not evidence that all of these answers are available.

### Example: changing reconciliation

Keep the layers separate:

```text
metadata/config.py
  source-controlled policy semantics

contracts/reconciliation.py
  provider-neutral observation/metric/result values

quality/reconciliation/engine.py
  validation + tolerance + PASS/WARN/FAIL authority

provider/project adapter
  observation collection only

execution/*
  publication/state gating
```

Do not move generic tolerance, severity, or PASS/WARN/FAIL authority into SQL, Spark, Pipeline, or project-specific code.

## 7. Safe extension versus framework modification

Prefer a bounded project extension when the behavior is specific to one domain but can operate behind an existing framework contract. Modify the framework only when the behavior is reusable and the framework must own its semantics.

The framework has a bounded extension registry under:

```text
src/fabric_data_framework/extensions/
```

Treat explicit extension contracts/registry points as the supported extension boundary. Do not make a project depend on arbitrary internal helper functions merely because they are importable.

When reviewing an implementation/domain repo, flag imports of internal framework modules that bypass an explicit contract or intended owner boundary.

## 8. Fail-closed rules to preserve

These are design constraints, not optional style preferences:

```text
provider Completed != framework semantic success
missing required evidence -> fail closed
unknown/ambiguous target commit -> no blind retry
reconciliation-required FAIL -> no state/checkpoint advance
same append identity + different business payload -> fail closed
truthful downstream history <= captured source fidelity
runtime state remains environment-local
quarantine evidence is immutable
Bronze is never manually corrected as an operational shortcut
rebuild != purge
cutover != delete old version
```

If a change weakens one of these, the PR must explicitly change the owning architecture/contract and prove the new rule. Do not introduce a silent fallback.

## 9. Hard-cut policy

Do not add compatibility shims, deprecated aliases, duplicate old paths, or hidden fallback imports by default.

When ownership or an API path changes:

```text
1. choose the canonical owner/path;
2. update all repository callers;
3. update tests and docs;
4. remove the old path completely;
5. let downstream incompatibility be explicit and versioned.
```

A compatibility layer is not a readability improvement; it creates two apparent sources of truth.

## 10. Testing matrix

Choose tests from the semantic blast radius, not from file count.

| Change type | Minimum proof |
|---|---|
| immutable contract/value | construction/validation/serialization tests |
| metadata/config | config validation + deterministic identity/materialization tests |
| capture/apply semantic | focused semantic tests + strategy composition tests |
| execution/orchestration | plan/backend/dispatch + failure/state-gate tests |
| DQ/reconciliation | evaluator + malformed/missing evidence + execution-gate tests |
| control plane/recovery | repository/CAS/transaction + recovery/idempotency tests |
| provider adapter | provider contract tests + semantic-owner tests; live Fabric proof where required |
| packaging/import surface | installed-wheel acceptance |
| certification/release identity | provenance/hash/readiness fail-closed tests |
| docs-only navigation/ownership | documentation consistency/path guards |

Before PR:

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check src tests
```

For packaged runtime changes, CI must also prove the clean installed-wheel boundary. A local editable checkout is not package proof.

## 11. Debug by identities, not by guesses

When a runtime behavior is unclear, trace the durable chain in this order:

```text
pipeline_run_id
-> dataset_run_id
-> effective_config_hash
-> execution_plan_hash
-> provider run identity
-> CaptureReceipt
-> DQ/quarantine outcome
-> reconciliation result
-> target operation evidence
-> DatasetRunAudit / durable child outcome
```

At each hop ask:

```text
Who produced this identity?
Who is allowed to validate it?
What evidence must agree before the next state transition?
```

This is usually faster than stepping through every helper function.

## 12. Read an unfamiliar module efficiently

Use the same reading pattern across the repository:

```text
1. read the nearest README / canonical topic doc;
2. identify immutable dataclasses/enums/protocols first;
3. identify the owner function for the happy path;
4. find fail-closed validation branches;
5. find durable writes/state transitions;
6. inspect direct focused tests;
7. only then read provider-specific mechanics;
8. search callers before changing a signature.
```

Do not start by reading a long provider implementation line-by-line without first knowing which semantic contract it implements.

## 13. Code readability rules for maintainers

Prefer code that makes ownership obvious:

- one semantic concept has one canonical owner;
- typed immutable values cross layer boundaries instead of loose dictionaries when the concept is stable;
- names distinguish entity key, event identity, cursor, checkpoint, plan hash, and provider run identity;
- validation happens close to the semantic owner;
- execution functions state the gate order explicitly;
- provider adapters return evidence/facts rather than semantic verdicts they do not own;
- comments explain invariants and non-obvious constraints, not line-by-line mechanics;
- tests are named around behavior and failure mode, not implementation detail;
- documentation examples use the same terminology as code.

Avoid adding abstractions that only rename a one-line call or hide ownership behind generic `manager`, `service`, `processor`, or `utils` modules.

## 14. Candidate-impact classification

Every merged change must be classified as either executable/package-affecting or bookkeeping-only.

### Packaged-code change

Any change that alters the built wheel bytes invalidates an earlier executable candidate for a future release claim. A new exact main wheel and the required package/certification chain are needed.

### Docs/test-only bookkeeping change

A docs/test-only merge may advance `main` without changing the already-selected executable wheel bytes. It must not rewrite candidate identity or pretend the newer docs commit produced the selected executable artifact.

Never rebuild a release candidate at promotion time. Promotion uses the exact already-proven wheel bytes.

## 15. Pull-request workflow

Use a feature/docs branch; do not develop directly on `main`.

```text
current main
-> focused branch
-> code + tests + canonical docs in the same change
-> PR
-> exact-head CI green
-> merge with expected head SHA
-> verify post-merge main CI
```

A PR is not ready merely because unit tests pass. Review repository ownership, dependency direction, fail-closed behavior, package impact, and documentation ownership too.

## 16. Review checklist

Copy this into a review when useful:

```text
[ ] Correct repository owns the change
[ ] Canonical semantic owner identified
[ ] No project-specific logic leaked into framework
[ ] Capture/apply/provider responsibilities remain separate
[ ] Fail-closed invariants preserved
[ ] Durable identity/state impact assessed
[ ] No compatibility shim / deprecated alias / duplicate old path introduced
[ ] Focused behavior tests added or updated
[ ] Cross-layer/state-gate tests added where required
[ ] Canonical docs updated without duplicating another topic
[ ] Concrete documented repository paths exist
[ ] Installed-wheel impact assessed
[ ] Live Fabric proof requirement assessed
[ ] Candidate invalidation/retention assessed
[ ] Exact PR-head CI is green before merge
```

## 17. Reading and development path for a new maintainer

Recommended onboarding sequence:

```text
Session 1: understand the model
README.md
-> docs/ARCHITECTURE.md
-> docs/DATA_PATTERNS.md

Session 2: trace one dataset through code
-> docs/CODE_READING_GUIDE.md
-> src/fabric_data_framework/README.md
-> focused tests beside the modules you read

Session 3: make the first small framework change
-> docs/DEVELOPMENT_GUIDE.md
-> CONTRIBUTING.md
-> one narrowly owned bug/doc/test change

Session 4: only after runtime understanding
-> docs/TESTING_AND_CERTIFICATION.md
-> docs/RELEASE.md
```

New maintainers should not need to understand candidate SHA plumbing before they can read capture/apply/runtime code. Release internals come after the core runtime mental model.

## Runtime-safety regression rule

Changes to checkpoints, persisted state, hashing, audit evidence, retry/recovery, CDC ordering, or replay storage require failure-path regression tests, not only happy-path tests. Prefer a shared typed codec/redaction primitive over per-feature `default=str` or ad-hoc sanitization. Persisted state updates that can race must use an atomic provider-side predicate/CAS; an application-level read followed by an unconditional write is not sufficient proof.

The CI baseline includes configured Ruff, focused MyPy and package-wide coverage in addition to the existing source and installed-wheel gates. A packaged runtime change always invalidates the previously selected exact candidate even when all source tests pass.
