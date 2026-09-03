"""Packaged certification policy mirrors for notebook-only execution.

The canonical release JSON files remain the source-controlled release policy. Tests
lock these in-package mirrors by semantics to those canonical files so a wheel can
materialize the same exact spec without requiring a repository checkout.
"""

from __future__ import annotations

from fabric_data_framework.evidence.integration_evidence import IntegrationEvidenceSpec
from fabric_data_framework.evidence.release_readiness import ReleaseReadinessSpec


_INTEGRATION_TEMPLATE = {
    "evidence_schema_version": 1,
    "environment": "DEV",
    "domain": "candidate-template",
    "framework_version": "0.4.0",
    "release_hash": None,
    "domain_release_hash": None,
    "checks": [
        {"check_id": "fabric.item.read", "kind": "FABRIC_ITEM_READ", "required": True, "description": "Enterprise identity and read-only workspace/item authorization smoke."},
        {"check_id": "control.cert", "kind": "CONTROL_PLANE_CERTIFICATION", "required": True, "description": "Selected production control-plane backend certification evidence."},
        {"check_id": "fabric.pipeline", "kind": "FABRIC_PIPELINE_RUN", "required": True, "description": "Approved Fabric Pipeline execution with exact framework and native correlation evidence."},
        {"check_id": "fabric.copy", "kind": "FABRIC_COPY_JOB_CAPTURE", "required": True, "description": "Approved Copy capture with verified CaptureReceipt and retained provider evidence."},
        {"check_id": "fabric.spark", "kind": "FABRIC_SPARK_CAPTURE", "required": True, "description": "Approved bounded Spark capture with verified CaptureReceipt and retained provider evidence."},
        {"check_id": "warehouse.commit", "kind": "FABRIC_WAREHOUSE_TARGET_COMMIT", "required": True, "description": "Warehouse target mutation and operation marker commit semantics for the exact candidate."},
        {"check_id": "warehouse.ambiguous_commit", "kind": "FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL", "required": True, "description": "Real ambiguous-COMMIT drill with retained fail-closed recovery evidence."},
        {"check_id": "kafka.live", "kind": "KAFKA_PROVIDER", "required": False, "description": "Optional for 0.4 unless Debezium/Kafka is explicitly promoted into GA certification scope."}
    ]
}


_READINESS_SPEC = {
    "readiness_schema_version": 1,
    "framework_version": "0.4.0",
    "gates": [
        {"gate_id": "source.tests", "kind": "SOURCE_VERIFICATION", "required": True, "description": "Python 3.11/3.13 tests, architecture checks and package checks for the exact candidate."},
        {"gate_id": "wheel.integrity", "kind": "WHEEL_INTEGRITY", "required": True, "description": "Exact candidate wheel is retained, checksum-verified and install-tested."},
        {"gate_id": "customer.compatibility", "kind": "CUSTOMER_COMPATIBILITY", "required": True, "description": "fabric-customer exact-candidate compatibility validation is retained."},
        {"gate_id": "fabric.identity", "kind": "FABRIC_IDENTITY", "required": True, "integration_check_id": "fabric.item.read", "description": "Enterprise identity and read-only workspace/item authorization are proven in Fabric."},
        {"gate_id": "control.certification", "kind": "CONTROL_PLANE", "required": True, "integration_check_id": "control.cert", "description": "Selected production control-plane backend certification is retained."},
        {"gate_id": "fabric.pipeline", "kind": "FABRIC_PIPELINE", "required": True, "integration_check_id": "fabric.pipeline", "description": "Approved Fabric Pipeline execution has exact framework and native correlation evidence."},
        {"gate_id": "fabric.copy", "kind": "FABRIC_COPY_CAPTURE", "required": True, "integration_check_id": "fabric.copy", "description": "Approved Copy capture path has verified CaptureReceipt and retained provider evidence."},
        {"gate_id": "fabric.spark", "kind": "FABRIC_SPARK_CAPTURE", "required": True, "integration_check_id": "fabric.spark", "description": "Approved bounded Spark capture path has verified CaptureReceipt and retained provider evidence."},
        {"gate_id": "warehouse.commit", "kind": "STATE_COMMIT_SAFETY", "required": True, "integration_check_id": "warehouse.commit", "description": "Warehouse target mutation and operation marker commit semantics are proven for the exact artifact."},
        {"gate_id": "full.replace", "kind": "FULL_REPLACE", "required": True, "description": "Representative live FULL to REPLACE dataset proof is retained."},
        {"gate_id": "watermark.scd1", "kind": "WATERMARK_SCD1", "required": True, "description": "Representative live WATERMARK to SCD1 dataset proof is retained."},
        {"gate_id": "watermark.scd2", "kind": "WATERMARK_SCD2", "required": True, "description": "Representative live WATERMARK to SCD2 history proof is retained."},
        {"gate_id": "retry.idempotency", "kind": "RETRY_IDEMPOTENCY", "required": True, "description": "Retry/rerun failure drill proves idempotent final state and no unsafe progress advance."},
        {"gate_id": "reconciliation.fail_closed", "kind": "RECONCILIATION_FAIL_CLOSED", "required": True, "description": "Provider success cannot override failed semantic reconciliation."},
        {"gate_id": "warehouse.ambiguous_commit", "kind": "AMBIGUOUS_COMMIT_RECOVERY", "required": True, "integration_check_id": "warehouse.ambiguous_commit", "description": "Real ambiguous-COMMIT drill and fail-closed recovery evidence are retained."},
        {"gate_id": "external.cdc.debezium", "kind": "EXTERNAL_CDC", "required": False, "integration_check_id": "kafka.live", "description": "Optional for 0.4.0 unless Debezium/Kafka is explicitly included in the GA certification scope."}
    ]
}


def integration_template() -> IntegrationEvidenceSpec:
    return IntegrationEvidenceSpec.model_validate(_INTEGRATION_TEMPLATE)


def readiness_spec() -> ReleaseReadinessSpec:
    return ReleaseReadinessSpec.model_validate(_READINESS_SPEC)


__all__ = ["integration_template", "readiness_spec"]
