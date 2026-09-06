# Documentation

Documentation is split by audience.

## Human docs

Start with `human/README.md` when learning or using the Framework.

Human docs cover:

- architecture and concepts;
- new-project bootstrap and dataset onboarding;
- normal Pipeline operations/recovery;
- Fabric-native SQL authentication;
- current Framework developer certification;
- release-candidate operating rules.

They intentionally do not preserve superseded candidate identities, old Fabric test walkthroughs, PR timelines or CI archaeology.

## Machine / engineering recovery docs

Start with `machine/STATE.md` when continuing Framework engineering or opening a new AI conversation.

Use this minimal read order:

```text
1. machine/STATE.md
2. machine/ENTERPRISE_TOPOLOGY.md
3. machine/UNIFIED_CERTIFICATION.md
```

Open other machine contracts only when the task needs them.

`machine/STATE.md` contains current executable identity, current Customer binding, real-evidence state, release gates and the exact next boundary. Git history is the historical record; do not duplicate it into current-state docs.

## Truth rule

```text
code + tests > machine/STATE.md > task-specific machine docs > human docs
```

If these disagree, fix the current-state docs in the same engineering slice rather than adding another recovery checkpoint file.
