# Repo 文件和目录是干什么的

这份文档是人读的导航。目标不是解释每个内部函数，而是让你看到一个文件/目录时知道：**它属于哪一层、什么时候需要看、正常业务接入要不要改。**

## 顶层

```text
fabric-data-framework/
├─ README.md
├─ pyproject.toml
├─ .github/workflows/
├─ docs/
├─ examples/
├─ src/fabric_data_framework/
└─ tests/
```

| 路径 | 用途 | 正常新 dataset 要改吗 |
|---|---|---|
| `README.md` | repo 入口，告诉你 framework 是什么以及从哪里开始读 | 否 |
| `pyproject.toml` | Python package metadata、依赖、console script、版本 | 通常否 |
| `.github/workflows/ci.yml` | static check、Python tests、wheel build | 否 |
| `.github/workflows/release.yml` | immutable wheel / GitHub Release 发布流程 | 只有 framework release 时 |
| `docs/human/` | 人读的稳定使用文档 | 文档变化时 |
| `docs/machine/` | 精确状态、evidence、history、AI recovery context | 每个重要 framework slice 后 |
| `examples/` | schema-valid 示例配置和 approved-run recipe | 参考，不是生产配置 |
| `src/fabric_data_framework/` | framework package 本体 | 只有通用能力变化时 |
| `tests/` | semantic/runtime/provider/evidence contract tests | framework 改动时同步改 |

如果只是想浏览 Python 源码，先看：

```text
src/fabric_data_framework/README.md
```

它是代码层导航，不记录开发历史。

## `src/fabric_data_framework/` 怎么看

可以按下面七个层次理解：

```text
1. semantic config
2. capture / apply semantics
3. planning / execution
4. provider adapters
5. recovery / control plane
6. evidence / delivery
7. CLI presentation
```

### 1. Semantic config

| 文件/目录 | 职责 |
|---|---|
| `config.py` | `DatasetConfig` 和 source/load/target/orchestration/DQ/reconciliation 等 immutable semantic config |
| `contracts/` | framework 跨模块共享的 typed contracts，例如 capture/recovery outcomes |
| `capture/semantic_contracts.py` | source semantics、read strategy、delete semantics、Bronze contract，以及 cheatsheet presets |
| `capture/onboarding.py` | 新 dataset 的语义组合校验，阻止 overclaim |

先看这些，才能理解 dataset “是什么”；不要先从 Fabric REST adapter 开始读。

### 2. Capture / Bronze / Apply

| 文件/目录 | 职责 |
|---|---|
| `capture/` | snapshot、watermark、lookback、CDC、API/file 等 capture semantics 与 bootstrap contracts |
| `bronze.py` | Bronze lineage/record contract |
| `apply/` | APPEND、REPLACE、UPSERT、SCD1、SCD2、SNAPSHOT_DIFF 等目标应用语义 |
| CDC 相关模块 | ordering、dedupe、checkpoint、Debezium/Kafka、Delta CDF 的 normalize/recovery contract |

这里解决的是“拿到什么”和“怎样应用”，不是“用哪个 Fabric item 跑”。

### 3. Planning / execution

执行层把 immutable semantics 变成 immutable execution plan，并决定一个 stage 由 framework 还是 provider-native engine 执行。

重点概念：

```text
DatasetConfig -> capability resolution -> ExecutionPlan -> execution units
```

如果你在排查“为什么这张表选择 Copy Job 而不是 Spark”，应该从 capability/execution plan 这一层看，而不是改 DatasetConfig 去写 engine-specific hacks。

### 4. Provider adapters

| 文件/目录 | 职责 |
|---|---|
| `adapters/` | 外部/provider adapter 边界 |
| Fabric Pipeline backend 相关模块 | 调 Fabric Pipeline job，并保留 native correlation |
| Copy Job transport 相关模块 | Copy Job REST execution/status transport |
| Spark Job Definition transport 相关模块 | Spark SJD REST execution/status transport |
| Fabric auth 相关模块 | token-provider abstraction，不在 config 里保存 credential value |

Provider 返回 `Completed` 不代表 framework 已经可以推进 semantic checkpoint。

### 5. Recovery / control plane

| 文件/目录 | 职责 |
|---|---|
| `target_operations.py` | 一个逻辑 target mutation 的稳定 semantic identity、状态和允许动作 |
| `target_operation_io.py` | target-operation journal 的持久化/CAS 操作 |
| `recovery/` | provider-native recovery、target commit probe、Warehouse marker/session recovery |
| `relational_repository.py` | SQLAlchemy production-oriented control-plane repository |
| control-plane certification 相关模块 | 验证一个 SQL backend 是否符合 framework runtime contract |

Warehouse 相关要记住：

```text
matching marker -> COMMITTED
marker absent -> UNRESOLVED
只有独立 no-late-commit 证明 -> NOT_COMMITTED
```

### 6. `evidence/` / delivery

Approved evidence 的实际 implementation 现在集中在：

```text
src/fabric_data_framework/evidence/
├─ README.md
├─ __init__.py
├─ integration_evidence.py
├─ integration_checks.py
├─ integration_evidence_merge.py
├─ integration_runner.py
├─ approved_control_plane_runner.py
├─ approved_pipeline_runner.py
├─ approved_capture_runner.py
├─ approved_warehouse_runner.py
└─ approved_warehouse_fault_runner.py
```

阅读顺序建议：

```text
integration_evidence.py
  ↓
integration_checks.py
  ↓
integration_evidence_merge.py / integration_runner.py
  ↓
approved_*_runner.py
```

| 文件 | 职责 |
|---|---|
| `evidence/integration_evidence.py` | exact-release evidence spec、check kind、manifest、PASS/FAIL/NOT_RUN contract |
| `evidence/integration_checks.py` | 把已有 provider/runtime 结果安全投影为 evidence result |
| `evidence/integration_runner.py` | credential-free approved-run preflight；config 只保存 env-var name |
| `evidence/integration_evidence_merge.py` | staged evidence 的严格 merge，冲突 rerun 不做 latest-wins |
| `evidence/approved_control_plane_runner.py` | approved control-plane certification |
| `evidence/approved_pipeline_runner.py` | approved Pipeline execution evidence |
| `evidence/approved_capture_runner.py` | approved Copy Job / Spark capture evidence |
| `evidence/approved_warehouse_runner.py` | approved Warehouse target+marker commit/recovery |
| `evidence/approved_warehouse_fault_runner.py` | real ambiguous-COMMIT drill + optional session-termination recovery |
| `delivery.py` / deployment 相关模块 | config bundle、release manifest、deployment provenance |

Evidence 的职责是**证明已有 contract**，不是重新定义 dataset semantics、capture fidelity、target commit truth 或 recovery semantics。

根目录仍然保留例如：

```text
integration_evidence.py
integration_runner.py
approved_capture_runner.py
approved_warehouse_runner.py
```

这些现在只是 deprecated compatibility alias。它们和 `evidence/` 中的 canonical module 指向同一个 module object，确保已有 import/monkeypatch 不因为整理目录而突然失效。**不要再往这些根目录 shim 里新增 implementation。**

### 7. `cli/` — 可以单独忽略的 presentation layer

```text
src/fabric_data_framework/cli/
├─ README.md
├─ __init__.py
├─ __main__.py
├─ main.py
├─ base.py
└─ approved.py
```

| 文件 | 职责 |
|---|---|
| `cli/main.py` | 很薄的 command-family router / composition root |
| `cli/base.py` | validation、metadata、deployment、preflight 等通用 CLI |
| `cli/approved.py` | approved evidence / real-environment CLI |
| `cli/__init__.py` | 暴露 console-script `main` |
| `cli/__main__.py` | 支持 `python -m fabric_data_framework.cli` |
| `cli/README.md` | CLI 代码边界说明 |

依赖方向保持：

```text
semantic/runtime/provider/recovery core
                 ↑
             evidence
                 ↑
                cli

core -X-> cli
evidence -X-> cli
```

因此如果你只是想理解 framework 的核心数据处理能力，可以直接跳过整个 `cli/`；如果只想理解业务数据语义，也可以先跳过 `evidence/`。

更强的 CLI 约束是：**把 `src/fabric_data_framework/cli/` 物理删除后，核心 library import、capture/apply/execution/recovery/runtime 仍必须可用。** CI 有专门的 isolation test 钉住这个边界。

`cli_router.py` 只保留为旧 import 的 deprecated compatibility shim；实际 CLI implementation 不再放在顶层。

## `extensions/` 是什么

Framework 不允许 customer 随便注入任意代码路径，而是提供有边界的 logical-name extension registry。

当前主要 extension 类型包括：

```text
capture_observers
spark_execution_data
warehouse_mutations
warehouse_commit_fault_injectors
```

典型原则：

```text
framework owns semantics / transaction / PASS decision
customer extension owns only bounded customer-specific translation or mutation
```

## `examples/` 怎么用

`examples/` 是：

```text
“一个合法配置长什么样”
```

不是：

```text
“生产环境直接复制这个 ID/URL”
```

里面的 release hash、workspace/item UUID、artifact name、env-var name 都可能是 placeholder。生产使用时必须替换成 exact candidate / environment 的真实值。

## `tests/` 怎么看

测试不是只为了 coverage，它也是 framework contract 的可执行说明。

当文档说某个行为必须 fail closed，例如：

```text
provider Completed + missing framework outcome -> FAIL
marker absent -> UNRESOLVED
fault injection permission != Admin KILL permission
core library must not depend on CLI
legacy evidence import == canonical evidence module
```

对应测试应该明确钉住这个行为。

修改 framework contract 时，优先找到相应 contract test，再改实现。

## 人通常不用看的文件

如果你的任务只是接一张新表，正常不应该去改：

```text
evidence/approved_*_runner.py
evidence/integration_*.py
recovery/*
target_operation_*.py
provider REST transports
control-plane repository
cli/*
```

如果你发现每接一个新 dataset 都要改这些文件，说明 customer/framework 边界已经设计错了。

## 完整机器级 implementation map

需要精确到工程恢复、evidence level 和内部 owner 时，看：

```text
docs/machine/IMPLEMENTATION_MAP.md
```
