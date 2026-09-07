# Documentation

This directory intentionally has a small number of canonical documents. A fact should have **one home**; other documents link to it instead of copying the same explanation.

## I want to...

| Goal | Read |
|---|---|
| Understand the framework and repo boundaries | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Start developing or consume the wheel in Fabric | [`GETTING_STARTED.md`](GETTING_STARTED.md) |
| Create a real project such as `fabric-health` | [`IMPLEMENTATION_PROJECT.md`](IMPLEMENTATION_PROJECT.md) |
| Onboard a new table/source and choose the right semantics | [`DATA_PATTERNS.md`](DATA_PATTERNS.md) |
| Recover a failed business Pipeline safely | [`OPERATIONS.md`](OPERATIONS.md) |
| Test/certify exact framework wheel bytes | [`TESTING_AND_CERTIFICATION.md`](TESTING_AND_CERTIFICATION.md) |
| Build/freeze/promote a framework release candidate | [`RELEASE.md`](RELEASE.md) |
| Look up Fabric SQL auth or Pipeline child details | [`reference/`](reference/) |
| Resume framework engineering or inspect current evidence state | [`internal/STATE.md`](internal/STATE.md) |

## Canonical ownership

```text
ARCHITECTURE.md
  architecture + ownership + topology + durable semantic model

GETTING_STARTED.md
  installation/build/Fabric consumption only

IMPLEMENTATION_PROJECT.md
  real consumer project bootstrap only

DATA_PATTERNS.md
  source/capture/Bronze/apply decision rules only

OPERATIONS.md
  normal runtime operations and recovery only

TESTING_AND_CERTIFICATION.md
  test/certification execution and evidence semantics only

RELEASE.md
  candidate/readiness/promotion only

reference/
  narrow technical contracts

internal/
  current state, capability matrix, module ownership
```

Do not create a new top-level document when an existing canonical topic can absorb the information. Git history is the historical record; current docs do not maintain PR timelines or superseded candidate walkthroughs.

## Truth order

```text
code + tests + executable schemas
  > internal/STATE.md
  > canonical topic docs
  > examples / local README files
```

If a document disagrees with current behavior, update the canonical document in the same engineering change rather than adding another explanatory file.
