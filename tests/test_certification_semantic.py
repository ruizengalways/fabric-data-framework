from fabric_data_framework.certification import run_semantic_acceptance


def test_framework_owned_semantic_acceptance_is_self_contained():
    assert run_semantic_acceptance() == {
        "metadata.config": "PASS",
        "incremental.watermark": "PASS",
        "cdc.normalization": "PASS",
    }
