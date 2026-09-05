# 人读文档

这里是正常开发、接新数据、部署和运维时需要看的文档。

不要从 `docs/machine/` 开始学这个 repo；那部分是给 framework 维护、AI 恢复上下文和证据审计用的。

## 推荐阅读顺序

| 文件 | 解决什么问题 |
|---|---|
| [`CONCEPTS.md`](CONCEPTS.md) | 先理解这个 framework 的边界、数据语义和整体运行模型 |
| [`REPOSITORY_GUIDE.md`](REPOSITORY_GUIDE.md) | 看 repo 目录和重要代码文件分别负责什么 |
| [`GETTING_STARTED.md`](GETTING_STARTED.md) | 本地怎么装、怎么测试、怎么打 wheel、Fabric 里怎么用 |
| [`CUSTOMER_PROJECT_BOOTSTRAP.md`](CUSTOMER_PROJECT_BOOTSTRAP.md) | 新项目怎么初始化 customer repo，几十/几百张表怎么放在一个产品级 repo 里 |
| [`DATASET_ONBOARDING.md`](DATASET_ONBOARDING.md) | 来了一个新数据源/新表，到底该选哪种 capture/Bronze/Silver 模式 |
| [`PIPELINE_OPERATIONS_AND_RECOVERY.md`](PIPELINE_OPERATIONS_AND_RECOVERY.md) | **正常业务 Pipeline 主运维 runbook**：ForEach 多表 fail-at-end、execution-group defaults、DQ/quarantine 阈值、状态审计、RETRY/REPLAY/BACKFILL/FULL_REBUILD 和 incident repair |
| [`OPERATIONS.md`](OPERATIONS.md) | CLI 是干什么的，release/evidence/approved run 怎么执行，以及 normal runtime recovery 与 certification 的边界 |
| [`FRAMEWORK_DEVELOPER_CERTIFICATION.md`](FRAMEWORK_DEVELOPER_CERTIFICATION.md) | **Framework 开发者/新员工 certification 主 runbook**：从改代码、PR/main CI、exact artifact、Fabric bounded/full certification、SQL Database/Warehouse runtime binding 到证据交接，一步步 follow |
| [`ONE_CALL_CERTIFICATION_RUNTIME.md`](ONE_CALL_CERTIFICATION_RUNTIME.md) | one-call runtime mapping、临时 process-env bridge、新 SQL Database 首次 bootstrap、durable Pipeline child 的精确 contract |
| [`UNIFIED_FABRIC_CERTIFICATION.md`](UNIFIED_FABRIC_CERTIFICATION.md) | unified runner 的 operator contract、状态语义、governance 和 provider-stage 说明 |
| [`FABRIC_PIPELINE_CHILD_CONTRACT.md`](FABRIC_PIPELINE_CHILD_CONTRACT.md) | 可复用 Fabric child Pipeline/Notebook 必须如何接收 Framework 参数、验证 exact config/plan 并持久化 DatasetDispatchOutcome |
| [`FIRST_FABRIC_NOTEBOOK_TEST.md`](FIRST_FABRIC_NOTEBOOK_TEST.md) | 逐 cell 的诊断/兼容 runbook；新 candidate 默认先用 unified runner，失败时再用这里隔离单项 |
| [`MANUAL_CERTIFICATION.md`](MANUAL_CERTIFICATION.md) | 旧/manual governance lane 和 Admin Override 的语义；不是新 unified runner 的默认执行方式 |
| [`RELEASE_CANDIDATE.md`](RELEASE_CANDIDATE.md) | 0.4 feature freeze 后如何聚合 exact-candidate evidence、判断是否允许 release |

## 正常业务 Pipeline 出错从哪里开始

不要先去 certification 文档，也不要第一反应整批 100 张表重跑。先看：

```text
docs/human/PIPELINE_OPERATIONS_AND_RECOVERY.md
```

默认产品语义是：

```text
one table FAIL
-> independent siblings continue
-> dependents BLOCKED
-> all runnable work reaches terminal state
-> parent Pipeline FAILED at the end
```

Control Plane 中从 `pipeline_run -> dataset_run -> step_run/reconciliation/quarantine/attempt lineage` 定位 first failure。只有明确 `retryable=true` 的 transient failure 才适合 bounded automatic retry；unknown commit 必须先 reconcile，DQ 要先修数据/rule 再 retry/replay，dependency failure 先恢复 upstream。

## 如果你在开发这个 Framework，Certification 从哪里开始

新员工或第一次维护 certification 的 Framework 开发者，直接从：

```text
docs/human/FRAMEWORK_DEVELOPER_CERTIFICATION.md
```

开始，不要靠聊天记录恢复步骤。这个 runbook 明确覆盖：

```text
本地开发
-> PR CI
-> merge
-> independent main CI
-> exact main wheel artifact
-> Fabric bounded certification
-> exact Customer input bundle
-> Control Plane SQL Database / Warehouse runtime binding
-> full certification
-> report/evidence review
-> release boundary
```

其中最重要的一点：

```python
report = certify(spark=spark)
```

**不会扫描 workspace 自动选择 SQL Database。** 没有 `customer-inputs/` 时它只执行 bounded suite。Full certification 时，`customer-inputs/runner-config.json` 声明需要读取哪个 runtime environment-variable name，而实际 SQL Database/Warehouse URL 由 runtime-only secret/environment value 提供。

如果要理解为什么 `runtime_environment` 能同时被 Framework approved runner 和 Customer extension 看见，以及新建 SQL Database 第一次为什么还需要 exact semantic metadata materialization，直接看 [`ONE_CALL_CERTIFICATION_RUNTIME.md`](ONE_CALL_CERTIFICATION_RUNTIME.md)。

## 第一次公司 Fabric 测试从哪里开始

新 candidate 默认不要逐 cell 复制，也不要先打开 certification 表单填结果。使用统一执行入口：

```python
from fabric_data_framework.certification import certify, print_certification_summary

report = certify(spark=spark)
print_certification_summary(report)
```

约定目录是：

```text
/lakehouse/default/Files/framework_cert/
  CANDIDATE.json
  fabric_data_framework-<version>-py3-none-any.whl
  SHA256SUMS
  customer-inputs/        # 完整环境 certification 时可选/需要
```

只有 Framework artifact 时，runner 自动跑 exact identity、Lakehouse、FULL/SCD1/SCD2、retry、reconciliation bounded checks。

准备好同一 candidate 的 exact Customer input bundle，并且公司已经批准普通 certification mutation 时，可显式提供 runtime-only database bindings：

```python
runtime_environment = {
    "CONTROL_PLANE_DATABASE_URL": control_plane_database_url,
    "WAREHOUSE_DATABASE_URL": warehouse_database_url,
}

report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
)
```

`runtime_environment` 只在本次调用的 runtime scope 中使用。exact Customer `runner-config.json` 声明允许读取哪些 variable names；public API 在调用期间只把这些声明过的名字临时同步给需要 `os.environ` 的 Customer/domain extension，返回前恢复原 process environment。secret value 不进入 source-controlled bundle 或 retained report/evidence。

如果是**刚创建的专用 certification SQL Database**，第一次需要显式 bootstrap schema + exact Customer semantic metadata：

```python
report = certify(
    spark=spark,
    runtime_environment=runtime_environment,
    allow_live_mutations=True,
    allow_control_plane_migration=True,
)
```

这个 first-time path 会先要求 exact bounded checks 全部 PASS，再验证 Customer bundle 与同一个 Framework wheel 匹配，然后才 materialize Control Plane。正常 rerun 保持 `allow_control_plane_migration=False`。

这会按依赖顺序继续尝试 Fabric item read、Control Plane、Pipeline、Copy、Spark、Warehouse、ambiguous-COMMIT 和五条 live business path。缺 external evidence、缺 runtime secret、缺 fault controller 或缺授权的项目显示为 `BLOCKED` / `NOT_RUN`，不能用 synthetic PASS 填满结果。

Warehouse Admin-level exact-session termination 仍然需要独立显式授权，不能从普通 live mutation authorization 推导。

详细步骤看 [`FRAMEWORK_DEVELOPER_CERTIFICATION.md`](FRAMEWORK_DEVELOPER_CERTIFICATION.md)；one-call runtime/Control Plane 细节看 [`ONE_CALL_CERTIFICATION_RUNTIME.md`](ONE_CALL_CERTIFICATION_RUNTIME.md)；unified runner 的 contract 说明看 [`UNIFIED_FABRIC_CERTIFICATION.md`](UNIFIED_FABRIC_CERTIFICATION.md)。`FIRST_FABRIC_NOTEBOOK_TEST.md` 现在主要用于排查某一项失败或验证旧 wheel。

## 你通常应该改哪个 repo

### 新业务表、新数据源、新 domain

通常改：

```text
fabric-customer
```

包括：

- DatasetConfig；
- execution-group policy；
- source/target metadata；
- Fabric workspace/item binding；
- customer-specific observer / mutation / execution-data extension；
- domain release config。

### framework 没有你需要的通用能力

才改：

```text
fabric-data-framework
```

例如：

- 新的通用 capture semantics；
- 新 apply strategy；
- 新 provider transport；
- 新 recovery contract；
- 新 evidence contract；
- 新 reusable CLI/runtime capability。

### Capacity / workspace / infra lifecycle

属于：

```text
fabric-infra
```

## 最重要的使用原则

```text
先描述数据语义，再选执行引擎。
```

不要因为 Fabric 里有 Copy Job、Pipeline、Spark 就先选工具，再反过来解释数据语义。

先回答：

- 我实际拿到的是 full snapshot、watermark rows、net changes、full ordered changes 还是 business events？
- delete 能不能看到？
- Bronze 是 current state、snapshot history 还是 append/event history？
- Silver 是 SCD1 还是 SCD2？
- source/capture 能支持多高的历史 fidelity？

然后 framework 才决定/验证物理执行方式。

## 人读文档不记录什么

这里刻意不维护：

- PR #xx 历史；
- merge SHA；
- Actions run ID；
- 每次测试数量演进；
- 某个功能是第几阶段实现的；
- 已经被整合进现有能力的临时设计过程。

这些内容统一放在 `docs/machine/`，避免把正常使用文档变成 changelog。
