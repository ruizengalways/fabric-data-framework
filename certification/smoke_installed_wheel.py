"""Thin acceptance smoke that must be launched by an interpreter using the wheel install."""

from __future__ import annotations

import argparse
import json

from fabric_data_framework.certification import attest_installed_wheel


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True)
    args = parser.parse_args()
    result = attest_installed_wheel(args.wheel)
    print(
        json.dumps(
            {
                "status": "PASS",
                "framework_version": result.framework_version,
                "wheel_sha256": result.wheel_sha256,
                "installed_root": str(result.installed_root),
                "checked_package_files": result.checked_package_files,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
