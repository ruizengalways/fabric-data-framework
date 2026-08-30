# Contracts package

Provider-neutral immutable contracts and semantic state machines live here.

```text
base.py              immutable strict Pydantic base
schema.py            schema intent and compatibility policy
audit.py             pipeline/dataset/step audit models
reconciliation.py    reconciliation result models
quarantine.py        quarantine batch models
target_operation.py  semantic target-mutation identity/lifecycle
capture_receipt.py   capture handoff receipt
dispatch.py          orchestration request/outcome
execution_plan.py    execution plan contracts
rebuild.py           rebuild-state contracts
recovery.py          retry/reprocess/unknown-outcome contracts
replay.py            quarantine replay contracts
```

Use explicit submodule imports; `contracts/__init__.py` is namespace-only.
