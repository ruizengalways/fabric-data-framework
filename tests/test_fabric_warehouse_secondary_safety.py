from uuid import uuid4

from fabric_data_framework.contracts.recovery import UnknownOutcomeResolution
from fabric_data_framework.recovery.fabric_warehouse import FabricWarehouseTargetCommitProbe
from fabric_data_framework.recovery.target_probe import TargetCommitProbeRequest
from fabric_data_framework.target_operations import TargetOperationStatus


class _EmptyMarkerStore:
    def read_markers(self, operation_key):
        return ()

    def marker_reference(self, operation_key):
        return f"marker:{operation_key}"


class _BrokenSecondaryReader:
    def lookup(self, request):
        raise RuntimeError(
            "query insights failed password=should-not-persist Authorization: Bearer secret"
        )


def test_warehouse_secondary_correlation_exception_retains_type_only():
    request = TargetCommitProbeRequest(
        operation_key="a" * 64,
        dataset_id="sales.order",
        operation_kind="MERGE",
        target_reference="warehouse.dbo.sales_order",
        effective_config_hash="b" * 64,
        input_fingerprint="c" * 64,
        current_status=TargetOperationStatus.UNKNOWN,
        current_version=2,
        owner_dataset_run_id=uuid4(),
        owner_attempt=1,
    )
    probe = FabricWarehouseTargetCommitProbe(
        marker_store=_EmptyMarkerStore(),
        secondary_correlation_reader=_BrokenSecondaryReader(),
    )

    evidence = probe.probe(request)

    assert evidence.resolution is UnknownOutcomeResolution.UNRESOLVED
    assert evidence.detail is not None
    assert "secondary correlation lookup failed: RuntimeError" in evidence.detail
    assert "should-not-persist" not in evidence.detail
    assert "password=" not in evidence.detail.lower()
    assert "authorization" not in evidence.detail.lower()
