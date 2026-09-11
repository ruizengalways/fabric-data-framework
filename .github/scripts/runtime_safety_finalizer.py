from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement target, found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


rest_path = "src/fabric_data_framework/adapters/fabric/rest.py"
replace_once(
    rest_path,
    '''            response = self._opener(request, timeout=self._request_timeout_seconds)\n            status_value = getattr(response, "status", None)\n            status = int(status_value if status_value is not None else response.getcode())\n            response_headers = response.headers\n            raw = response.read()\n''',
    '''            response = self._opener(request, timeout=self._request_timeout_seconds)\n            try:\n                status_value = getattr(response, "status", None)\n                status = int(status_value if status_value is not None else response.getcode())\n                response_headers = response.headers\n                raw = response.read()\n            finally:\n                close = getattr(response, "close", None)\n                if callable(close):\n                    close()\n''',
)
replace_once(
    rest_path,
    '''        except HTTPError as exc:\n            raw = exc.read()\n            response_headers = exc.headers\n            payload_obj: object | None = None\n''',
    '''        except HTTPError as exc:\n            try:\n                raw = exc.read()\n                response_headers = exc.headers\n            finally:\n                exc.close()\n            payload_obj: object | None = None\n''',
)

capture_path = "src/fabric_data_framework/adapters/fabric/capture_transports.py"
replace_once(
    capture_path,
    '''from .rest import FabricJobInstance, FabricJobStatus, FabricRestClient\n''',
    '''from .rest import FabricJobInstance, FabricJobStatus, FabricRestClient\nfrom ...evidence.safety import sanitize_audit_details, sanitize_audit_value\n''',
)
replace_once(
    capture_path,
    '''    return {\n        "workspace_id": str(workspace_id),\n        "item_id": str(item_id),\n        "job_instance_id": str(job.job_instance_id),\n        "root_activity_id": str(job.root_activity_id) if job.root_activity_id else None,\n        "job_type": job.job_type,\n        "remote_status": job.status.value,\n        "failure_reason": job.failure_reason,\n        "provider_start_time_present": job.start_time_utc is not None,\n        "provider_end_time_present": job.end_time_utc is not None,\n    }\n''',
    '''    return sanitize_audit_details(\n        {\n            "workspace_id": str(workspace_id),\n            "item_id": str(item_id),\n            "job_instance_id": str(job.job_instance_id),\n            "root_activity_id": str(job.root_activity_id) if job.root_activity_id else None,\n            "job_type": job.job_type,\n            "remote_status": job.status.value,\n            "failure_reason": sanitize_audit_value(job.failure_reason),\n            "provider_start_time_present": job.start_time_utc is not None,\n            "provider_end_time_present": job.end_time_utc is not None,\n        }\n    ) or {}\n''',
)
replace_once(
    capture_path,
    '''            "observation": dict(observation.diagnostics),\n''',
    '''            "observation": sanitize_audit_details(observation.diagnostics) or {},\n''',
)

business_test = "tests/test_business_path_driver.py"
replace_once(
    business_test,
    '''    assert "status" not in receipt.model_fields\n    assert "passed" not in receipt.model_fields\n''',
    '''    assert "status" not in BusinessPathDriverReceipt.model_fields\n    assert "passed" not in BusinessPathDriverReceipt.model_fields\n''',
)
