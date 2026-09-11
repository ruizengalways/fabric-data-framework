from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement target, found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def append_section(path: str, heading: str, body: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if heading in text:
        raise SystemExit(f"{path}: section already exists: {heading}")
    target.write_text(text.rstrip() + "\n\n" + heading + "\n\n" + body.strip() + "\n", encoding="utf-8")


state = "docs/internal/STATE.md"
replace_once(state, "  exact_candidate_source_selected: true\n", "  exact_candidate_source_selected: false\n")
replace_once(
    state,
    "  current_source_candidate_git_sha: 81b574fb79bcc5e74cb9eee6d0644c6de8ef7ffd\n",
    "  current_source_candidate_git_sha: not_selected_after_runtime_safety_hardening\n",
)
replace_once(
    state,
    "  current_source_framework_artifact_sha256: 5ee9a032d242f3a164ccfbfcfe5b646d91e6f35dbf603f21735b745dda6cead6\n",
    "  current_source_framework_artifact_sha256: not_selected_after_runtime_safety_hardening\n",
)
replace_once(
    state,
    "  current_source_requires_new_exact_artifact_before_release_claim: false\n",
    "  current_source_requires_new_exact_artifact_before_release_claim: true\n",
)
replace_once(state, "  candidate_bytes_must_not_change: true\n", "  candidate_bytes_must_not_change: false\n")
replace_once(state, "  selected_candidate:\n", "  superseded_scd2_key_contract_candidate:\n")
replace_once(state, "    status: selected_not_frozen\n", "    status: superseded_by_runtime_safety_hardening\n")
replace_once(state, "  exact_current_candidate_selected: true\n", "  exact_current_candidate_selected: false\n")
replace_once(
    state,
    "  current_source_installed_wheel_acceptance: passed\n",
    "  current_source_installed_wheel_acceptance: not_run_for_new_current_source\n",
)
replace_once(
    state,
    "next_boundary:\n  - obtain and live-verify the approved isolated DEV Fabric workspace/lakehouse identity and runtime credentials\n",
    "next_boundary:\n  - merge the runtime-safety hardening only after exact PR-head source and installed-wheel gates pass\n  - build and retain the exact post-merge main wheel; independently verify its inner SHA256\n  - record a new exact executable candidate before constructing live Fabric integration inputs\n  - obtain and live-verify the approved isolated DEV Fabric workspace/lakehouse identity and runtime credentials\n",
)
replace_once(
    state,
    "## Selected exact current candidate after the SCD2 key-contract repair\n",
    "## Superseded SCD2 key-contract candidate\n",
)
replace_once(
    state,
    "This selects the exact executable candidate after the SCD2 key-contract repair. It does **not** freeze 0.4, construct integration inputs, execute Microsoft Fabric, authorize release, or claim Fabric PASS. Candidate/evidence identity remains `framework_artifact_sha256 + integration_inputs_hash`; `integration_inputs_hash` is still not yet constructed.\n",
    "This wheel was the exact executable candidate after the SCD2 key-contract repair, but the packaged runtime-safety hardening now supersedes it. It is historical provenance only and must not be used for the next Fabric certification. A new exact post-hardening main wheel must be selected after merge. Candidate/evidence identity remains `framework_artifact_sha256 + integration_inputs_hash`; `integration_inputs_hash` is still not yet constructed.\n",
)
replace_once(
    state,
    "`0.4.0` is not frozen and not release-authorized. The exact current executable candidate after the SCD2 key-contract repair is selected and independently verified, but release certification remains blocked at the external live-Fabric binding/evidence boundary.\n",
    "`0.4.0` is not frozen and not release-authorized. Packaged runtime-safety changes supersede the previously selected executable candidate, so no exact current-source candidate is selected until the hardening reaches `main`, both post-merge gates pass, and the retained main wheel is independently verified.\n",
)
append_section(
    state,
    "## Runtime-safety hardening in progress",
    """
The current packaged-source change set hardens the following fail-closed boundaries before real Fabric certification:

```text
watermark overlap -> reread allowed, checkpoint regression forbidden
watermark commit  -> expected-version compare-and-set
watermark JSON    -> typed/versioned value encoding
SCD2 hashing      -> canonical type-preserving hash input
pipeline failure  -> terminal FAILED audit for ordinary Exception paths when Control Plane is writable
provider evidence -> recursive redaction and bounded retained payloads
unknown outcome   -> only explicit NOT_COMMITTED may retry
CDC SCD2 delete   -> closed source-position evidence prevents stale resurrection
quarantine replay -> typed payload v2 + content hash + create-if-absent publication
```

Local/SQLite/POSIX tests can prove framework semantics but do not prove Microsoft Fabric, SQL Server, or OneLake filesystem behavior. Real Fabric status remains `FABRIC_CERTIFICATION_REQUIRED`.
""",
)

consistency = "tests/test_current_docs_consistency.py"
replace_once(
    consistency,
    '        "exact_candidate_source_selected: true",\n',
    '        "exact_candidate_source_selected: false",\n',
)
replace_once(
    consistency,
    '        "current_source_candidate_git_sha: 81b574fb79bcc5e74cb9eee6d0644c6de8ef7ffd",\n',
    '        "current_source_candidate_git_sha: not_selected_after_runtime_safety_hardening",\n',
)
replace_once(
    consistency,
    '        "current_source_framework_artifact_sha256: 5ee9a032d242f3a164ccfbfcfe5b646d91e6f35dbf603f21735b745dda6cead6",\n',
    '        "current_source_framework_artifact_sha256: not_selected_after_runtime_safety_hardening",\n',
)
replace_once(
    consistency,
    '        "current_source_requires_new_exact_artifact_before_release_claim: false",\n',
    '        "current_source_requires_new_exact_artifact_before_release_claim: true",\n',
)
replace_once(
    consistency,
    '        "status: selected_not_frozen",\n',
    '        "status: superseded_by_runtime_safety_hardening",\n',
)
replace_once(
    consistency,
    '        "exact_current_candidate_selected: true",\n',
    '        "exact_current_candidate_selected: false",\n',
)
replace_once(
    consistency,
    '        "current_source_installed_wheel_acceptance: passed",\n',
    '        "current_source_installed_wheel_acceptance: not_run_for_new_current_source",\n',
)

append_section(
    "docs/DATA_PATTERNS.md",
    "## Runtime ordering invariants",
    """
For `WATERMARK` capture, an overlap/lookback window may reread older rows for idempotent apply, but it never moves the durable composite checkpoint backwards. The checkpoint compares the watermark value first and the configured tie-breaker values second. Incompatible scalar domains, naive datetimes, non-finite numerics, bool-as-int ambiguity, or tie-breaker arity changes fail closed. Durable advancement uses an expected-version compare-and-set rather than an application-level read followed by an unconditional write.

For CDC-to-SCD2, a DELETE closes the current history row and retains the source partition/position that performed the close. When no current row exists, that closed/tombstone position remains the ordering authority: stale or equal events cannot resurrect the entity; only a strictly newer source position may reinsert it. If retained history cannot prove ordering, a trusted lower checkpoint is required or apply refuses to continue.
""",
)
append_section(
    "docs/OPERATIONS.md",
    "## Runtime safety and retained evidence",
    """
Operational recovery must preserve the same fail-closed boundaries as normal execution:

- Watermark commits are monotonic and use expected-version CAS. A stale concurrent writer fails instead of overwriting a newer checkpoint.
- Ordinary pipeline/backend exceptions are terminalized as `FAILED` with `completed_at` whenever the Control Plane remains writable. If terminal audit persistence itself fails, both the original execution error and the finalization error are surfaced; a stored `RUNNING` row cannot be falsely claimed as finalized.
- Unknown target-commit outcomes are never retried blindly. Resolver failure or an invalid resolver value records `UNKNOWN_COMMIT_RESOLUTION_FAILED`; only explicit `NOT_COMMITTED` may enter the retry path.
- Provider error/failure payloads are recursively redacted and bounded before entering audit models or repositories. Secrets such as passwords, bearer tokens, authorization values, connection strings, and nested token/secret fields must not be retained.
- Detailed quarantine replay payloads use typed schema v2, validate exact dataset/quarantine identity and a content SHA256, and publish with create-if-absent semantics. Unsupported business value types fail closed instead of being stringified.

The filesystem atomicity tests are local/POSIX evidence only. OneLake/Lakehouse mount create-if-absent semantics remain part of real Fabric certification and must not be inferred from local tests.
""",
)
append_section(
    "docs/TESTING_AND_CERTIFICATION.md",
    "## Source quality gates added before Fabric certification",
    """
Repository CI now keeps the historical isolated Ruff baseline (`E4,E7,E9,F`) and also reads the committed Ruff configuration, runs focused MyPy checks across runtime contracts/repository/recovery state transitions, and enforces an initial whole-package pytest coverage floor without excluding core framework modules. Installed-wheel acceptance remains a separate gate.

These source/SQLite/fault-injection checks prove framework behavior such as watermark CAS, typed value round trips, secret redaction, terminal audit handling, CDC tombstone ordering, and quarantine immutability. They do **not** upgrade the candidate to real Fabric proof. SQL Server concurrency semantics, Fabric REST behavior, and OneLake filesystem atomicity still require the exact selected wheel and retained live evidence.
""",
)
append_section(
    "docs/DEVELOPMENT_GUIDE.md",
    "## Runtime-safety regression rule",
    """
Changes to checkpoints, persisted state, hashing, audit evidence, retry/recovery, CDC ordering, or replay storage require failure-path regression tests, not only happy-path tests. Prefer a shared typed codec/redaction primitive over per-feature `default=str` or ad-hoc sanitization. Persisted state updates that can race must use an atomic provider-side predicate/CAS; an application-level read followed by an unconditional write is not sufficient proof.

The CI baseline includes configured Ruff, focused MyPy and package-wide coverage in addition to the existing source and installed-wheel gates. A packaged runtime change always invalidates the previously selected exact candidate even when all source tests pass.
""",
)
append_section(
    "docs/internal/CAPABILITIES.md",
    "## Runtime safety hardening",
    """
Current source hardens monotonic watermark CAS, typed persisted watermark values, type-preserving SCD2 hashes, terminal pipeline/recovery failure boundaries, bounded credential redaction, CDC SCD2 tombstone ordering, and typed immutable quarantine replay payloads. These are source/runtime capabilities only until the post-hardening exact wheel is selected and real Fabric evidence is retained.
""",
)
append_section(
    "docs/internal/IMPLEMENTATION_MAP.md",
    "## Runtime safety implementation map",
    """
```text
src/fabric_data_framework/contracts/typed_values.py
  canonical typed codec / deterministic canonical bytes

src/fabric_data_framework/contracts/runtime.py
src/fabric_data_framework/capture/watermark.py
src/fabric_data_framework/control_plane/repository.py
src/fabric_data_framework/control_plane/sqlalchemy_repository.py
src/fabric_data_framework/execution/watermark_scd2.py
  composite watermark comparison, monotonic transition, expected-version CAS, typed persistence

src/fabric_data_framework/apply/record_hash.py
src/fabric_data_framework/apply/scd2.py
src/fabric_data_framework/apply/cdc_scd2.py
  typed change hashing and CDC tombstone/history ordering

src/fabric_data_framework/evidence/safety.py
src/fabric_data_framework/execution/backends/fabric_pipeline.py
src/fabric_data_framework/orchestration/dispatcher.py
  bounded recursive audit redaction and terminal ordinary-exception boundaries

src/fabric_data_framework/recovery/runtime.py
  unknown-commit resolver terminalization; only explicit NOT_COMMITTED permits retry

src/fabric_data_framework/quality/quarantine_store.py
  typed payload schema v2, identity/content-hash validation, create-if-absent publish
```
""",
)
