from pathlib import Path
import re


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Current projection canonical guide: physical Mode-3 runtime and governed recovery now exist.
replace_once(
    "docs/CURRENT_PROJECTIONS.md",
    '''The executor rejects missing completeness attestations, history rows outside the\naffected-key scope, and CDF records newer than the frozen upper bound. The target read\nboundary is affected-key scoped; a physical adapter must perform that lookup and the\ndistinct-key calculation in Spark/Delta rather than collect a large key set or history\ntable into the framework process.\n''',
    '''The provider-neutral executor rejects missing completeness attestations, history rows\noutside the affected-key scope, and CDF records newer than the frozen upper bound. The\nproduction Fabric Spark adapter performs the distinct-key calculation, exact-version\nhistory reread and target MERGE in Spark/Delta; it does not collect a large key set or\nhistory table into the framework process.\n\n`adapters/fabric/current_projection.py` owns the Spark/Delta physical work and\n`execution/backends/fabric_spark.py` is the child-runtime dispatch boundary. CDF rows are\nused only to derive distinct business keys. Authoritative values are always reread from\nhistory `VERSION AS OF M` before target mutation.\n''',
    "mode3 physical owner",
)
replace_once(
    "docs/CURRENT_PROJECTIONS.md",
    '''The reference executor acquires the existing durable, environment-local `dataset_lease`\nbefore reading progress or mutating the projection. This prevents two cooperative\nwriters from interleaving target mutation and checkpoint commit. A lease review deadline\nis **not** an automatic takeover time: if an executor disappears, the claim remains until\nan operator proves the old writer cannot resume and performs governed recovery. There is\ncurrently no packaged automatic abandoned-lease recovery operation.\n''',
    '''The executor acquires the durable, environment-local `dataset_lease` before reading\nprogress or mutating the projection. This prevents two cooperative writers from\ninterleaving target mutation and checkpoint commit. A lease review deadline is **not** an\nautomatic takeover time. If an executor disappears, the claim remains until an operator\nproves the old writer cannot resume. `control_plane/dataset_lease_recovery.py` then\nperforms an exact-identity, post-deadline recovery transaction that appends immutable\nactor/reason/proof evidence and removes only that abandoned lease.\n''',
    "lease recovery docs",
)
replace_once(
    "docs/CURRENT_PROJECTIONS.md",
    '''Changing the configured value is not by itself a safe physical migration. Entering or\nleaving `DELTA_PROJECTION` while a runtime checkpoint exists is blocked. Rebinding an\nexisting Mode-3 checkpoint to changed key/schema/source semantics is also blocked. The\nrepository does not yet package an audited checkpoint-reset and physical object\ntransition coordinator, so such transitions remain an explicit implementation/release\ngap rather than an automatic destructive deployment action.\n''',
    '''Changing the configured value is not by itself a safe physical migration. Normal\nmetadata materialization still blocks entering or leaving `DELTA_PROJECTION` while a\nruntime checkpoint exists, and rebinding an existing Mode-3 checkpoint to changed\nkey/schema/source semantics fails closed. Physical changes use\n`recovery/current_projection.py`: the coordinator records STARTED/FAILED/COMPLETED\nevidence, rebuilds the desired object from authoritative history and resets only an exact\ncheckpoint version when leaving Mode 3. A config edit therefore cannot silently perform\na destructive state transition.\n''',
    "mode transition docs",
)
replace_once(
    "docs/CURRENT_PROJECTIONS.md",
    '''The current repository contains provider-neutral apply/execution contracts and an\nin-memory reference target. It does **not** yet contain a production Spark/Delta\n`CurrentProjectionTarget`, distributed affected-key/CDF reader, or backend dispatch\nwiring that invokes the Mode-3 executor. Therefore Mode 3 is not an end-to-end deployable\nFabric capability in the current source, even if its local contract tests pass.\n''',
    '''The current repository contains both the provider-neutral reference executor and a\nFabric Spark/Delta physical runtime for Mode 3. Local/CI tests cover CDF window selection,\nexact-version reread, affected-key MERGE/delete semantics, checkpoint gating, durable\nlease recovery and governed mode transitions. This makes Mode 3 an end-to-end packaged\ncapability, but **not FABRIC PROVEN**: OneLake/Delta CDF retention, `VERSION AS OF`, Spark\nMERGE behavior, Fabric SQL Database concurrency and physical mode-transition syntax still\nrequire retained execution evidence from the exact selected wheel in an approved Fabric\nenvironment.\n''',
    "certification boundary docs",
)

# Operations: replace unsupported-manual gap with the governed recovery operation.
replace_once(
    "docs/OPERATIONS.md",
    '''For a `DELTA_PROJECTION` dataset, inspect `dataset_lease` before retrying. The claim is\ndurable mutual exclusion around target mutation plus checkpoint commit; `expires_at` is\nonly a review deadline and never authorizes automatic takeover. If the claim remains\nafter a process failure, stop and prove the old executor and any provider-side work\ncannot resume. The current package has no audited abandoned-lease removal command, so\nmanual row deletion is not presented as a supported recovery procedure.\n''',
    '''For a `DELTA_PROJECTION` dataset, inspect `dataset_lease` before retrying. The claim is\ndurable mutual exclusion around target mutation plus checkpoint commit; `expires_at` is\nonly a review deadline and never authorizes automatic takeover. If the claim remains\nafter a process failure, stop and prove the old executor and any provider-side work\ncannot resume. Use the governed `recover_abandoned_dataset_lease(...)` operation only\nafter the review deadline, passing the exact lease owner/run/version plus operator, reason\nand durable proof reference. Recovery appends immutable `dataset_lease_recovery_event`\nevidence and removes only the exact abandoned claim in the same Control Plane\ntransaction. Never delete the row manually or treat timeout alone as proof of abandonment.\n\nCurrent-projection physical mode changes are similarly explicit. Use\n`FabricSparkProjectionTransitionCoordinator` rather than changing the source-controlled\nmode and manually deleting checkpoints. The coordinator preserves the stable consumer\nname, rebuilds from authoritative history, records transition evidence and performs an\nexact checkpoint reset only when required.\n''',
    "operations lease recovery",
)

# Capability evidence must distinguish packaged implementation from live Fabric proof.
replace_once(
    "docs/internal/CAPABILITIES.md",
    '''| DELTA_PROJECTION affected-key semantics, bootstrap/rebuild, checkpoint and lease gates | `apply/current_projection.py` + `execution/current_projection.py` | IMPLEMENTED reference contract + source tests; no production Spark/Delta adapter or backend dispatch wiring; not end-to-end deployable/FABRIC PROVEN |''',
    '''| DELTA_PROJECTION affected-key semantics, bootstrap/rebuild, checkpoint and lease gates | `apply/current_projection.py` + `execution/current_projection.py` + `adapters/fabric/current_projection.py` + `execution/backends/fabric_spark.py` | IMPLEMENTED packaged Spark/Delta path + source tests; live OneLake/CDF/time-travel/MERGE evidence still required before FABRIC PROVEN |''',
    "capability mode3 row",
)
replace_once(
    "docs/internal/CAPABILITIES.md",
    '''The superseded exact wheel passed post-merge source CI and installed-wheel acceptance.\nCurrent packaged hardening requires a new exact post-merge candidate before installed\nwheel evidence can be attributed to current source. Neither result proves real Fabric\nSQL/Spark observation collection or upgrades the capability to FABRIC PROVEN.\n''',
    '''The previously selected second-review wheel is superseded by the packaged projection\nproduction runtime/schema-v8 change. Current source therefore requires a new exact\npost-merge wheel and installed-wheel acceptance before candidate evidence can be\nattributed to it. Source/installed-wheel success will still not prove real Fabric\nSQL/Spark behavior or upgrade any capability to FABRIC PROVEN.\n''',
    "capability candidate paragraph",
)

# Implementation ownership map.
replace_once(
    "docs/internal/IMPLEMENTATION_MAP.md",
    '''| Mode-3 reference execution, bootstrap/rebuild and checkpoint gating | `execution/current_projection.py` |\n| Mode-3 health from existing runtime state | `control_plane/current_projection.py` |\n| Durable dataset mutation claim | `control_plane/dataset_lease.py` |''',
    '''| Mode-3 provider-neutral reference execution, bootstrap/rebuild and checkpoint gating | `execution/current_projection.py` |\n| Mode-3 Fabric Spark/Delta CDF, exact-version reread and affected-key MERGE | `adapters/fabric/current_projection.py` |\n| Fabric Spark current-projection child dispatch | `execution/backends/fabric_spark.py` |\n| Mode-3 health from existing runtime state | `control_plane/current_projection.py` |\n| Durable dataset mutation claim | `control_plane/dataset_lease.py` |\n| Governed abandoned-lease recovery evidence | `control_plane/dataset_lease_recovery.py` |\n| Governed current-projection mode transition/checkpoint reset | `control_plane/current_projection_transition.py` + `recovery/current_projection.py` |''',
    "implementation map rows",
)
replace_once(
    "docs/internal/IMPLEMENTATION_MAP.md",
    '''The Mode-3 executor currently has only an in-memory reference target. No production\nSpark/Delta target adapter, distributed CDF/affected-key reader, or backend invocation\npath exists. Treat that as a missing physical owner, not as work implicitly owned by the\nprovider-neutral apply module.\n''',
    '''Mode 3 deliberately keeps two owners: `execution/current_projection.py` is the\nprovider-neutral semantic/reference path, while `adapters/fabric/current_projection.py`\nowns distributed Delta CDF, exact-version history reads and affected-key target mutation.\nThe Fabric child executor in `execution/backends/fabric_spark.py` binds immutable dispatch\nrequests to that physical runtime. Recovery and mode transition mechanics remain outside\nthe apply module so provider mechanics cannot redefine projection truth.\n''',
    "implementation mode3 paragraph",
)

# State: any packaged source change supersedes the selected executable bytes before merge.
state_path = Path("docs/internal/STATE.md")
state = state_path.read_text(encoding="utf-8")
for old, new, label in (
    ("  exact_candidate_source_selected: true", "  exact_candidate_source_selected: false", "state selected flag"),
    ("  current_source_candidate_git_sha: 661c4fc82a071ed340c352561946e08d18031f01", "  current_source_candidate_git_sha: not_selected_after_projection_production_runtime", "state source sha"),
    ("  current_source_framework_artifact_sha256: d5b98aad88885e244061f0eb6e0c8d8b3c6a6a126bc1b3186d16dfd93ce02dec", "  current_source_framework_artifact_sha256: not_selected_after_projection_production_runtime", "state wheel sha"),
    ("  current_source_requires_new_exact_artifact_before_release_claim: false", "  current_source_requires_new_exact_artifact_before_release_claim: true", "state artifact flag"),
    ("  candidate_bytes_must_not_change: true", "  candidate_bytes_must_not_change: false", "state byte flag"),
    ("  control_plane_schema_version: 7", "  control_plane_schema_version: 8", "state schema version"),
    ("  exact_current_candidate_selected: true", "  exact_current_candidate_selected: false", "fabric selected flag"),
    ("  current_source_installed_wheel_acceptance: passed_main_run_34682679582", "  current_source_installed_wheel_acceptance: not_run_for_new_current_source", "installed wheel flag"),
):
    if state.count(old) != 1:
        raise SystemExit(f"{label}: expected one match, found {state.count(old)}")
    state = state.replace(old, new, 1)

selected_re = re.compile(r"  selected_candidate:\n.*?(?=  superseded_current_projection_candidate:)", re.S)
new_selected = '''  selected_candidate:\n    status: not_selected_after_projection_production_runtime\n  superseded_second_review_candidate:\n    candidate_git_sha: 661c4fc82a071ed340c352561946e08d18031f01\n    candidate_main_framework_ci_run: 34682679599\n    candidate_main_installed_wheel_run: 34682679582\n    candidate_wheel_artifact_id: 10294725569\n    candidate_wheel_artifact_name: framework-wheel-661c4fc82a071ed340c352561946e08d18031f01\n    candidate_wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl\n    framework_artifact_sha256: d5b98aad88885e244061f0eb6e0c8d8b3c6a6a126bc1b3186d16dfd93ce02dec\n    wheel_sha_verified_against_candidate_json: true\n    wheel_sha_verified_against_sha256sums: true\n    wheel_sha_independently_rehashed: true\n    status: superseded_by_projection_production_runtime\n'''
state, count = selected_re.subn(new_selected, state, count=1)
if count != 1:
    raise SystemExit("state selected candidate block mismatch")

old_next = '''next_boundary:\n  - keep the exact selected candidate bytes immutable while Fabric certification is pending\n  - obtain and live-verify the approved isolated DEV Fabric workspace/lakehouse identity and runtime credentials\n  - implement and review the missing production Mode-3 Spark/Delta target, distributed CDF reader, backend dispatch, transition/reset coordinator, and abandoned-lease recovery before claiming end-to-end readiness\n  - bootstrap/read back framework-owned certification assets using the exact selected wheel\n'''
new_next = '''next_boundary:\n  - merge the projection production runtime only after exact PR-head framework and installed-wheel gates pass\n  - verify post-merge main framework and installed-wheel gates\n  - download and independently verify the exact post-merge main wheel bytes\n  - select the new exact executable candidate before any live Fabric certification\n  - obtain and live-verify the approved isolated DEV Fabric workspace/lakehouse identity and runtime credentials\n  - bootstrap/read back framework-owned certification assets using the newly selected exact wheel\n'''
if state.count(old_next) != 1:
    raise SystemExit("state next boundary mismatch")
state = state.replace(old_next, new_next, 1)
state = state.replace("## Selected second-independent-review candidate", "## Superseded second-independent-review candidate", 1)
state = state.replace(
    '''This exact executable candidate is **selected but not frozen**. It has not constructed\n`integration_inputs_hash`, executed Microsoft Fabric, authorized release, or claimed\nFabric PASS. Mode 3 is also not end-to-end deployable until its documented production\nphysical adapters and recovery/transition integration exist. Candidate/evidence identity\nremains `framework_artifact_sha256 + integration_inputs_hash`; the selected wheel bytes\nmust not change before identity-bound Fabric certification.\n''',
    '''This exact executable candidate is now **superseded** by the projection production\nruntime, schema-v8 and governed recovery/transition changes. It must not be used for the\nnext Fabric certification. No `integration_inputs_hash`, Fabric PASS, release authorization\nor release claim was produced from this historical candidate.\n''',
    1,
)
state_path.write_text(state, encoding="utf-8")

# Consistency tests follow the fail-closed current state rather than historical candidate status.
test_path = Path("tests/test_current_docs_consistency.py")
test = test_path.read_text(encoding="utf-8")
replacements = {
    '"exact_candidate_source_selected: true"': '"exact_candidate_source_selected: false"',
    '"current_source_candidate_git_sha: 661c4fc82a071ed340c352561946e08d18031f01"': '"current_source_candidate_git_sha: not_selected_after_projection_production_runtime"',
    '"current_source_framework_artifact_sha256: d5b98aad88885e244061f0eb6e0c8d8b3c6a6a126bc1b3186d16dfd93ce02dec"': '"current_source_framework_artifact_sha256: not_selected_after_projection_production_runtime"',
    '"current_source_requires_new_exact_artifact_before_release_claim: false"': '"current_source_requires_new_exact_artifact_before_release_claim: true"',
    '"status: selected_not_frozen"': '"status: not_selected_after_projection_production_runtime"',
    '"superseded_current_projection_candidate:"': '"superseded_second_review_candidate:"',
    '"exact_current_candidate_selected: true"': '"exact_current_candidate_selected: false"',
    '"current_source_installed_wheel_acceptance: passed_main_run_34682679582"': '"current_source_installed_wheel_acceptance: not_run_for_new_current_source"',
    '"control_plane_schema_version: 7"': '"control_plane_schema_version: 8"',
}
for old, new in replacements.items():
    if test.count(old) != 1:
        raise SystemExit(f"test token {old}: expected one match, found {test.count(old)}")
    test = test.replace(old, new, 1)
anchor = '        "candidate_wheel_artifact_name: framework-wheel-661c4fc82a071ed340c352561946e08d18031f01",\n'
if anchor not in test:
    raise SystemExit("historical second review candidate anchor missing")
if '        "status: superseded_by_projection_production_runtime",\n' not in test:
    test = test.replace(
        '        "framework_artifact_sha256: d5b98aad88885e244061f0eb6e0c8d8b3c6a6a126bc1b3186d16dfd93ce02dec",\n',
        '        "framework_artifact_sha256: d5b98aad88885e244061f0eb6e0c8d8b3c6a6a126bc1b3186d16dfd93ce02dec",\n        "status: superseded_by_projection_production_runtime",\n',
        1,
    )
old_doc_test = '''def test_current_projection_docs_do_not_overclaim_physical_runtime():\n    current = _read("CURRENT_PROJECTIONS.md")\n    capabilities = _read("internal/CAPABILITIES.md")\n    implementation_map = _read("internal/IMPLEMENTATION_MAP.md")\n    operations = _read("OPERATIONS.md")\n    repair = _read("REPAIR_AND_REBUILD.md")\n\n    for token in (\n        "Bootstrap rule",\n        "CDF evidence is complete through frozen upper version M",\n        "dataset_lease",\n        "production Spark/Delta",\n        "not an end-to-end deployable",\n    ):\n        assert token in current\n    assert "NOT IMPLEMENTED in current source" in capabilities\n    assert "No production" in implementation_map\n    assert "never authorizes automatic takeover" in operations\n    assert "may not rewind" in repair\n'''
new_doc_test = '''def test_current_projection_docs_separate_packaged_runtime_from_live_fabric_proof():\n    current = _read("CURRENT_PROJECTIONS.md")\n    capabilities = _read("internal/CAPABILITIES.md")\n    implementation_map = _read("internal/IMPLEMENTATION_MAP.md")\n    operations = _read("OPERATIONS.md")\n    repair = _read("REPAIR_AND_REBUILD.md")\n\n    for token in (\n        "Bootstrap rule",\n        "CDF evidence is complete through frozen upper version M",\n        "dataset_lease",\n        "production Fabric Spark adapter",\n        "not FABRIC PROVEN",\n    ):\n        assert token in current\n    assert "IMPLEMENTED packaged Spark/Delta path" in capabilities\n    assert "adapters/fabric/current_projection.py" in implementation_map\n    assert "recover_abandoned_dataset_lease" in operations\n    assert "never authorizes automatic takeover" in operations\n    assert "may not rewind" in repair\n'''
if test.count(old_doc_test) != 1:
    raise SystemExit("current projection docs consistency test mismatch")
test = test.replace(old_doc_test, new_doc_test, 1)
test_path.write_text(test, encoding="utf-8")
