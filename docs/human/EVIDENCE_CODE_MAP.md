# Evidence 代码怎么读

如果你只是接新 dataset，通常不需要看这一层。这里是 framework 用来证明“某个 exact release 在 approved environment 里真的满足既有 contract”的代码。

## 阅读顺序

```text
src/fabric_data_framework/evidence/
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

先看 `integration_evidence.py`，理解 PASS / FAIL / NOT_RUN、spec、result 和 manifest。然后看 `integration_checks.py`，理解 provider/runtime 的事实怎样被安全投影成 evidence。`integration_evidence_merge.py` 负责 staged evidence 的严格合并；`integration_runner.py` 负责 credential-free preflight。

只有需要理解真实环境检查时，才继续看 `approved_*_runner.py`。

## 这层不负责什么

它不重新定义：

```text
DatasetConfig semantics
capture fidelity
SCD1/SCD2 semantics
provider transport behavior
target commit truth
recovery tri-state
```

这些真相仍然属于 core semantic/runtime/provider/recovery 层。Evidence 只能证明它们，不能为了“让检查通过”在这里复制或改变语义。

## 为什么根目录还有旧文件名

例如：

```text
integration_evidence.py
approved_capture_runner.py
approved_warehouse_runner.py
```

这些根目录文件现在只是 compatibility alias，保证已有 import 不突然失效。实际 implementation 在 `evidence/`。

新代码应该从新路径导入；旧路径只用于兼容已有调用方。
