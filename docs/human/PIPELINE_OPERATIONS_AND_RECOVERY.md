# Pipeline Operations, Data Quality, Quarantine, and Recovery

这份 runbook 定义正常业务 Pipeline 的产品级运行语义，不是 release certification 流程。

目标场景是最常见的 Fabric 数据工程模式：一个 parent Pipeline / execution group 用 ForEach 或等价 orchestration 运行多张表，例如 50 张 FULL/REPLACE、20 张 WATERMARK/SCD2、20 张 WATERMARK/SCD1。

---

## 1. 默认运行语义：table fault isolation + fail at end

Framework 默认使用：

```text
PipelineFailurePolicy.FAIL_AT_END
```

语义是：

```text
parent Pipeline
  table A PASS
  table B FAIL  ----> 记录 dataset_run error，不终止独立 siblings
  table C PASS
  table D BLOCKED ---> 只因为 D 依赖 B
  table E PASS
        |
        v
所有仍可运行的 table 到 terminal state
        |
        v
aggregate
        |
        v
parent Pipeline FAILED
```

这解决两个常见问题：

1. 第一张坏表不会浪费剩余几十张独立表的执行窗口；
2. parent 仍然明确 FAILED，不会把数据不完整伪装成 SUCCESS。

只有明确业务接受 LOW/MEDIUM 表失败的 domain 才应显式采用 `CRITICALITY_AWARE`。不要为了让监控变绿而改这个策略。

---

## 2. Source-controlled execution-group policy

Parent Pipeline 的共享默认值放在 execution-group policy，而不是复制到几十张表。

例如：

```json
{
  "execution_group": "crm_scd2_daily",
  "failure_policy": "FAIL_AT_END",
  "max_concurrency": 8,
  "quality_defaults": {
    "enabled": true,
    "quarantine_enabled": true,
    "quarantine_detail_mode": "FULL",
    "max_quarantine_rows": 100,
    "max_quarantine_fraction": 0.005
  },
  "dataset_quality_overrides": {
    "crm.customer_sensitive": {
      "quarantine_enabled": false
    },
    "crm.contact": {
      "max_quarantine_rows": 10,
      "max_quarantine_fraction": 0.001
    }
  }
}
```

推荐 customer repo 布局：

```text
config/
  datasets/
    crm.customer.json
    crm.contact.json
  execution-groups/
    crm_scd2_daily.json
```

优先级固定为：

```text
DatasetConfig
-> execution-group quality defaults
-> execution-group per-dataset patch
-> audited RuntimeOverride
```

RuntimeOverride 是临时运维控制，不应该成为长期配置管理方式。事故结束后应把正确配置回写 Git，再关闭临时 override。

当 execution-group policy 被采用时，它的 exact content 必须进入 release/config bundle identity；否则同一个 dataset config hash 可能对应不同运行策略，无法审计。

---

## 3. DQ 和 quarantine 的四种常见模式

### 模式 A：DQ 开，quarantine 开，没有阈值

```text
bad rows -> quarantine
good rows -> continue
```

适合已知有少量可容忍坏行、下游允许 clean subset 的数据集。

### 模式 B：DQ 开，quarantine 开，有阈值

推荐生产默认。

例如：

```text
max_quarantine_rows = 100
max_quarantine_fraction = 0.005
```

只要任意一个上限被超过：

```text
完整坏行先被 durable quarantine
-> dataset FAILED
-> target/state/watermark 不 commit
-> independent siblings continue
-> parent finally FAILED
```

这样既保留调查证据，又不会因为“quarantine 功能存在”而静默吞掉大面积数据质量退化。

### 模式 C：DQ 开，quarantine 关

任何 invalid row：

```text
dataset FAILED
no target commit
no watermark/state advance
```

适合 regulated / financially sensitive / exact-completeness 数据。

### 模式 D：DQ 关

规则不执行，Framework 会记录 VALIDATE=SKIPPED。

这应该是明确的业务选择，不应作为事故时的快捷修复。不要为了让失败消失临时关 DQ，除非有审批、审计和明确风险接受。

---

## 4. Quarantine 保存在哪里

完整坏行可能包含 PII、大字段和敏感业务内容，因此：

```text
Fabric SQL Database / Control Plane
  quarantine_batch
    quarantine_id
    dataset_run_id
    row_count
    reason summary
    source_reference

Governed Lakehouse / data plane
  immutable detailed payload
    original row
    Bronze lineage
    rule_code
    rule_message
```

不要把完整业务坏行直接写进通用 Control Plane SQL error table。

`FULL` detail mode 要求存在 governed `QuarantinePayloadWriter`。如果 writer 不可用，Framework fail closed，而不是假装已经安全 quarantine。

生产 quarantine storage 应至少有：

- restricted ACL / least privilege；
- platform-approved encryption；
- retention policy；
- lineage；
- audit access；
- 删除/隐私流程和企业治理一致。

Source-controlled config 只保存逻辑配置，不保存 access token、password、signed URL。

---

## 5. 日常故障先看哪些表

先从 `pipeline_run` 找 parent：

```text
pipeline_run_id
status
error_code
error_message
started_at
completed_at
```

然后按 `pipeline_run_id` 查 `dataset_run`：

```text
dataset_id
status
attempt
rows_read
rows_accepted
rows_quarantined
rows_filtered
rows_inserted
rows_updated
rows_deleted
error_code
error_message
retryable
```

再用 `dataset_run_id` 查：

```text
step_run
reconciliation_result
quarantine_batch
capture_receipt
dataset_attempt_lineage
target_operation / target_operation_event
```

不要只看 Fabric UI 上的红/绿 activity。Provider `Completed` 也不等于 Framework semantic success。

---

## 6. Error -> repair decision table

| 情况 | 自动重试？ | 正确修复 |
|---|---:|---|
| 明确 transient provider error，`retryable=true` | 可以，bounded | `RETRY` + backoff + attempt lineage |
| `BLOCKED_DEPENDENCY` | 不直接重试 | 先修 upstream，再跑受影响 dependency chain |
| `DATA_QUALITY_FAILED_QUARANTINE_DISABLED` | 不可以 | 修 source/rule/config，再 audited RETRY |
| `DATA_QUALITY_QUARANTINE_THRESHOLD_EXCEEDED` | 不可以 | 修数据或 DQ rule，再从 retained quarantine 做 audited REPLAY |
| `RECONCILIATION_FAILED` | 不可以 | 查 source/target/mapping/reconciliation；确认正确后 reprocess |
| unknown/ambiguous COMMIT | 绝对不 blind retry | 先 reconcile target/operation marker；只有证明 NOT_COMMITTED 才可 retry |
| config/binding/schema contract 错误 | 不可以 | 修 Git config/binding，PR/CI/deploy 后再 retry |
| cancelled | 默认不可以 | 先确认 provider/target/checkpoint 是否有 partial effect |
| 未分类异常 | 不可以 | manual investigation，直到能证明 retry safety |

Framework `recovery.pipeline.build_pipeline_recovery_plan()` 会把 terminal outcomes 分成：

```text
safe_auto_retry_dataset_ids
operator_action_dataset_ids
```

这个函数只做保守诊断，不会自己执行 mutation。

---

## 7. RETRY：只用于已证明安全的同一逻辑工作

Framework 已有 `execute_with_retry()`：

```text
explicit retryable failure
-> bounded attempts
-> exponential backoff
-> new dataset_run_id per attempt
-> immutable DatasetAttemptLineage
-> final audit
```

推荐原则：

- retry count 有上限；
- backoff，不 tight loop；
- 每次 attempt 可审计；
- target apply 必须 idempotent 或有 operation journal；
- unknown commit 不进入普通 transient retry 分支。

`orchestration.retry_count` 表示业务期望，但物理 executor/backend 仍必须通过 Framework recovery contract 实现安全 retry，不能在 Fabric activity 里另外偷偷套一个无审计无限 retry。

---

## 8. Unknown COMMIT：先证明，再决定

最危险的错误是：

```text
request sent
server may have committed
client timed out / connection dropped
```

这时：

```text
DO NOT immediately retry mutation
```

Framework 的 target operation journal / Warehouse marker recovery 用语义 identity 判断：

```text
COMMITTED
  -> converge to success; do not mutate again

NOT_COMMITTED
  -> safe retry may be allowed

UNRESOLVED
  -> stop; operator/provider evidence required
```

这是防 double-write、double-SCD-version、double-append 的核心边界。

---

## 9. REPLAY：修完 DQ 后只重放 quarantine

如果：

```text
DATA_QUALITY_QUARANTINE_THRESHOLD_EXCEEDED
```

推荐流程：

```text
1. 保留原 quarantine payload，不删除
2. 定位 rule/source defect
3. 修 source 或 rule/mapping
4. PR + CI + deploy 正确版本
5. 创建 audited ReprocessRequest(run_mode=REPLAY)
6. 从 exact quarantine_id/source_reference 载入 payload
7. 重新执行 transform/DQ/apply/reconciliation
8. target/state gate PASS
9. 只写 replay correlation marker
```

原始 quarantine evidence 必须继续保留。Replay success 不是把历史坏行记录抹掉，而是记录：

```text
this quarantine was successfully replayed by dataset_run_id X
```

---

## 10. BACKFILL：修复一个有边界的 source gap

适用于：

- 一段 watermark 时间窗漏数；
- 一段分区未捕获；
- source connector 在明确区间失败。

使用 `ReprocessRequest(run_mode=BACKFILL)` 并明确：

```text
lower
upper
```

不要用 unrestricted FULL rebuild 代替一个很小的 gap。

Backfill 仍然走正常 DQ、apply、reconciliation 和 idempotency contract。

---

## 11. FULL_REBUILD：最后手段

只在 authoritative reset 明确成立时使用：

```text
run_mode = FULL_REBUILD
range_json.authoritative_reset = true
```

典型用途：

- SCD history 算法/业务定义发生不可增量修复的变化；
- target 已无法可信地从局部增量恢复；
- authoritative full source snapshot 可重建完整目标。

Full rebuild 不应该成为“夜里 pipeline 红了”的第一反应。

---

## 12. Dependency failure 如何恢复

例子：

```text
A = customer master
B = customer SCD2, depends on A
C = independent order

A FAIL
B BLOCKED
C PASS
parent FAILED
```

恢复时：

```text
先恢复 A
-> 验证 A success/state
-> 再执行 B dependency chain
```

不要把整个 100-table parent 无差别重跑，除非所有 apply 都已经证明完全 idempotent且业务上确实需要。

---

## 13. 推荐告警

至少对这些信号告警：

```text
parent Pipeline FAILED
retry exhausted
unknown commit unresolved
DQ quarantine threshold exceeded
quarantine rate trend abnormal
BLOCKED dependency count > 0
reconciliation failed
SLA/expected-finish breach
repeated failures for same dataset
```

不要只告警 Fabric parent activity status。Control Plane 的 semantic outcome 才是业务运行事实。

推荐同时做趋势监控：

```text
rows_quarantined / rows_read
per dataset / rule / day
```

即使单次没有越阈值，持续上升也应该触发 investigation。

---

## 14. Operator incident flow

生产事故建议固定为：

```text
1. 获取 pipeline_run_id
2. 查 FAILED/BLOCKED dataset_run
3. 查 first failing step + provider correlation
4. 生成/阅读 PipelineRecoveryPlan
5. 判断 transient / DQ / reconciliation / dependency / unknown commit / config
6. 按对应 recovery mode 修复
7. 创建 audited reprocess request
8. 只重跑必要 scope
9. 验证 target + reconciliation + state/watermark
10. 验证 downstream dependency chain
11. 关闭 incident，并把 temporary RuntimeOverride 回写/清理
```

Stop condition：只要 commit outcome 仍 `UNRESOLVED`，就停止自动恢复。

---

## 15. Pipeline 设计建议

Fabric parent Pipeline 本身尽量薄：

```text
lookup/select dataset work
-> bounded ForEach / reusable child
-> child passes exact framework run identity
-> Framework persists semantic outcome
-> parent waits for all runnable work
-> Framework aggregate
-> final activity reflects aggregate status
```

不要给每张表复制一套 20 个 activities，也不要让几十个 Notebook 各自维护 watermark、retry、quarantine、SCD2 规则。

Framework owns HOW；customer/domain config owns WHAT。

---

## 16. 运维上不要做的事

不要：

- 第一张表失败就取消所有独立 tables；
- 为了绿灯把 `FAIL_AT_END` 改成 partial success；
- unknown commit 直接 retry；
- DQ 失败后直接关 DQ；
- quarantine payload 写进 public repo / chat；
- replay 成功后删除原始审计证据；
- 全表重建来修一个可定位的小范围 gap；
- 同时在 Fabric native retry 和 Framework retry 两层做无边界重试；
- 只保留字符串日志、不保留 typed run identity 和 lineage。

---

## 17. 和 certification 的关系

这些是正常 runtime / operations contract。

```text
日常业务 Pipeline
!=
Framework release certification
```

CI 可以证明代码 contract；真实 Fabric certification 证明 exact Framework bytes 和环境边界。当前 0.4 release governance 仍独立执行，不能因为这套 runtime tests 通过就自动 freeze/release。
