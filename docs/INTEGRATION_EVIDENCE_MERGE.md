# Staged Integration Evidence Merge

Status: Canonical runbook  
Last updated: 2026-08-29

## Purpose

Approved-environment validation is intentionally staged. A read-only Fabric item check may be retained first, production-candidate control-plane certification later, and explicitly authorized Pipeline/Copy/Spark/Warehouse checks later still.

Do not rerun a successful real check merely to create one monolithic manifest.

Instead retain every partial manifest and combine them with a fail-closed merge:

```text
partial item-read manifest
        +
partial control-plane manifest
        +
partial provider manifests
        ↓
integration-evidence-merge
        ↓
merged exact-release manifest
```

The merged manifest is an aggregate view. It does **not** replace retention of the source partial manifests and their referenced external evidence.

## Command

```bash
fabric-framework integration-evidence-merge \
  --spec evidence-spec.json \
  --input evidence/item-read.json \
  --input evidence/control-plane.json \
  --input evidence/pipeline.json \
  --output evidence/merged.json
```

Require every required check to be PASS before writing the output:

```bash
fabric-framework integration-evidence-merge \
  --spec evidence-spec.json \
  --input evidence/item-read.json \
  --input evidence/control-plane.json \
  --input evidence/pipeline.json \
  --output evidence/certified.json \
  --require-certified
```

`--input` is repeatable.

## Exact-spec rule

Every input manifest is validated against the same `IntegrationEvidenceSpec` before any output is written.

The following must match exactly:

```text
evidence schema version
environment
domain
framework version
release hash
check specification
```

A manifest from another release, environment, domain or check list cannot be silently combined.

## Merge semantics

For each check ID in spec order:

```text
all inputs NOT_RUN
  -> merged result = canonical NOT_RUN

one substantive result + any number of NOT_RUN results
  -> retain the substantive result unchanged

same substantive result repeated identically
  -> accept once

two different substantive results
  -> IntegrationEvidenceMergeConflict
```

Substantive statuses are:

```text
PASS
FAIL
EXTERNAL_REQUIRED
```

`NOT_RUN` means absence of evidence for that stage.

## Rerun conflict rule

The merge layer never chooses among contradictory reruns using:

```text
latest timestamp wins
PASS wins
FAIL wins
highest evidence_id wins
```

Example:

```text
item-read-run-A -> PASS with evidence A
item-read-run-B -> PASS with evidence B
```

Even though both are PASS, they are two different substantive results. The merge fails and the operator must explicitly choose which retained rerun manifest belongs in the candidate evidence bundle.

Likewise:

```text
PASS vs FAIL -> conflict
FAIL A vs FAIL B -> conflict
PASS A vs PASS B -> conflict
```

This prevents a later rerun from silently erasing prior failure evidence or replacing a previously approved result.

## Output safety

The CLI performs all merge and optional certification validation before writing `--output`.

Therefore:

```text
merge conflict
exact-spec mismatch
--require-certified failure
```

must not overwrite an existing retained output file.

The existing integration-evidence models continue to reject obvious credential-bearing material. Runtime token/database values are not read by the merge command and are not serialized into the merged manifest.

## Certification

Without `--require-certified`, a partial merged manifest is valid and may still contain required checks in `NOT_RUN`, `FAIL` or `EXTERNAL_REQUIRED` state.

With `--require-certified`, the command fails unless every required check is exactly `PASS`.

The command prints only:

```text
integration_evidence_id
manifest_hash
certified
```

after a successful write.

## Retention rule

Retain:

```text
exact IntegrationEvidenceSpec
all source partial manifests
merged manifest(s)
all evidence_references targets
exact release artifact / release_hash
approved runner/preflight artifacts where required
```

A merged manifest alone is not a replacement for its source evidence chain.

## Relationship to real provider proof

This merge capability is a credential-safe evidence aggregation contract. Deterministic CI proving the merge algorithm is **not** evidence that any Fabric, SQL, Kafka or Delta service check actually ran.

Use the existing evidence vocabulary:

```text
IMPLEMENTED + CI PROVEN EVIDENCE MERGE CONTRACT
```

Only retained approved real checks can elevate the corresponding provider capability to its real-service evidence label.
