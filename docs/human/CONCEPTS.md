# 怎么理解这个 framework

## 一句话

`fabric-data-framework` 把 **数据工程语义** 和 **Fabric 的物理执行方式** 分开。

业务团队描述“这是什么数据、怎么变化、历史要保留到什么程度、目标表怎么应用”；framework 再把这些语义编译成可执行计划，并负责可验证的运行、恢复和证据。

## 三层模型

```text
1. Data semantics
   这份数据本质上是什么？

2. Execution
   用 Copy Job / Pipeline / Spark / SQL / provider-native capability 怎么跑？

3. Evidence + recovery
   怎么知道真的成功了？失败/超时/未知 commit 时能不能安全恢复？
```

不要把 2 当成 1。

例如：

```text
“用 Spark”
```

不是数据语义。

真正的数据语义可能是：

```text
source = current-state relational table
read = updated_at watermark + lookback
delete = soft delete column
Bronze = raw append observations
Silver = SCD2
```

Spark 只是执行这套语义的一种 engine。

## 核心流水线

```text
DatasetConfig
  ↓
semantic validation / onboarding
  ↓
capability resolution
  ↓
immutable ExecutionPlan
  ↓
capture / orchestration
  ↓
verified CaptureReceipt / durable child outcome
  ↓
normalize + DQ
  ↓
apply to target
  ↓
commit proof / recovery
  ↓
downstream semantic checkpoint
```

## Capture 和 Apply 是两件事

Capture 回答：

```text
这次从 source 实际拿到了什么？
```

Apply 回答：

```text
拿到的数据怎样写到目标？
```

常见组合：

```text
FULL snapshot capture + REPLACE apply
WATERMARK capture + UPSERT apply
full CDC capture + SCD2 apply
business events capture + APPEND apply
snapshot capture + SNAPSHOT_DIFF apply
```

所以不要用 `SCD2` 来描述 source capture，也不要把 `watermark` 当成 Silver strategy。

## Bronze 不是固定一种表

Framework 允许 Bronze 表达不同含义。

### Current Bronze

保存 source 当前/最新状态。

适合：

- current-state serving；
- 不需要保留每次 observation；
- downstream 只关心当前值。

### Snapshot Bronze

每次完整 snapshot 都保留。

适合：

- source 没有 CDC；
- 需要按 snapshot grain 追踪历史；
- 后面要做 snapshot diff。

### Raw Append / Event Bronze

把每次 change/event/observation append 保存。

适合：

- CDC/event stream；
- 需要 audit/replay；
- SCD2 需要有足够 change fidelity。

## 历史 fidelity 的上限来自 capture

这是整个 framework 最重要的语义约束：

```text
capture fidelity <= truthful downstream history fidelity
```

例如 source 只给：

```text
每天 02:00 一张完整快照
```

你最多能证明“snapshot grain 的历史”。

就算 Silver 写成 SCD2，也不能声称知道：

```text
09:03 A -> B
09:08 B -> C
```

因为这两个中间变化根本没被 capture。

同理，如果 provider CDC 只给 net changes，那么一个 batch 内被 collapse 的中间状态不能被 framework 恢复出来。

## Provider cursor 和 framework checkpoint 不是一个东西

```text
provider/native cursor
```

表示 provider 自己消费到哪里。

```text
framework downstream semantic checkpoint
```

表示 framework 已经确认：capture、apply、target commit、reconciliation 都完成，可以安全推进的语义边界。

两者不能自动等价。

因此：

```text
provider Completed != framework semantic success
```

Copy Job、Pipeline、Spark 显示 Completed 只是一个必要信号，不是最终业务成功证明。

## Unknown commit 为什么不能直接 retry

数据库写入可能出现：

```text
COMMIT 已经成功
但是 client 没收到 ACK
```

这时如果盲目 retry，可能重复写入。

Framework 使用稳定的 target-operation identity、控制面 journal 和 target-side marker 来区分：

```text
COMMITTED
NOT_COMMITTED
UNRESOLVED
```

规则是：

```text
UNRESOLVED -> 不允许 blind retry
```

只有确切证明 `NOT_COMMITTED` 后，才允许重新执行。

## Framework 和 customer repo 的边界

Framework 拥有：

```text
semantics
contracts
planning
runtime
provider adapters
recovery
control-plane model
evidence model
release tooling
```

Customer repo 拥有：

```text
business DatasetConfig
business source/target names
workspace/item bindings
customer-specific SQL/mutation logic
customer-specific observation translation
business deployment/release inputs
```

Customer extension 是有边界的插槽，不是绕过 framework 的入口。

例如 Warehouse mutation extension 可以拿到 framework 已打开的 SQLAlchemy `Connection` 做业务 mutation，但不能自己：

```text
COMMIT
写 framework marker
改 target-operation journal
决定 PASS/FAIL
```

## 什么时候需要改 framework

判断标准：

```text
这个能力能不能被多个 domain / customer 复用？
```

如果只是：

```text
customer A 的某张表如何映射字段
customer B 的某个 API 怎么翻译 payload
```

放 customer repo。

如果是：

```text
所有 watermark source 都需要一种新的安全 handoff contract
所有 Fabric Warehouse 都需要新的 recovery primitive
```

才进入 framework。
