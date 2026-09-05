"""Recovery package.

Primary operator/runtime surfaces:

- ``recovery.runtime``: bounded retry and unknown-outcome reconciliation;
- ``recovery.pipeline``: conservative Pipeline failure diagnosis/recovery plan;
- ``recovery.replay``: governed quarantine replay;
- ``recovery.rebuild``: backfill/full-rebuild contracts;
- ``recovery.target_probe`` / ``recovery.fabric_warehouse``: target and Warehouse recovery.
"""
