# 人读文档

这里放正常开发、接新数据、部署和运维时真正需要看的文档。旧 PR、旧 candidate、旧 Fabric 测试记录不放在默认阅读路径里；需要考古时直接看 Git history。

## 推荐阅读顺序

1. `ARCHITECTURE_BOUNDARIES.md` — 先看 repo ownership，避免把 simulator、implementation 和 certification 混在一起。
2. `CONCEPTS.md` — Framework 的数据语义和整体运行模型。
3. `ENTERPRISE_FABRIC_ARCHITECTURE.md` — DEV/UAT/PROD canonical Fabric 架构。
4. `GETTING_STARTED.md` — 安装、source tests、打 wheel、Fabric 中消费 package。
5. `IMPLEMENTATION_PROJECT_BOOTSTRAP.md` — 新 business/domain implementation repo 怎么初始化。
6. `DATASET_ONBOARDING.md` — 新表/新源如何选择 capture、Bronze、Silver 策略。
7. `PIPELINE_OPERATIONS_AND_RECOVERY.md` — 多表 Pipeline 正常运维、fail-at-end 和恢复策略。
8. `CERTIFICATION_LIFECYCLE.md` — source test、installed-wheel acceptance、real Fabric certification 的硬边界。
9. `FRAMEWORK_DEVELOPER_CERTIFICATION.md` — Framework 开发者 certification 主 runbook。
10. `FABRIC_NATIVE_SQL_AUTH.md` — Fabric-native Microsoft Entra SQL 认证。
11. `ONE_CALL_CERTIFICATION_RUNTIME.md` / `UNIFIED_FABRIC_CERTIFICATION.md` — environment-dependent integration runner contract。
12. `RELEASE_CANDIDATE.md` — exact-candidate evidence 和 release gate。

如果要恢复**当前 exact main wheel、CI、真实 Fabric evidence 状态和下一步**，不要从旧 runbook 猜，直接看：

```text
docs/machine/STATE.md
```

## 四个职责，不是三个代码库强行装所有东西

```text
fabric-infra
  Fabric capacity/workspace/permission infrastructure lifecycle

fabric-customer
  Fabric-native, framework-agnostic source-system simulator
  deterministic source facts + expected business truth

fabric-data-framework
  reusable processing framework + installed-wheel certification

implementation/domain repo（每个真实项目独立）
  DatasetConfig / source-to-target mapping / environment bindings / deployment content
  可以依赖 released framework wheel
```

`fabric-customer` **不是** implementation/domain repo。它不能因为某个真实项目需要 SCD2、watermark 或 framework adapter 就重新依赖 Framework。

## 企业环境 topology

DEV、UAT、PROD 从一开始就使用同一种逻辑架构：

```text
Fabric SQL Database = Framework operational Control Plane
Lakehouse / OneLake = Bronze / Silver / Gold business data + quarantine detail
Fabric Warehouse    = optional SQL-first Gold / dimensional serving
```

Canonical Control Plane profile：

```text
fabric_sql_database_v1
```

不要在 DEV 把 control state 放 Lakehouse，到 UAT/PROD 再换 SQL Database。CI/CD promote code、schema、DatasetConfig、execution policy 和 implementation-owned Fabric definitions；runtime rows、watermarks、credentials、business data 和 physical UUIDs 保持环境本地化。

## 正常业务 Pipeline 出错

先看：

```text
docs/human/PIPELINE_OPERATIONS_AND_RECOVERY.md
```

默认语义：

```text
one dataset FAIL
-> independent siblings continue
-> dependents BLOCKED
-> runnable work reaches terminal state
-> parent Pipeline fails at the end
```

不要默认整批重跑。只有明确 retryable 的 transient failure 才做 bounded retry；unknown commit 先 reconcile；DQ 先修数据/rule；dependency failure 先恢复 upstream。

## Framework certification 从哪里开始

Framework 开发者从：

```text
docs/human/CERTIFICATION_LIFECYCLE.md
docs/human/FRAMEWORK_DEVELOPER_CERTIFICATION.md
```

开始。

当前正确链路是：

```text
source tests
-> build exact wheel
-> clean install
-> installed package byte attestation
-> framework-owned semantic smoke
-> real Fabric bounded/unified certification
-> retained evidence
```

真实 Fabric certification 也属于 `fabric-data-framework`。`fabric-customer` 只提供可选的独立 production-like source workload；它不是 certification bootstrap owner。

Notebook 最小入口：

```python
from fabric_data_framework.certification import certify_installed, print_certification_summary

report = certify_installed(
    spark=spark,
    certification_root="/lakehouse/default/Files/framework_cert",
)
print_certification_summary(report)
```

## 通常应该改哪个 repo

- Framework 缺少通用能力：改 `fabric-data-framework`。
- Source simulator 缺少真实 source behavior/scenario：改 `fabric-customer`。
- 某个真实业务项目来了新表/新源：改该项目自己的 implementation/domain repo。
- Capacity/workspace/permission 基础设施：改 `fabric-infra`。

## 最重要的原则

```text
先描述数据语义，再选执行引擎。
```

先确认拿到的是 full snapshot、watermark rows、net changes、ordered changes 还是 business events；delete 能否看到；Bronze 要保存 current/snapshot/event 哪种形态；Silver 要 SCD1 还是 SCD2；然后再决定 Copy/Pipeline/Spark 等物理实现。
