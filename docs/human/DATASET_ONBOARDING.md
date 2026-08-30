# 新数据来了怎么接

这份文档是日常 data engineering 最重要的入口。

目标是回答：

```text
来了一个新 source / 新表，我到底选什么？
```

不要先问“用 Copy Job 还是 Spark”。

先把数据语义确定下来。

---

# 1. 先收集这 8 个事实

对 source owner / upstream 系统确认：

1. **第一次能拿什么？** 全量 snapshot 还是只能增量？
2. **以后每次拿什么？** full snapshot、updated rows、net changes、all changes、events？
3. **主键是什么？** 是否稳定？
4. **update 顺序依据是什么？** `updated_at`、LSN、offset、sequence、version？
5. **delete 怎么表现？** hard delete、soft delete、tombstone、CDC delete event，还是完全看不到？
6. **会不会迟到/回写？** `updated_at` 有没有 back-dated update？
7. **provider 会不会 collapse 中间 changes？**
8. **业务到底需要 current state 还是 history？history 要细到什么粒度？**

如果这些事实没搞清楚，不要直接配置 SCD2。

---

# 2. 用一个简单 decision tree 选 capture

```text
每次只能/适合拿整张表？
  |
  +-- 是 -> FULL SNAPSHOT
  |          |
  |          +-- 只要当前状态 -> Current Bronze
  |          +-- 要 snapshot history -> Snapshot Bronze
  |          +-- 要推断变化 -> Snapshot Diff
  |
  +-- 否
       |
       +-- 有 updated_at / monotonically progressing watermark？
       |     |
       |     +-- 是 -> WATERMARK
       |              |
       |              +-- 可能 late update -> LOOKBACK
       |              +-- 有 is_deleted -> SOFT DELETE
       |
       +-- provider 给 CDC/change feed？
       |     |
       |     +-- 只给最终 net changes -> NET CHANGES
       |     +-- 给全部有序 changes -> FULL / ALL CHANGES
       |
       +-- 本身就是业务事件 -> BUSINESS EVENTS
```

---

# 3. Framework 支持的 14 种常见语义模式

下面是 onboarding 时真正应该对照的表。

| # | 模式 | 实际拿到什么 | Delete 能力 | 推荐 Bronze | 历史真实性上限 | 常见 Silver |
|---|---|---|---|---|---|---|
| 1 | Full Snapshot -> Current | 整表当前状态 | 可通过 snapshot 对比间接识别，但 current Bronze 自己不保留前态 | Current | current state | SCD1 / current |
| 2 | Full Snapshot -> Snapshot | 每次整表 snapshot | 可通过相邻 snapshot 推断 | Snapshot | snapshot grain | SCD2 / snapshot history / diff |
| 3 | Watermark -> Current | `watermark > checkpoint` rows | hard delete 通常不可见 | Current | observed updates | SCD1；SCD2 只能记录观测到的变化 |
| 4 | Watermark + Lookback -> Current | watermark 窗口重读一段历史 | hard delete 通常不可见 | Current | observed updates，late update 更安全 | SCD1 / limited SCD2 |
| 5 | Watermark + Lookback -> Raw Append | 每次窗口 observation append | hard delete 通常不可见 | Raw Append | observed-change history | SCD2 / audit |
| 6 | Watermark + Soft Delete -> Current | updated rows + `is_deleted` | soft delete 可见 | Current | observed updates + tombstones | SCD1 / SCD2 |
| 7 | Watermark + Lookback + Soft Delete -> Raw Append | 重叠窗口 observations + tombstones | soft delete 可见 | Raw Append | observed-change history | SCD2 / audit |
| 8 | Net Changes -> Current | 一个 provider window 内每个 key 的净变化 | 看 provider 是否保留 delete net change | Current | batch/window grain | SCD1；谨慎 SCD2 |
| 9 | Net Changes -> Append | 每个 batch 的 net change append | 同上 | Append Changes | batch/window grain | SCD2，但不能声称中间事件完整 |
| 10 | Full / All Changes -> Event | 完整、有序 change events | delete event 可保留 | Event | captured event grain | SCD2 / event history |
| 11 | Full Changes -> Current | source 给完整 changes，但 Bronze 主动压成当前值 | delete 可处理 | Current | **人为降级为 current** | SCD1；这是 intentional lossy |
| 12 | Business Events -> Event | 订单创建、付款、状态变更等业务事件 | 由事件语义定义 | Event | captured business-event grain | Append/event-derived models |
| 13 | Snapshot Diff -> Current | framework 比较前后 snapshot 推断 I/U/D | 可推断 snapshot 间消失 | Current | snapshot interval grain | SCD1 / current |
| 14 | Snapshot Diff -> Append Changes | snapshot diff 结果 append 成 changes | 可推断 snapshot 间消失 | Append Changes | snapshot interval grain | SCD2 / audit |

关键点：

```text
“All 14 supported” 表示 framework 能表达并验证这些语义组合。
```

不表示每一种 source/provider 都已经有一条真实生产环境的 provider proof。

---

# 4. Bronze 怎么选

## 只需要当前状态

选：

```text
Current Bronze
```

典型：

```text
customer master
product current attributes
reference data
```

优点：简单、存储小。

缺点：失去 observation history。

## Source 没有 change feed，但你想保留历史

选：

```text
Snapshot Bronze
```

典型：

```text
每天 SFTP 一份 customers.csv
每天 API 导出全部 accounts
```

之后可以用 snapshot diff 推断 snapshot 间变化。

## 需要 audit / replay / SCD2

优先考虑：

```text
Raw Append / Event Bronze
```

前提是 source 本身能提供足够 change fidelity。

不要因为“我要 SCD2”就自动 raw append；要先确认 append 的每条 observation 到底代表 change 还是重复扫描。

---

# 5. Silver SCD1 还是 SCD2

## SCD1

适合：

```text
只关心最新状态
历史没有业务价值
source 本身历史 fidelity 很弱
```

## SCD2

适合：

```text
业务需要 as-of history
source/capture 能证明变化边界
key/order/delete 语义足够明确
```

永远记住：

```text
SCD2 是 target representation，不是 source history generator。
```

如果你每天只有一次 snapshot，那么 SCD2 最多只能说：

```text
“在两个 snapshot 之间发生了变化”
```

不能准确声称变化发生在某个中间时间点，除非 source 里本身有可信的 effective timestamp/change sequence。

---

# 6. Watermark 怎么判断安不安全

最常见的新 source 是：

```sql
WHERE updated_at > :last_watermark
```

你需要检查：

- `updated_at` 是否每次 update 都会更新？
- precision 是否足够？
- 多行相同 timestamp 怎么 deterministic order？
- upstream 会不会把旧记录 back-date？
- transaction commit 和 timestamp assignment 的顺序是否可能导致漏数？
- delete 怎么看到？

如果可能 late update，通常使用：

```text
watermark + lookback
```

例如：

```text
checkpoint = 2026-08-30 10:00
lookback   = 2 hours
next read  = updated_at >= 08:00 and <= frozen_upper_bound
```

然后在 capture/apply 中依靠稳定 PK + ordering/dedupe 去重。

Lookback 解决的是：

```text
迟到 observation / boundary safety
```

不是 hard delete visibility。

---

# 7. Full baseline -> Watermark 怎么做

常见场景：

```text
第一次拿全表
以后只拿 updated_at 增量
```

不能简单做：

```text
今天 full load
明天开始 updated_at > 今天凌晨
```

需要一个可证明的 handoff boundary。

Framework 的原则是：

```text
baseline 必须完整
handoff boundary 必须一致
post-boundary changes 必须仍然可见
ordering 必须 deterministic
```

如果 source 无法证明这些条件，就不能声称 no-gap bootstrap。

---

# 8. Delete 怎么判断

## Hard delete + watermark table

如果一行直接从 source 消失，而增量 query 只读取存在的 rows：

```text
delete visibility = none
```

Framework 不会猜。

解决方式只能来自额外信号，例如：

```text
soft delete flag
CDC delete event
periodic full snapshot diff
tombstone feed
source audit table
```

## Soft delete

例如：

```text
is_deleted = 1
```

需要确认 tombstone 不会在你 capture 前被 purge。

否则理论上有 soft delete column，也不代表你一定能可靠看到 delete。

---

# 9. Net CDC 和 Full CDC 的区别

## Net changes

假设同一个 customer 在一个 provider window 内：

```text
A -> B -> C
```

provider 最后只给：

```text
A -> C
```

那就是 net changes。

Framework 可以保存 batch/window grain history，但不能恢复 `B`。

## Full / all changes

如果 provider 给：

```text
A -> B
B -> C
```

并且有可靠顺序/offset/LSN，那么才能保留完整 captured change history。

---

# 10. 四个具体例子

## 例子 A：CRM Customer

Source：

```text
SQL table
PK = customer_id
updated_at 每次修改都会更新
有 is_deleted
可能有 30 分钟迟到
```

推荐：

```text
capture = WATERMARK + LOOKBACK + SOFT DELETE
Bronze  = Raw Append（如果需要 audit/SCD2）
Silver  = SCD2
```

需要配置：

```text
PK
watermark column
lookback duration
soft-delete signal
frozen upper bound / deterministic ordering
```

如果业务只关心最新 customer，可以把 Bronze/Silver 简化成 current + SCD1。

## 例子 B：ERP 每晚完整 Orders 文件

Source：

```text
每天 01:00 一个完整 orders.csv
没有 CDC
```

如果只要当前状态：

```text
FULL SNAPSHOT -> Current Bronze -> REPLACE/SCD1
```

如果需要追踪每天之间变化：

```text
FULL SNAPSHOT -> Snapshot Bronze
                  ↓
              Snapshot Diff
                  ↓
             Append Changes / SCD2
```

历史粒度是“每天 snapshot”，不是订单真实发生变更的秒级时间。

## 例子 C：数据库 native CDC 只给 net changes

Source：

```text
provider CDC
每个 batch 对同一个 PK collapse 成最后状态
```

推荐：

```text
NET CHANGES -> Current Bronze
```

或：

```text
NET CHANGES -> Append Changes
```

但文档和数据产品都必须承认：

```text
history fidelity = batch/window grain
```

不能标成 full event history。

## 例子 D：支付业务事件

Source：

```text
PaymentAuthorized
PaymentCaptured
PaymentRefunded
```

这是 business events，不需要强行转换成 watermark semantics。

推荐：

```text
BUSINESS EVENTS -> Event Bronze -> append/event-derived models
```

如果还需要 payment current state，可以在 downstream 派生 current projection。

---

# 11. 实际 onboarding 步骤

新 dataset 正常应该在 `fabric-customer` 完成：

```text
1. 收集 source facts
2. 选择上面的语义 pattern
3. 创建 DatasetConfig
4. 声明 Bronze / apply / quality / reconciliation 语义
5. 运行 semantic onboarding validation
6. 配置 DEV physical binding
7. 如果 provider 需要 customer-specific translation，再写 bounded extension
8. 生成 exact release/config bundle
9. 部署 DEV
10. 做 normal run + evidence
```

验证命令从 CLI help 开始：

```bash
fabric-framework capture-semantic-onboarding-validate --help
```

不要为了让 validator 通过而“降低描述精度”。如果 source 只能提供 net changes，就如实声明 net changes；framework 的价值就是阻止 downstream overclaim。

---

# 12. 什么时候需要 framework 新功能

当你发现现有 14 种模式都无法准确表达 source，而这个缺口是**通用数据工程能力**，再来改 `fabric-data-framework`。

例如合理的 framework enhancement：

```text
一种新的通用 delete semantics
一种新的 provider-neutral bounded cursor contract
一种新的通用 apply semantic
```

不合理的 framework enhancement：

```text
customer A 的表名例外
某张表特殊字段 rename
某个 business domain 的 hard-coded SQL
```

后者应该留在 customer repo。
