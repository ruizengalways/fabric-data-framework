# 人读文档

这里放正常开发、接新数据、部署和运维时真正需要看的文档。旧 PR、旧 candidate、旧 Fabric 测试记录不放在默认阅读路径里；需要考古时直接看 Git history。

## 推荐阅读顺序

1. `CONCEPTS.md` — Framework 的边界、数据语义和整体运行模型。
2. `ENTERPRISE_FABRIC_ARCHITECTURE.md` — DEV/UAT/PROD canonical Fabric 架构。
3. `GETTING_STARTED.md` — 安装、测试、打 wheel、Fabric 中消费 package。
4. `CUSTOMER_PROJECT_BOOTSTRAP.md` — 新 domain/customer repo 怎么初始化。
5. `DATASET_ONBOARDING.md` — 新表/新源如何选择 capture、Bronze、Silver 策略。
6. `PIPELINE_OPERATIONS_AND_RECOVERY.md` — 多表 Pipeline 正常运维、fail-at-end 和恢复策略。
7. `FABRIC_NATIVE_SQL_AUTH.md` — Fabric-native Microsoft Entra SQL 认证。
8. `FRAMEWORK_DEVELOPER_CERTIFICATION.md` — Framework 开发者当前 certification 主 runbook。
9. `ONE_CALL_CERTIFICATION_RUNTIME.md` — one-call runtime / Control Plane bootstrap contract。
10. `UNIFIED_FABRIC_CERTIFICATION.md` — unified certification runner contract。
11. `RELEASE_CANDIDATE.md` — exact-candidate evidence 和 release gate。

如果要恢复**当前 exact executable、Customer main、真实 Fabric evidence 状态和下一步**，不要从人读文档猜，直接看：

```text
docs/machine/STATE.md
```

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

不要在 DEV 把 control state 放 Lakehouse，到 UAT/PROD 再换 SQL Database。CI/CD promote code、schema、DatasetConfig、execution policy 和 Fabric item definitions；runtime rows、watermarks、credentials、business data 和 physical UUIDs 保持环境本地化。

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
docs/human/FRAMEWORK_DEVELOPER_CERTIFICATION.md
```

开始。当前默认认证方向是 exact artifact + Fabric-native identity + unified runner，不再维护旧 candidate 的逐 cell/manual 教程作为默认路径。

最小 bounded 入口仍是：

```python
from fabric_data_framework.certification import certify, print_certification_summary

report = certify(spark=spark)
print_certification_summary(report)
```

完整 company-Fabric 操作步骤由 `fabric-customer/docs/runbooks/TEST_FRAMEWORK_IN_COMPANY_FABRIC.md` 持有，因为具体 Fabric item deployment、Customer inputs 和环境 binding 属于 Customer/reference domain repo。

## 通常应该改哪个 repo

新业务表、新数据源、新 domain：通常改 `fabric-customer`。

只有缺少通用能力时才改 `fabric-data-framework`，例如新的 capture semantics、apply strategy、provider transport、recovery/evidence contract 或 reusable CLI/runtime capability。

Capacity/workspace/基础设施生命周期属于 `fabric-infra`。

## 最重要的原则

```text
先描述数据语义，再选执行引擎。
```

先确认拿到的是 full snapshot、watermark rows、net changes、ordered changes 还是 business events；delete 能否看到；Bronze 要保存 current/snapshot/event 哪种形态；Silver 要 SCD1 还是 SCD2；然后再决定 Copy/Pipeline/Spark 等物理实现。
