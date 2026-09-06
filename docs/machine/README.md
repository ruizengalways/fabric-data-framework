# Machine / Engineering Recovery Documentation

Use this directory when continuing Framework engineering, restoring an AI conversation, or auditing release evidence.

## New conversation read order

Start with only:

```text
1. STATE.md
2. ENTERPRISE_TOPOLOGY.md
3. UNIFIED_CERTIFICATION.md
```

Then open a task-specific contract only when needed:

- `CONTEXT.md` — semantic/recovery invariants.
- `APPROVED_EVIDENCE.md` — approved-run evidence and authorization rules.
- `BUSINESS_PATH_EVIDENCE.md` — five representative live business-path gates.
- `RELEASE_READINESS.md` — exact candidate and release aggregation rules.
- `CAPABILITIES.md` — capability/evidence matrix.
- `IMPLEMENTATION_MAP.md` — module ownership.

`STATE.md` is the only current-state recovery checkpoint. Do not add PR-by-PR checkpoint files or duplicate historical timelines here.

## Source-of-truth rule

```text
code + tests > STATE.md > task-specific machine docs > human docs
```

If code/tests disagree with `STATE.md`, repair `STATE.md` in the same engineering slice.

Git history already stores old implementation history. Current machine docs should contain only information required to understand current behavior, current evidence boundaries and the next action.

## Update policy

Update:

- `STATE.md` when executable identity, Customer binding, real evidence, release status or the next boundary changes;
- `ENTERPRISE_TOPOLOGY.md` when environment/storage/promotion architecture changes;
- `CONTEXT.md` when a semantic or fail-closed invariant changes;
- `UNIFIED_CERTIFICATION.md` when certification execution/status/auth contracts change;
- evidence/readiness docs when their actual contracts change;
- `CAPABILITIES.md` / `IMPLEMENTATION_MAP.md` when capability level or code ownership changes.

Do not create a historical runbook for each PR. Do not keep old candidate identities in the current recovery path after they are superseded.
