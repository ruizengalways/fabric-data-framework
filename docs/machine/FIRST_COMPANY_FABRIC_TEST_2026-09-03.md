# First Company Fabric Bounded Test — 2026-09-03

Status: **EXECUTED — BOUNDED NOTEBOOK CHECKS PASSED**

This checkpoint records the first real company Microsoft Fabric DEV execution of the bounded Notebook/manual-certification lane. It is a factual execution summary only. It does **not** select/freeze a release candidate, authorize Framework 0.4 release, prove privileged Warehouse recovery, or replace the strict evidence-based release lane.

## Exact Framework artifact tested

```text
framework-ci main run          33381666892
candidate_git_sha              303683729c4915d78200d463a6def01c8de9eae6
artifact ID                    9753976212
wheel filename                 fabric_data_framework-0.4.0-py3-none-any.whl
wheel SHA256                   0638c95c19ebcc43ec4ec462b7f960a164209874223517e3f74b951264b0eaf6
artifact ZIP digest            sha256:cd790310378d8aa11e950b004c9183125c52bbbc0ddf484d7749faa675e7171b
```

The Notebook verified the actual Fabric-resident wheel bytes against `CANDIDATE.json`, verified installed version `0.4.0`, and matched the expected Framework Git SHA and workflow run ID before semantic testing.

## Environment boundary

The test ran in an approved company **DEV** Fabric workspace with an attached disposable/default Lakehouse. A dedicated test Warehouse exists in the DEV workspace, but session-termination/fault-injection authorization was not confirmed and the full approved Warehouse evidence-runner prerequisites were not assembled for this bounded lane.

The inline wheel installation completed successfully. A post-install `%pip check` surfaced environment-level dependency conflicts involving `fsspec-wrapper`/`PyJWT` and `nni`/`filelock`. A pre-install `%pip check` was not captured, so this checkpoint does not classify those conflicts as pre-existing. No corporate Fabric packages or security controls were modified to suppress the observations. Framework identity/import and all executed bounded checks below still passed.

## Actual executed results

```text
identity                           PASS
lakehouse.smoke                    PASS
full.replace                       PASS
watermark.scd1                     PASS
watermark.scd2                     PASS
retry.idempotency                  PASS
reconciliation.fail_closed         PASS
warehouse.commit                   NOT_RUN
warehouse.ambiguous_commit         NOT_RUN
```

`reconciliation.fail_closed = PASS` means the deliberately forced underlying reconciliation result was `FAIL` and Framework returned `blocks_state_advance=true`, as required.

The Warehouse checks are `NOT_RUN`, not PASS. The dedicated DEV Warehouse was not used as a substitute for the Framework approved Warehouse evidence runner, and no session termination/fault injection was attempted without explicit authorization.

## Manual certification record

The Framework Notebook form recorded only observed results. The generated record reported:

```text
framework_version      0.4.0
status                 CERTIFIED
mode                   NOTEBOOK
candidate_git_sha      303683729c4915d78200d463a6def01c8de9eae6
artifact_sha256        0638c95c19ebcc43ec4ec462b7f960a164209874223517e3f74b951264b0eaf6
environment            DEV
missing_fields         [notebook_reference]
admin_override         false
override_reason        null
release_authorized     false
```

Retained PASS checks in the record:

```text
lakehouse.smoke
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

The two `NOT_RUN` Warehouse dropdowns are intentionally omitted from the retained check tuple by the current Notebook UI contract; this checkpoint keeps their `NOT_RUN` truth explicit.

A final sanity inspection showed `operator`, `notebook_reference`, `notes`, and `override_reason` empty/null and no password, token, connection string, SAS/access key, bearer token, or other secret-bearing evidence text in the record.

The raw `manual-certification.json` was created in the attached company Fabric DEV Lakehouse. Its raw contents are **not** committed to this public repository; this source-controlled checkpoint retains only the non-secret execution summary above.

## Evidence-class boundary

This run proves the exact tested wheel can be installed and exercised successfully for the bounded Notebook/Lakehouse + Framework semantic checks listed above in a real company Fabric DEV environment.

It does **not** prove or change any of the following:

```text
candidate_status                         not_frozen
release_allowed                          false
Framework 0.4.0                          unreleased
warehouse.commit                         NOT_RUN
warehouse.ambiguous_commit               NOT_RUN
production-eligible control-plane proof  not produced
five live business-path proofs           not retained
strict release readiness                 false / blockers remain
Customer production Framework pin        fabric-data-framework==0.3.0
```

Do not label this checkpoint as `FABRIC WAREHOUSE PROVEN`, `PRODUCTION DB PROVEN`, or evidence-based `RELEASE PROVEN`.

## Next governance step

First merge this documentation checkpoint and verify CI/main. After that, the next release-oriented work is to satisfy the real evidence prerequisites documented in `STATE.md`: reviewed real control-plane evidence/binding and an explicitly approved reachable Warehouse ambiguous-COMMIT fault controller. Only after those prerequisites are genuinely ready should one NEW exact Framework candidate be explicitly selected/frozen for the strict evidence-based release chain.
