# Repository architecture boundaries

## fabric-data-framework

Reusable Fabric data engineering framework.

Owns:

- ingestion semantics
- metadata interpretation
- Bronze and Silver logic
- full refresh / replace safety
- incremental watermark
- SCD1 and SCD2
- CDC / Debezium normalization
- merge/apply logic
- audit and observability
- retries, reconciliation and idempotency
- configuration/runtime abstractions
- Lakehouse/Warehouse integration
- package lifecycle
- lightweight installed-wheel certification

## fabric-customer

Fabric-native realistic source environment/testbed.

Owns synthetic source systems, source data, production-like source changes, deterministic scenario generation, Fabric-native source/landing patterns, expected business truth and workload identity/digests.

It may depend on Microsoft Fabric capabilities. It must not import or depend on `fabric-data-framework` implementation. It answers **what happened in the source?**, not **how should the target process it?**

## implementation/domain repo

A real business project normally has its own consumer repository, for example `fabric-health`.

Owns project-specific:

- DatasetConfig / framework metadata
- source-to-target mapping
- business DQ/reconciliation policy
- execution groups/dependencies
- environment bindings
- Fabric item/deployment content for that project
- implementation-specific adapters and output normalization

This repo may depend on an approved/released framework wheel. It is not `fabric-customer`.

## fabric-infra

Owns Fabric infrastructure lifecycle: capacity, workspaces, permissions, infrastructure deployment and automation.

## Three different validations

Framework certification belongs in `fabric-data-framework` and answers: **does this built wheel actually work in Fabric?**

Implementation project validation belongs with the implementation/domain repo and answers: **is this project's source-controlled framework configuration internally valid?**

Production scenario validation may use `fabric-customer` and answers: **how does an implementation behave against realistic source changes?** Framework v1, v2 and other implementations can consume the same customer workload digest and compare with the same business truth.

## Dependency direction

```text
implementation/domain repo -> approved fabric-data-framework wheel

fabric-customer -X-> fabric-data-framework
fabric-data-framework -X-> fabric-customer
```

A benchmark/orchestration layer may reference both artifacts, but neither core repository should import the other to perform its owned responsibility.
