# 新项目怎么从 0 建起来

这份 runbook 回答一个很实际的问题：

```text
我刚接到一个新的 Fabric data engineering 项目，
应该怎么在本机 / jumpbox 建 customer repo，
怎么放几十到几百张表，
什么时候用 CLI，什么时候进入 Fabric？
```

## 1. CLI 在哪里运行

`fabric-framework` 是开发、验证、交付和受控运维工具。

它通常运行在：

```text
开发机
jumpbox / build agent
CI/CD runner
受控 operator environment
```

它不是要求你进入 Fabric 后找一个 terminal 手工执行日常 pipeline。

典型起点：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install fabric-data-framework
```

如果你正在开发 framework 本身，则用 editable install：

```bash
python -m pip install -e '.[dev]'
```

## 2. 初始化一个 customer/domain repo

例如新项目叫 `health`：

```bash
fabric-framework project-init ./fabric-health --domain health
cd fabric-health
```

会生成类似：

```text
fabric-health/
├─ fabric-project.json
├─ README.md
├─ config/
│  ├─ datasets/
│  ├─ capture/
│  └─ environments/
├─ deploy/
├─ docs/
│  └─ dataset-inventory.csv
├─ src/
└─ tests/
```

`project-init` 只创建 source-controlled skeleton。

它不会：

- 根据 table name 猜 primary key；
- 猜 `updated_at` 是否安全；
- 猜 delete 是否可见；
- 自动决定 SCD1/SCD2；
- 创建 Fabric workspace / Lakehouse / Warehouse；
- 写 production control plane；
- 保存 secret。

这些行为如果自动猜，反而会让 framework 不可信。

## 3. 已经有 repo 怎么办

默认情况下，`project-init` 要求目标目录为空，防止误覆盖。

如果你明确要给已有 repo 补 skeleton：

```bash
fabric-framework project-init . --domain health --allow-existing
```

规则是：

```text
只补缺少的 scaffold file
已有文件永不覆盖
已有 fabric-project.json 的 domain 必须一致
```

所以它适合在已有 corporate repo 中逐步采用 framework，而不是强制重建 repo。

## 4. 100 张表需要几个 repo

通常一个业务 domain / data product boundary 一个 customer repo 就够了。

例如你拿到 100 张表：

```text
50 张以 full snapshot 为主要 capture
20 张最终需要 SCD2
20 张最终需要 SCD1
10 张来自 Debezium CDC
```

不要直接拆成：

```text
repo-full
repo-scd1
repo-scd2
repo-debezium
```

因为这四个词不是同一个维度。

Framework 的模型是：

```text
source semantics
  -> capture strategy
  -> Bronze meaning
  -> apply strategy
  -> physical execution engine
```

例如：

```text
Debezium CDC + SCD1
Debezium CDC + SCD2
Full Snapshot + SCD1
Full Snapshot + Snapshot Diff + SCD2
Watermark + Lookback + SCD2
```

都可能是合法组合。

所以 repo boundary 应该跟业务 ownership、release boundary、权限和生命周期走，而不是跟 SCD 类型走。

## 5. 100 张表怎么组织

推荐：

```text
config/datasets/
  patient.json
  provider.json
  claim.json
  encounter.json
  ...
```

一张 logical dataset 一个 `DatasetConfig`。

然后在每个 config 内描述：

```text
capture strategy
apply strategy
business / merge key
watermark / ordering
execution engine
execution_group
criticality
retry / timeout / concurrency
quality
reconciliation
extensions
```

不要把“50 张 full refresh”硬编码成 50 个 notebook 分支。

Framework 应该读取 50 份 metadata，用统一 runtime 调度。

## 6. execution_group 是干什么的

同一个 repo 中可以按 operational workload 分组，例如：

```text
health_reference
health_core_daily
health_cdc
health_heavy_snapshot
```

然后统一调度同一个 group。

这比按 SCD1/SCD2 拆 repo 更合理，因为 execution group 描述的是：

```text
什么时候一起跑
并发上限
依赖
优先级
运维边界
```

而 SCD1/SCD2 描述的是 target apply semantics。

## 7. 第一步不是写 JSON，而是做 inventory

初始化后先填：

```text
docs/dataset-inventory.csv
```

至少确认：

```text
source system/object
business key
change shape
ordering signal
watermark
hard/soft delete signal
late/back-dated update 风险
history requirement
capture semantics
Bronze meaning
apply strategy
execution group
```

如果 source owner 不能回答这些问题，先标记 unknown，不要让脚手架替你猜。

## 8. 然后写 DatasetConfig

每个 dataset 一个 JSON。

例如一个 current-state watermark dataset，关键点可能是：

```text
capture = WATERMARK
apply = SCD1
merge_key = stable PK
watermark = updated_at + tie breaker / overlap
```

一个 Debezium history dataset 可能是：

```text
capture = CDC
apply = SCD2
business_key = stable business key
ordering = source event position / sequence
```

但具体字段必须由真实 source semantics 决定。

## 9. 全量校验，不要一张张手工跑

当 config 和 semantic selections 都准备好后：

```bash
fabric-framework capture-semantic-onboarding-validate \
  --config-dir config/datasets \
  --selections config/capture/semantic-selections.json \
  --require-all
```

`--require-all` 很重要。

对于 100 张表，它能防止：

```text
99 张已经做 semantic onboarding
1 张忘了做
```

然后再进入 release/deployment 流程。

## 10. DEV / UAT / PROD 的物理信息放哪里

建议：

```text
config/environments/dev.json
config/environments/uat.json
config/environments/prod.json
```

这里保存：

```text
workspace/item physical IDs
non-secret binding metadata
secret env-var names / secret-store references
```

不要保存：

```text
access token
password
client secret
raw connection credential
```

Semantic DatasetConfig 仍然是 immutable source-controlled truth。

## 11. GitHub 的正常流程

一个合理的本地到企业 Git 流程是：

```text
拿到项目
  -> 本地 / jumpbox 建 repo
  -> project-init
  -> 做 inventory
  -> 写 DatasetConfig
  -> semantic validate
  -> unit / contract tests
  -> git commit
  -> push company GitHub
  -> PR / CI
  -> immutable release artifact
  -> DEV deployment
  -> UAT / PROD promotion
```

所以“CLI 是本地开发用的”这个理解大方向对，但还要补一句：

```text
CLI 也可以在 CI/CD 和受控 operator 环境中运行。
```

## 12. 什么情况下才拆成多个 customer repo

考虑拆 repo 的理由应该是：

- 不同业务 ownership；
- 独立 release cadence；
- 独立权限 / regulatory boundary；
- 明显不同的 deployment lifecycle；
- repo 大到 ownership 和 CI blast radius 已经不可控。

不应该仅仅因为：

```text
这 20 张是 SCD2
那 10 张是 Debezium
```

就拆 repo。

## 13. framework repo 和 customer repo 的边界

```text
fabric-data-framework
  reusable capture/apply/runtime/recovery/provider/evidence code
  immutable wheel

fabric-customer / fabric-health
  DatasetConfig
  source semantic decisions
  bounded domain extensions
  Fabric deployment content
  environment bindings
  domain tests/docs
```

Customer repo 不复制 framework source。

如果新项目暴露出一个真正通用的缺口，再把 reusable capability 提回 `fabric-data-framework`。
