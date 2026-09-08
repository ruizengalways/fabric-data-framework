# Documentation

This directory intentionally has a small number of canonical documents. A fact should have **one home**; other documents link to it instead of copying the same explanation.

## I want to...

| Goal | Read |
|---|---|
| Understand the framework and repo boundaries | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Read the source code in end-to-end execution order | [`CODE_READING_GUIDE.md`](CODE_READING_GUIDE.md) |
| Start developing or consume the wheel in Fabric | [`GETTING_STARTED.md`](GETTING_STARTED.md) |
| Create a real project such as `fabric-health` | [`IMPLEMENTATION_PROJECT.md`](IMPLEMENTATION_PROJECT.md) |
| Onboard a new table/source and choose the right semantics | [`DATA_PATTERNS.md`](DATA_PATTERNS.md) |
| Recover a transient/operational Pipeline failure safely | [`OPERATIONS.md`](OPERATIONS.md) |
| Fix bad Bronze/Silver/Gold data, rebuild affected descendants, or deploy v2 safely | [`REPAIR_AND_REBUILD.md`](REPAIR_AND_REBUILD.md) |
| Test/certify exact framework wheel bytes | [`TESTING_AND_CERTIFICATION.md`](TESTING_AND_CERTIFICATION.md) |
| Build/freeze/promote a framework release candidate | [`RELEASE.md`](RELEASE.md) |
| Look up Fabric SQL auth or Pipeline child details | [`reference/`](reference/) |
| Resume framework engineering or inspect current evidence state | [`internal/STATE.md`](internal/STATE.md) |

## Canonical ownership

```text
ARCHITECTURE.md
  architecture + ownership + topology + durable semantic model

CODE_READING_GUIDE.md
  source-code reading order + end-to-end runtime call flow only

GETTING_STARTED.md
  installation/build/Fabric consumption only

IMPLEMENTATION_PROJECT.md
  real consumer project bootstrap only

DATA_PATTERNS.md
  source/capture/Bronze/apply decision rules only

OPERATIONS.md
  transient runtime operations, failure isolation, retry/replay/backfill only

REPAIR_AND_REBUILD.md
  data-correctness repair, dependency impact, rebuild scope, v1/v2 cutover and rollback only

TESTING_AND_CERTIFICATION.md
  test/certification execution and evidence semantics only

RELEASE.md
  candidate/readiness/promotion only

reference/
  narrow technical contracts

internal/
  current state, capability matrix, module ownership
```

Do not create a new top-level document when an existing canonical topic can absorb the information. `REPAIR_AND_REBUILD.md` is the dedicated exception for data-correctness incidents because that lifecycle spans dependency impact, rebuild and consumer cutover and should not be mixed into transient runtime operations. Git history is the historical record; current docs do not maintain PR timelines or superseded candidate walkthroughs.

## Truth order

```text
code + tests + executable schemas
  > internal/STATE.md
  > canonical topic docs
  > examples / local README files
```

If a document disagrees with current behavior, update the canonical document in the same engineering change rather than adding another explanatory file.