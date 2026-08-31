from uuid import uuid4

from fabric_data_framework.evidence.integration_runner import IntegrationCheckPhysicalBinding


def test_pipeline_physical_binding_can_retain_customer_owned_dataset_id():
    binding = IntegrationCheckPhysicalBinding(
        check_id="fabric.pipeline",
        workspace_id=uuid4(),
        item_id=uuid4(),
        dataset_id="health.patient",
    )

    assert binding.dataset_id == "health.patient"
    assert binding.model_dump(mode="json")["dataset_id"] == "health.patient"


def test_dataset_id_remains_optional_for_non_pipeline_bindings():
    binding = IntegrationCheckPhysicalBinding(
        check_id="fabric.item.read",
        workspace_id=uuid4(),
        item_id=uuid4(),
    )

    assert binding.dataset_id is None
