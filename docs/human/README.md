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
| [`OPERATIONS.md`](OPERATIONS.md) | CLI 是干什么的，release/evidence/approved run 怎么执行 |
| [`MANUAL_CERTIFICATION.md`](MANUAL_CERTIFICATION.md) | 公司 Fabric 不允许 GitHub 直连时，如何用 Notebook + Admin Override 做可追溯 certification |
| [`FIRST_FABRIC_NOTEBOOK_TEST.md`](FIRST_FABRIC_NOTEBOOK_TEST.md) | 第一次在公司 Fabric 里怎么逐 cell 验证 exact wheel、Lakehouse、FULL/SCD1/SCD2、retry、reconciliation，并正确登记 PASS/FAIL/NOT_RUN |
| [`RELEASE_CANDIDATE.md`](RELEASE_CANDIDATE.md) | 0.4 feature freeze 后如何聚合 exact-candidate evidence、判断是否允许 release |

## 第一次公司 Fabric 测试从哪里开始

不要只打开 certification 表单然后勾选结果。表单是**登记结果**，不是测试执行器。

第一次实际测试按这个顺序：

```text
FIRST_FABRIC_NOTEBOOK_TEST.md
  -> 真正运行 bounded Fabric + framework checks
  -> MANUAL_CERTIFICATION.md
  -> 登记 PASS / FAIL / NOT_RUN
  -> 如确有企业权限/导出限制，再显式选择 Admin Override
```

没有权限的 Warehouse / ambiguous-COMMIT 项保持 `NOT_RUN`；不要用 synthetic PASS 填满表格。

## 你通常应该改哪个 repo

### 新业务表、新数据源、新 domain

通常改：

```text
fabric-customer
```

包括：

- DatasetConfig；
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
