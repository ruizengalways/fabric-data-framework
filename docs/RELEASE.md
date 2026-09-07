# Release

This is the canonical framework release runbook. It describes candidate identity, evidence aggregation, freeze and immutable promotion. Current exact status belongs only in [`internal/STATE.md`](internal/STATE.md).

## 1. Release is a separate gate

```text
source CI
!= installed-wheel acceptance
!= real Fabric certification
!= release readiness
!= release authorization
```

A green build is necessary but not sufficient to publish a framework release.

## 2. Framework-owned release chain

Framework release governance is self-contained in `fabric-data-framework`.

```text
main/source CI
-> exact framework wheel artifact
-> installed-wheel acceptance
-> framework-owned integration-input artifact
-> real Fabric integration/business-path evidence as required
-> release proof aggregation
-> candidate certification
-> explicit candidate freeze/authorization
-> exact-byte release promotion
```

`fabric-customer` is not a producer or dependency in the framework release chain. It may independently supply realistic source workloads for implementation regression testing.

## 3. Candidate identity

The release/certification chain binds two independent identities:

```text
framework_artifact_sha256
  exact candidate framework wheel bytes

integration_inputs_hash
  exact framework-owned integration configuration/recipe bundle
```

Both identities must remain consistent across integration evidence, business-path evidence and release-readiness aggregation.

Do not replace the framework wheel SHA with:

```text
version string
GitHub artifact ZIP digest
customer workload_digest
implementation/domain release hash
```

Those may be useful provenance in other lifecycles, but they are not the framework executable identity.

## 4. Candidate freeze rule

When one successful main artifact is explicitly selected:

```text
record exact source Git SHA
record main CI/run provenance
record exact inner wheel SHA256
record exact integration_inputs_hash when integration evidence is required
stop feature changes to those candidate bytes
```

Any executable framework change creates a new candidate and invalidates previous exact-byte release evidence for the old wheel.

A docs-only change may not alter package payload, but release governance still follows the exact artifact selected by the candidate manifest rather than guessing equivalence.

## 5. Build once, promote the same bytes

There must be no release-time rebuild of the Python wheel.

Correct flow:

```text
CI builds candidate wheel
-> certify that exact wheel
-> readiness binds that exact SHA256
-> publish/promote the same wheel bytes
```

Rebuilding at release time creates a different artifact boundary even when the version string is unchanged.

## 6. Evidence sources

Release readiness may require evidence from different owners/stages, for example:

```text
source.tests
wheel.integrity
integration.inputs
bounded real-Fabric certification
Control Plane / Pipeline / Copy / Spark / Warehouse checks
representative business paths
enterprise/platform external evidence when policy requires it
```

The exact gate set is executable policy under `release/<version>/readiness-spec.json` and packaged certification resources. The Markdown document does not duplicate that JSON matrix.

## 7. Strict evidence aggregation

Evidence merging is fail-closed.

Do not use:

```text
latest wins
PASS wins
FAIL wins
```

Substantively contradictory evidence for the same candidate/check must be treated as a conflict until intentionally resolved through a new explicit run/evidence chain.

Required candidate identities must match across merged proof sources.

## 8. Real Fabric evidence

Local/CI contract tests cannot manufacture real Fabric PASS states.

For capabilities requiring Fabric proof, the selected exact wheel must actually execute against approved resources and retain evidence for the exact candidate identity.

Until then:

```text
FABRIC CERTIFICATION REQUIRED
```

See [`TESTING_AND_CERTIFICATION.md`](TESTING_AND_CERTIFICATION.md).

## 9. Representative business paths

Framework candidate certification includes representative live semantic paths when required by the release policy:

```text
full.replace
watermark.scd1
watermark.scd2
retry.idempotency
reconciliation.fail_closed
```

These paths are framework-owned certification fixtures/recipes and use the same `framework_artifact_sha256 + integration_inputs_hash` identity chain.

## 10. External enterprise controls

Some production-readiness controls cannot be inferred from a successful SQL/Fabric call, for example:

```text
IAM review
network controls
backup/restore
HA/DR
monitoring/alerting
retention/governance
```

If release policy requires them, retain explicit external evidence references. Missing evidence is blocked/not-ready, not automatically PASS.

## 11. Release authorization

Certification runners do not publish a release and should retain:

```text
release_authorized = false
```

Candidate selection/freeze and promotion are explicit governance actions after readiness is satisfied.

## 12. Public version state

Do not copy exact current candidate SHAs/run IDs into this runbook. Those values change frequently and belong in [`internal/STATE.md`](internal/STATE.md).

The public/release history is represented by immutable Git tags/releases and Git history; this document only describes the current release process.
