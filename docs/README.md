# Documentation

Documentation is split by audience on purpose.

## Human documentation

Use [`human/`](human/README.md) when you want to understand or use the repository.

Human docs answer only these questions:

1. What is this repository responsible for?
2. What does each important file/folder do?
3. How do I install and consume the package?
4. What do I do when a new dataset arrives?
5. Which CLI/runbook do I use for normal operations?
6. How do I perform the first bounded company-Fabric Notebook test and record PASS/FAIL/NOT_RUN without pretending unexecuted checks passed?

For the first corporate Fabric validation, start with [`human/FIRST_FABRIC_NOTEBOOK_TEST.md`](human/FIRST_FABRIC_NOTEBOOK_TEST.md), then use [`human/MANUAL_CERTIFICATION.md`](human/MANUAL_CERTIFICATION.md) to record the observed results.

Human docs avoid PR history, commit SHAs, CI checkpoint history, and implementation archaeology.

## Machine / engineering-recovery documentation

Use [`machine/`](machine/README.md) when continuing framework engineering, auditing evidence, or restoring context in a new AI conversation.

Machine docs contain:

- exact current baseline and CI evidence;
- capability/evidence matrix;
- non-negotiable semantic and recovery invariants;
- implementation/module ownership map;
- merged milestone history;
- current real-service gaps and next engineering boundary.

If human docs and machine docs disagree on exact implementation state, inspect code/tests and repair `machine/` first. Human docs should describe the stable user-facing model, not implementation history.
