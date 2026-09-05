# Operations / CLI 使用指南

这份文档回答三个问题：

```text
CLI 到底什么时候用？
正常业务 Pipeline 出错如何恢复？
真实 DEV/UAT/PROD release evidence 应该按什么顺序跑？
```

正常业务 Pipeline 的完整 fault-isolation / DQ / quarantine / recovery runbook 现在统一放在：

```text
docs/human/PIPELINE_OPERATIONS_AND_RECOVERY.md
```

不要把 daily Pipeline recovery 和 Framework release certification 混在一起。

## 1. CLI 分成四类

### A. 开发和语义验证

用于本地：

```text
capture-semantic-onboarding-validate
metadata materialization
config/release validation
```

目的：在部署前发现 semantic overclaim 和 invalid config。

### B. Release / deployment preparation

用于生成或验证：

```text
release manifest
config bundle identity
deployment plan / record
artifact hashes
```

目的：让 deployed code/config 有 exact provenance。

如果 customer/domain 使用 execution-group policy，它也属于 source-controlled release input；policy 变化必须进入 config bundle identity，不能在 Fabric UI 里静默改一份不同的运行策略。

### C. Approved environment evidence

用于真实 DEV/UAT/PROD 环境中的受控检查：

```text
integration-run-preflight
integration-item-smoke-run
integration-control-plane-certify-run
integration-pipeline-run
integration-capture-run
integration-warehouse-run
integration-warehouse-fault-drill-run
```

### D. Evidence 汇总

```text
integration-evidence-merge
integration-evidence-validate
```

目的：把多个阶段的 immutable partial evidence 合成 exact-release manifest。

---

# 2. 正常业务 Pipeline 的 failure boundary

默认 parent Pipeline 使用 `FAIL_AT_END`：

```text
一个 table FAIL
-> 记录 dataset_run error
-> independent siblings 继续
-> downstream dependents BLOCKED
-> 所有 runnable work 结束
-> parent Pipeline FAILED
```

Control Plane `pipeline_run.error_code/error_message` 保存 parent summary；`dataset_run.error_code/error_message` 保存每表 root cause；`step_run`、`reconciliation_result`、`quarantine_batch`、`dataset_attempt_lineage` 提供进一步 drill-down。

故障恢复先读 [`PIPELINE_OPERATIONS_AND_RECOVERY.md`](PIPELINE_OPERATIONS_AND_RECOVERY.md)。核心安全边界：

```text
retryable=true transient -> bounded RETRY
DQ threshold -> fix data/rule then REPLAY
reconciliation fail -> investigate before reprocess
dependency blocked -> recover upstream first
unknown commit -> reconcile before any retry
bounded source gap -> BACKFILL
authoritative reset only -> FULL_REBUILD
```

不要整批 blind retry，也不要为了绿灯关闭 DQ/quarantine。

---

# 3. 为什么 release evidence 要分阶段

真实 environment 检查风险不同：

```text
read-only GET
  < normal provider execution
  < target mutation
  < fault injection
  < Admin session termination
```

所以不能用一个“大一统 smoke test”把所有权限一起拿到。

每一步只在前置证明成立后执行下一步。

---

# 4. 推荐真实 certification 执行顺序

```text
1. exact release/config preparation
2. read-only item smoke
3. control-plane certification
4. strict-merge prerequisites
5. approved Pipeline
6. approved Copy Job / Spark capture
7. approved Warehouse commit/recovery
8. optional ambiguous-COMMIT fault drill
9. optional exact-session termination recovery
10. strict merge all required evidence
11. integration-evidence-validate --require-certified
```

如果某个 release 不承诺 Kafka/Delta provider live support，就不要为了“测试多一点”随便把它们塞进 required evidence。

---

# 5. Credential 怎么处理

Source-controlled approved-run config 只能保存：

```text
env-var name
```

不能保存：

```text
access token
database URL value
password
client secret
signed URL
Authorization header
```

例如：

```json
{
  "control_plane_database_url_env_var": "FABRIC_CONTROL_PLANE_DATABASE_URL",
  "warehouse_database_url_env_var": "FABRIC_WAREHOUSE_DATABASE_URL",
  "warehouse_admin_database_url_env_var": "FABRIC_WAREHOUSE_ADMIN_DATABASE_URL"
}
```

真实 URL 在 runtime environment 中注入。

Admin Warehouse credential 必须和普通 Warehouse credential 分开。

---

# 6. Preflight

先运行 credential-free / non-secret preflight。

示意：

```bash
fabric-framework integration-run-preflight \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --require-ready \
  --output evidence/preflight.json
```

第一次真实调用建议只选 read-only item check。

不要为了 preflight 方便就默认批准所有 mutating checks。

---

# 7. Read-only item smoke

这是最适合做第一条真实 Fabric call 的阶段。

```bash
fabric-framework integration-item-smoke-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --check-id fabric.item.read \
  --evidence-reference artifact:item-read \
  --output evidence/item-read-partial.json
```

它验证：

```text
token path
workspace/item authorization
returned item identity
```

HTTP 200 但 item identity 不匹配不能 PASS。

---

# 8. Control-plane certification

```bash
fabric-framework integration-control-plane-certify-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --check-id control-plane.certify \
  --external-evidence evidence/control-plane-external.json \
  --evidence-reference artifact:control-plane-certification \
  --report-output evidence/control-plane-report.json \
  --output evidence/control-plane-partial.json \
  --allow-conformance-writes
```

它证明 framework repository contract，不等于自动证明：

```text
IAM
private networking
backup/restore
HA/DR
monitoring
retention/governance
```

这些需要独立 enterprise evidence reference。

---

# 9. Pipeline evidence

```bash
fabric-framework integration-pipeline-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/prerequisites.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --check-id fabric.pipeline \
  --dataset-id crm.customer \
  --evidence-reference artifact:pipeline-run \
  --output evidence/pipeline-partial.json \
  --allow-pipeline-execution
```

Fabric Pipeline 显示 `Completed` 还不够。

Framework 还要看到 exact child `dataset_run_id` 的 durable framework outcome 是 `SUCCEEDED`，否则 FAIL。

---

# 10. Copy Job / Spark capture evidence

```bash
fabric-framework integration-capture-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/prerequisites.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --capture-config evidence/capture-run.json \
  --evidence-reference artifact:capture-output \
  --report-output evidence/capture-report.json \
  --output evidence/capture-partial.json \
  --allow-capture-execution
```

PASS 需要：

```text
provider success
+ item-specific post-run observation
+ native correlation
+ verified CaptureReceipt
```

Copy Job 的 provider-native incrementality 和 framework downstream checkpoint 要分开理解。

Spark 的 WATERMARK/CDC capture 如果 framework 负责 progress，需要 frozen upper bound。

---

# 11. Warehouse normal commit/recovery evidence

```bash
fabric-framework integration-warehouse-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/prerequisites.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --warehouse-config evidence/warehouse-run.json \
  --evidence-reference artifact:warehouse-marker \
  --report-output evidence/warehouse-report.json \
  --output evidence/warehouse-partial.json \
  --allow-warehouse-execution
```

Framework 负责同一个 SQL transaction 内：

```text
target mutation
+ framework operation marker
```

Unknown outcome 时：

```text
matching marker -> COMMITTED
marker absent -> UNRESOLVED
```

普通 run 不会因为 marker absent 就重跑。

---

# 12. Ambiguous-COMMIT fault drill

只有 normal Warehouse path 已经 PASS 后，才考虑 fault drill。

```bash
fabric-framework integration-warehouse-fault-drill-run \
  --config dev-integration-runner.json \
  --spec evidence-spec.json \
  --prerequisite-manifest evidence/warehouse-prerequisites.json \
  --release-manifest release-manifest.json \
  --config-dir config/datasets \
  --fault-config evidence/warehouse-fault-drill.json \
  --evidence-reference artifact:warehouse-fault \
  --report-output evidence/warehouse-fault-report.json \
  --output evidence/warehouse-fault-partial.json \
  --allow-warehouse-fault-injection
```

这个 check 证明的是：

```text
真的发生 provider/driver exception
+ fault identity 被验证
+ marker 最终证明 COMMITTED
+ framework 恢复 SUCCEEDED
```

普通 transaction return 永远不能假装成 real-fault PASS。

---

# 13. Session termination recovery

这是一个更高权限、可选的 recovery path。

它只用于这种分支：

```text
真实/已验证 fault
+ marker probe UNRESOLVED
+ exact target session identity 已捕获
```

启用需要两层明确授权：

```text
run config:
  enable_session_termination_recovery = true

CLI:
  --allow-warehouse-session-termination
```

`--allow-warehouse-fault-injection` **不等于** Admin `KILL` 权限。

Admin credential 也必须单独配置。

安全证明成立后：

```text
UNKNOWN -> NOT_COMMITTED
```

这里只说明“这个 operation 可以在未来安全 retry”；runner 不会自动重新执行 mutation。

---

# 14. Evidence merge

每个阶段输出 partial manifest。

合并时：

```text
NOT_RUN = 没有该阶段证据
相同 substantive evidence = 可合并
不同 rerun evidence = conflict
```

不会使用：

```text
latest wins
PASS wins
FAIL wins
```

这是故意的，避免两次相互矛盾的真实运行被静默覆盖。

最后：

```bash
fabric-framework integration-evidence-validate \
  --spec evidence-spec.json \
  --manifest evidence/merged.json \
  --require-certified
```

---

# 15. 日常运维和 certification 的边界

如果只是正常业务 pipeline：

```text
不需要每次都跑 certification/fault drill
```

Approved evidence runner 是 release/certification/controlled validation surface，不是把所有生产 batch 都变成一次 certification suite。

正常 runtime 使用 framework 的 dispatch、DQ/quarantine、retry/replay/backfill/rebuild 和 unknown-outcome contracts；release evidence 在需要证明 capability/environment 时执行并保留。

---

# 16. 什么时候可以 release

Human 侧只需要知道一条：

```text
CI green 不等于 Fabric/production proven
```

当前 exact release gate、哪些能力只有 CI contract、哪些已经有真实 retained evidence，以：

```text
docs/machine/STATE.md
docs/machine/CAPABILITIES.md
```

为准。
