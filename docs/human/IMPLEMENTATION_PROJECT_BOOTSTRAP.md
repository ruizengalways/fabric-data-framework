# 新 implementation/domain project 怎么从 0 建起来

这份 runbook 讲的是**真实业务项目的 framework consumer repo**，不是 `fabric-customer` simulator。

## 1. 先区分 repo

```text
fabric-data-framework
  reusable framework + wheel certification

fabric-customer
  independent source-system simulator/testbed
  no framework dependency

fabric-health / fabric-finance / ...
  real implementation/domain repo
  may depend on released framework wheel
```

真实项目里的 DatasetConfig、业务 mapping、DQ policy、execution group、环境 binding 和 deployment content 放 implementation/domain repo。

## 2. CLI 在哪里运行

`fabric-framework` 主要运行在开发机、jumpbox、CI/CD runner 或受控 operator environment。它不是要求你在 Fabric 里找 terminal 手工跑日常 Pipeline。

安装 released/approved wheel 后：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install fabric-data-framework
```

如果你正在开发 framework 本身，才在 framework source repo 使用 editable install：

```bash
python -m pip install -e '.[dev]'
```

## 3. 初始化真实项目 repo

例如 `health`：

```bash
fabric-framework project-init ./fabric-health --domain health
cd fabric-health
```

典型 skeleton：

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
├─ src/
└─ tests/
```

`project-init` 只创建 source-controlled skeleton。它不会猜 primary key、水位列、delete 语义、SCD1/SCD2，也不会创建真实 Fabric workspace/Lakehouse/Warehouse 或保存 secret。

已有 repo 可以明确使用：

```bash
fabric-framework project-init . --domain health --allow-existing
```

原则是补缺失 scaffold，不覆盖已有业务文件。

## 4. 100 张表通常仍然是一个 domain repo

如果同一个 data product/domain 有：

```text
50 full snapshot
20 watermark + SCD2
20 watermark + SCD1
10 Debezium CDC
```

不要按技术策略拆成四个 repo。Repo boundary 应优先跟业务 ownership、release cadence、access boundary 和 data product boundary 对齐。

技术差异放在每张 dataset 的 source-controlled contract/config 中，并用 execution groups 控制运行组织。

## 5. 每张新数据先写 source facts，再写 framework config

先确认：

- 第一次/以后能拿什么；
- 主键与 ordering evidence；
- delete 是否可见；
- late/back-dated update；
- provider 是否 collapse changes；
- 业务需要 current 还是 history，以及 fidelity。

然后才选择 capture/apply。具体 decision tree 看 `DATASET_ONBOARDING.md`。

## 6. 静态验证

```bash
fabric-framework project-validate .
```

这是 source-controlled contract validation，不是 real Fabric certification。它不证明 source connectivity、Fabric permissions、Pipeline/Spark execution 或 target commit。

## 7. 与 fabric-customer simulator 配合

`fabric-customer` 可以作为独立测试源，但不是你的 project config repo。

推荐：

```text
fabric-customer frozen workload
  -> implementation-owned landing
  -> fabric-health config/runtime
  -> normalized business output
  -> compare customer expected truth
```

比较 v1/v2 时记录 customer `workload_digest`，并确保两个 implementation run 使用相同 digest。

## 8. Fabric 中消费 Framework

稳定模式：

```text
approved/released framework wheel
  -> Fabric Environment
  -> Publish
  -> Notebook / Spark Job / Pipeline child
```

Implementation repo 记录应该部署什么；真实 workspace/item UUID、runtime credentials 和 state 保持环境本地。

## 9. Framework certification 和 project validation 不要混

```text
framework repo certification
  proves exact framework wheel

implementation project validation
  proves project config/contracts

end-to-end DEV scenario
  proves implementation + real Fabric + source workload
```

Framework certification 从 `CERTIFICATION_LIFECYCLE.md` / `FRAMEWORK_DEVELOPER_CERTIFICATION.md` 开始。

## 10. 推荐交付顺序

```text
framework approved wheel
-> implementation repo project-validate
-> DEV Environment publish
-> source connectivity / customer workload
-> DEV end-to-end
-> UAT promotion
-> PROD promotion
```

不要把 `fabric-customer` 重新变成 implementation repo，也不要为了方便把 framework certification artifacts 搬回 simulator。
