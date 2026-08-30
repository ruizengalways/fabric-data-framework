# Machine / Engineering Recovery Documentation

Purpose: restore exact framework engineering context without forcing human-facing docs to carry implementation history.

## Read order for a new AI conversation

1. `STATE.md` — exact current baseline, release status, CI/test baseline, real-service gaps, next work.
2. `CONTEXT.md` — non-negotiable semantic/recovery/evidence invariants.
3. `CAPABILITIES.md` — capability -> implementation owner -> evidence level.
4. `IMPLEMENTATION_MAP.md` — code/module ownership and where to change what.
5. `HISTORY.md` — merged milestone history; read only when historical provenance matters.

## Source-of-truth rule

For exact implementation state:

```text
code + tests > machine docs > human docs
```

If code/tests disagree with machine docs, repair machine docs in the same engineering slice.

Human docs intentionally omit PR history, Actions IDs, merge SHAs, test-count progression, and implementation archaeology.

## Update policy

After a meaningful framework slice:

- update `STATE.md` if baseline/gap/next-work changed;
- update `CAPABILITIES.md` if a guarantee/evidence level changed;
- update `CONTEXT.md` if a new invariant or fail-closed boundary was introduced;
- update `IMPLEMENTATION_MAP.md` if module ownership/surface changed;
- append `HISTORY.md` only for release-significant merged milestones.

Do not create a new top-level historical runbook for every PR. Integrate the stable behavior into the appropriate machine document and keep history compact.
