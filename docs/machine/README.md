# Machine / Engineering Recovery Documentation

Purpose: restore exact framework engineering context without forcing human-facing docs to carry implementation history.

## Read order for a new AI conversation

1. `STATE.md` — exact current baseline, release status, CI/test baseline, real-service gaps, next work.
2. `CONTEXT.md` — non-negotiable semantic/recovery/evidence invariants.
3. `UNIFIED_CERTIFICATION.md` — one-call real-Fabric certification architecture, status/governance boundaries and exact-byte rerun rules.
4. `APPROVED_EVIDENCE.md` — exact approved-run prerequisite, PASS/FAIL, authorization, and merge contracts.
5. `BUSINESS_PATH_EVIDENCE.md` — representative live FULL/REPLACE, SCD1, SCD2, retry, reconciliation proof contract.
6. `RELEASE_READINESS.md` — exact candidate identity, release gate aggregation and fail-closed release rules.
7. `CAPABILITIES.md` — capability -> implementation owner -> evidence level.
8. `IMPLEMENTATION_MAP.md` — code/module ownership and where to change what.
9. `HISTORY.md` — merged milestone history; read only when historical provenance matters.

## File purpose

| File | Machine use |
|---|---|
| `STATE.md` | answer “where are we now and what is next?” |
| `CONTEXT.md` | prevent semantic/recovery regressions after context reset |
| `UNIFIED_CERTIFICATION.md` | restore the minimal Notebook API, approved-run composition, status semantics and non-release boundary |
| `APPROVED_EVIDENCE.md` | restore exact runner/evidence/authorization rules |
| `BUSINESS_PATH_EVIDENCE.md` | restore exact five-gate live path, driver/observer, rerun and cleanup rules |
| `RELEASE_READINESS.md` | prevent candidate/artifact evidence mismatch and release overclaim |
| `CAPABILITIES.md` | prevent CI/reference/live evidence overclaim |
| `IMPLEMENTATION_MAP.md` | find the correct module before editing code |
| `HISTORY.md` | recover why/when a capability entered the framework |

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
- update `CONTEXT.md` if a new invariant or fail-closed boundary was introduced;
- update `UNIFIED_CERTIFICATION.md` if the one-call API, runner ordering, status vocabulary, auto-discovery or authorization boundary changed;
- update `APPROVED_EVIDENCE.md` if an approved-run prerequisite/PASS/authorization contract changed;
- update `BUSINESS_PATH_EVIDENCE.md` if representative live path, scenario/driver/observer, explicit rerun or cleanup rules changed;
- update `RELEASE_READINESS.md` if candidate identity, gate aggregation or exact-artifact rules changed;
- update `CAPABILITIES.md` if a guarantee/evidence level changed;
- update `IMPLEMENTATION_MAP.md` if module ownership/surface changed;
- append `HISTORY.md` only for release-significant merged milestones.

Do not create a new top-level historical runbook for every PR. Integrate stable behavior into the appropriate canonical machine file and keep history compact.

## Documentation structure rule

`docs/` must stay visually simple:

```text
docs/
  README.md
  human/
  machine/
```

Executable/sample configuration belongs under root `examples/`, not under `docs/`.
