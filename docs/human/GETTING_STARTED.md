# Getting Started

## 1. 先明确：你为什么要打开这个 repo

### 情况 A：只是接一个新 dataset

你大概率应该去：

```text
fabric-customer
```

这个 repo 主要作为依赖和 contract reference 使用。

### 情况 B：framework 缺一个可复用能力

例如需要新的 capture semantics、apply strategy、provider adapter、recovery/evidence contract，才在这里开发。

## 2. 本地开发安装

```bash
python -m pip install -e '.[dev]'
pytest
```

这会以 editable mode 安装 framework，适合本地开发和测试。

常用检查：

```bash
python -m compileall -q src tests
ruff check --isolated --select E4,E7,E9,F src tests
python -m pip check
pytest -q
```

CI 会在 Python 3.11 / 3.13 上重新验证并构建 wheel。

## 3. CLI 是干什么的

CLI 主要是 **开发/验证/交付/证据工具**，不是要求你在 Fabric 里打开一个 terminal 手工跑所有 pipeline。

典型用途：

```text
本地
  semantic validation
  metadata/release materialization
  preflight
  evidence merge/validate

CI/CD 或受控运维环境
  approved item smoke
  control-plane certification
  approved Pipeline/Copy/Spark/Warehouse evidence run
```

先看：

```bash
fabric-framework --help
```

再看某个命令：

```bash
fabric-framework <command> --help
```

## 4. 如何打 immutable wheel

生产/共享环境不要依赖 editable install。

本地如果需要按 CI 相同方式构建 wheel：

```bash
python -m pip install 'setuptools>=77'
python -m pip wheel . --no-deps --no-build-isolation -w dist
(cd dist && sha256sum *.whl)
```

得到类似：

```text
dist/fabric_data_framework-<version>-py3-none-any.whl
```

正式 release 应由 repository release workflow 生成并保留 checksum/provenance，不要手工把一个未知本地 wheel 当生产 artifact。

## 5. Fabric 里怎么用

推荐稳定模式：

```text
GitHub Release wheel
   -> Fabric Environment
   -> Custom Libraries
   -> Publish Environment
   -> Notebook / Spark Job Definition / Pipeline child
```

代码在 Fabric runtime 中正常 import：

```python
import fabric_data_framework
```

或者 import 具体 contract/runtime module。

关键点：

- wheel 是 immutable artifact；
- Fabric Environment/site-packages 不是 source repo；
- 不在 Fabric 中直接修改 package 源码；
- source of truth 永远是 Git；
- UAT/PROD 应记录 Git SHA、wheel SHA256、release manifest。

## 6. DEV 可以怎么快一点

本地开发：

```bash
pip install -e '.[dev]'
```

Fabric DEV 环境如果只是快速试验，可以上传 development wheel；但进入 UAT/PROD 前必须换成 exact immutable artifact。

不要把下面这种方式作为稳定生产依赖：

```text
%pip install git+https://...
```

原因是它把 runtime build、Git access、network availability 和 source state 混到一起，不利于 reproducibility 和 audit。

## 7. 一个新 customer repo 怎么消费 framework

推荐关系：

```text
fabric-data-framework
  -> 发布 immutable wheel

fabric-customer
  -> pin framework version/artifact
  -> 保存 DatasetConfig
  -> 保存 customer-specific extension
  -> 保存 Fabric item/config deployment content
```

Customer repo 不复制 framework 源码。

## 8. 新 dataset 的正常流程

```text
理解 source semantics
  ↓
选择 capture pattern + Bronze meaning + Silver apply
  ↓
写 DatasetConfig（customer repo）
  ↓
跑 semantic onboarding validation
  ↓
配置 environment-local physical binding
  ↓
只有确实需要时才加 bounded extension
  ↓
生成/验证 release artifact
  ↓
部署到 DEV
  ↓
按需要跑 approved evidence
```

具体怎么选模式看：

```text
docs/human/DATASET_ONBOARDING.md
```

## 9. 什么时候需要 control plane

Control plane 保存的是运行/部署/evidence state，不替代 source-controlled DatasetConfig。

可以理解为：

```text
Git/release artifact = 完整 immutable semantic truth
SQL control plane     = deployed identity + runtime state + audit/evidence
```

Runtime 不会偷偷给生产数据库做 schema migration。

需要升级 schema 时，使用明确的 migration/deployment 步骤，不要让业务执行路径自动改 schema。

## 10. 运行真实 Fabric evidence 前

顺序永远从低风险开始：

```text
read-only item smoke
  -> control-plane certification
  -> normal provider path
  -> target mutation
  -> optional fault injection
  -> optional Admin session termination
```

不要一上来就跑 destructive/fault/KILL 类检查。

完整顺序见：

```text
docs/human/OPERATIONS.md
```
