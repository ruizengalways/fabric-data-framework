# 0.4 release-candidate readiness

`0.4.0` is still development source. A green build, retained wheel, installed-wheel smoke or Fabric-reported `Completed` state is not enough to publish it.

## 1. Current ownership model

Release governance belongs to `fabric-data-framework`.

```text
fabric-data-framework
  exact framework wheel + certification + release evidence

fabric-customer
  independent framework-agnostic realistic source workload
  optional for end-to-end scenario evidence, not release-input ownership

implementation/domain repo
  project-specific framework config/adapters
```

Historical code/evidence field names containing `customer`, such as `customer.compatibility`, `customer-inputs`, or domain release fields, are compatibility names. They do not make the current `fabric-customer` simulator responsible for framework certification or candidate production inputs.

## 2. Freeze rule

No exact 0.4 candidate is frozen yet.

When one successful main-CI wheel is explicitly selected as the release candidate:

```text
freeze exact Git SHA + wheel SHA256 + main CI identity
-> stop feature work on those candidate bytes
-> only release/certification/evidence defects may create a replacement candidate
-> any executable code change means a new candidate and new real-Fabric evidence
```

A documentation-only commit does not change the Framework package source/payload, but CI may still emit a newly built wheel artifact with its own Git/CANDIDATE identity. `docs/machine/STATE.md` therefore records the exact executable artifact selected for the next Fabric run separately from repository documentation HEAD.

## 3. Required lifecycle

```text
source CI
  -> exact main wheel artifact
  -> clean installed-wheel acceptance
  -> exact wheel identity retained
  -> real Fabric bounded certification
  -> environment-dependent Control Plane / Pipeline / Copy / Spark / Warehouse evidence as required
  -> representative live business-path evidence
  -> strict release-readiness aggregation
  -> explicit candidate selection/freeze
  -> exact-byte promotion without rebuilding the wheel
```

There is no release-time wheel rebuild.

## 4. Current executable baseline

The exact Framework artifact currently selected as the next real-Fabric baseline is:

```text
framework Git SHA       38741777955ffdb59cf9bdeea361bdd6651c5ee2
main framework CI       34091549404
Python 3.11             PASS
Python 3.13             PASS
wheel build             PASS
readiness contract      PASS (fail-closed / release not ready)
installed-wheel run     34091549510 PASS
wheel filename          fabric_data_framework-0.4.0-py3-none-any.whl
wheel SHA256            201947410f75b88596af897c78d6fd056a9a3040fbec4d83d85b5439d7077cf0
wheel artifact ID       10006992444
artifact ZIP digest     sha256:7f418fe8d099d5a0b3cd1fffa656d8217496fea4845259064d9cd88d639d78ec
```

The readiness artifact for those bytes is fail-closed and still reports the required live/evidence blockers. Therefore these bytes are **candidate-capable**, not selected/frozen/release-authorized.

## 5. Exact identity is non-negotiable

The candidate identity is the exact Framework wheel SHA256 plus the Git/main-CI provenance in `CANDIDATE.json`.

The uploaded GitHub artifact ZIP digest is useful transport evidence but is not the framework wheel identity.

Installed-wheel certification also verifies that the active installed package payload matches the candidate wheel package bytes. A source checkout or a different wheel with the same version string does not satisfy this gate.

## 6. Real Fabric certification

Real Fabric execution for the current exact wheel has not yet been retained.

The minimum next environment gate is:

```text
exact candidate wheel
-> install in dedicated Fabric DEV Environment
-> publish/restart runtime
-> certify_installed(...)
-> exact candidate identity PASS
-> Lakehouse bounded checks PASS
```

Only after actual execution may those checks be labeled PASS. Until then:

```text
FABRIC CERTIFICATION REQUIRED
```

Environment-dependent integration checks may additionally require dedicated:

- Fabric SQL Database Control Plane;
- Pipeline / Copy / Spark provider items;
- Warehouse;
- explicit runtime credentials/identity;
- separately approved fault/session-termination authority where applicable.

No local/CI result can manufacture those PASS states.

## 7. Representative workload evidence

`fabric-customer` can now generate a deterministic framework-neutral workload with:

```text
SHA256SUMS
WORKLOAD.json
workload_digest
```

This is useful for implementation regression/business-path evidence:

```text
same verified customer workload_digest
  -> framework v1 implementation
  -> framework v2 implementation
  -> normalize business outputs
  -> compare each against the same expected truth
```

The customer workload digest is **not** the framework wheel SHA and must never replace candidate identity.

For any scenario evidence retained for release governance, record both identities independently:

```text
framework wheel SHA256
customer workload_digest
implementation/domain Git SHA when applicable
Fabric environment/workspace identity
```

## 8. Legacy readiness gate names

Current readiness code may still expose historical names such as:

```text
customer.compatibility
customer-inputs
```

Treat them as deprecated compatibility labels for release/integration contracts. New docs and new automation should use framework/integration terminology. Renaming serialized public fields should happen only through an explicit compatibility/deprecation migration, not as an incidental documentation change.

## 9. Release authorization

Certification runners keep:

```text
release_authorized = false
```

They do not freeze a candidate, create `v0.4.0`, or authorize promotion.

Release readiness must fail closed until all required exact-byte evidence is present and consistent. Candidate selection/freeze and promotion are separate explicit governance actions.

## 10. Current state

```text
public release                   v0.3.0
0.4 source                       development / unreleased
next Fabric artifact baseline    38741777955ffdb59cf9bdeea361bdd6651c5ee2
source/main CI                   PASS
installed-wheel acceptance       PASS
real Fabric exact-wheel evidence FABRIC CERTIFICATION REQUIRED
candidate frozen                 no
release authorized               no
immutable v0.4.0                 not published
```

The next release-relevant work is real Fabric execution for an explicitly selected exact wheel, not rebuilding the customer-owned certification system that was removed by the repository-boundary refactor.
