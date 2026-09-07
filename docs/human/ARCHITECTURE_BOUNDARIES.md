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
- configuration and runtime abstractions
- Lakehouse/Warehouse integration
- package lifecycle
- lightweight installed-wheel certification

## fabric-customer

Fabric-native realistic source environment/testbed.

Owns synthetic source systems, source data, production-like source changes, deterministic scenario generation, Fabric-native source/landing patterns and expected business truth.

It may depend on Microsoft Fabric capabilities. It must not import or depend on `fabric-data-framework` implementation. It answers **what happened in the source?**, not **how should the target process it?**

## fabric-infra

Owns Fabric infrastructure lifecycle: capacity, workspaces, permissions, infrastructure deployment and automation.

## Two different validations

Framework certification belongs here and answers: **does this built wheel actually work in Fabric?**

Production scenario validation uses `fabric-customer` and answers: **how does an implementation behave against realistic source changes?** Framework v1, v2 and other implementations can consume the same customer bytes and compare with the same business truth.
