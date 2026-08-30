from fabric_data_framework import cli_router


def _base_args():
    return [
        "--config",
        "runner.json",
        "--spec",
        "spec.json",
        "--prerequisite-manifest",
        "prerequisite.json",
        "--release-manifest",
        "release.json",
        "--config-dir",
        "configs",
        "--fault-config",
        "fault.json",
        "--evidence-reference",
        "artifact:fault",
        "--report-output",
        "report.json",
        "--output",
        "partial.json",
        "--allow-warehouse-fault-injection",
    ]


def test_session_termination_authorization_is_false_by_default():
    args = cli_router._warehouse_fault_parser().parse_args(_base_args())

    assert args.allow_warehouse_fault_injection is True
    assert args.allow_warehouse_session_termination is False


def test_session_termination_requires_its_own_explicit_flag():
    args = cli_router._warehouse_fault_parser().parse_args(
        _base_args() + ["--allow-warehouse-session-termination"]
    )

    assert args.allow_warehouse_fault_injection is True
    assert args.allow_warehouse_session_termination is True
