from pathlib import Path

from fabric_data_framework.capture import (
    load_capture_selections,
    validate_capture_selection,
)
from fabric_data_framework.delivery import load_dataset_configs
from fabric_data_framework.metadata import DEFAULT_CAPABILITY_REGISTRY


EXAMPLE_ROOT = Path("examples/capture-patterns")


def test_capture_pattern_examples_are_typed_and_onboarding_claims_remain_valid():
    configs = load_dataset_configs(EXAMPLE_ROOT / "configs")
    selections = load_capture_selections(EXAMPLE_ROOT / "capture-selections.json")
    configs_by_id = {item.dataset_id: item for item in configs}

    assert len(configs) == 5
    assert {item.dataset_id for item in selections} == set(configs_by_id)

    for selection in selections:
        config = configs_by_id[selection.dataset_id]
        report = validate_capture_selection(config, selection)
        assert report.dataset_id == config.dataset_id
        DEFAULT_CAPABILITY_REGISTRY.validate(config)
