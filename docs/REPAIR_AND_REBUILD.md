# Data repair, rebuild and version cutover

This is the canonical runbook for **data correctness problems and logic changes** in a framework-consuming project. It answers the operator question: **what is wrong, what is contaminated, what should be rebuilt, and how do we move safely to the corrected version?**

For transient runtime failures, retry exhaustion and unknown commit handling, see [`OPERATIONS.md`](OPERATIONS.md). For source/capture semantics, see [`DATA_PATTERNS.md`](DATA_PATTERNS.md).

## 1. First classify where trust failed

Do not start by deleting tables. Find the first layer whose facts or logic are no longer trustworthy.

| First bad point | `RepairIssueOrigin` | Root rebuild scope | Typical example |
|---|---|---|---|
| Gold/Silver target logic | `TARGET_LOGIC` | `TARGET_ONLY` | SCD2 rule, mapping, calculation or new business requirement changed |
| Bronze/captured data | `CAPTURE_DATA` | `CAPTURE_AND_TARGET` | bad filter, bad dedupe, missed source rows, wrong capture window while progress model stays the same |
| Capture semantics/progress model | `CAPTURE_SEMANTICS` | `AUTHORITATIVE_RESET` | watermark should become CDC, CDC state is untrustworthy, progress ownership changes |

The key rule is:

```text
first untrustworthy node
        |
        v
all downstream descendants are potentially contaminated
```

Unrelated branches are not rebuilt.

## 2. The minimum repair decision table

| Problem | Correct repair |
|---|---|
| Provider/network transient; no ambiguous commit | bounded `RETRY` |
| Small known source interval missing | `BACKFILL` exact range |
| Retained quarantine payload should be reprocessed | `REPLAY` |
| Gold calculation wrong; its inputs are correct | `FULL_REBUILD + TARGET_ONLY` at Gold |
| Silver logic wrong/new requirement; Bronze is correct | `FULL_REBUILD + TARGET_ONLY` at Silver, then rebuild affected downstream Gold |
| Bronze facts are wrong; capture model still valid | `FULL_REBUILD + CAPTURE_AND_TARGET` at the bad Bronze root, then rebuild affected descendants |
| Capture/checkpoint semantics themselves are wrong | `FULL_REBUILD + AUTHORITATIVE_RESET` at the root, then rebuild affected descendants |
| Dataset is no longer needed | disable/pause; permanent purge stays manual |
| Unknown target commit | reconcile first; never blind retry |

## 3. Use the dependency-aware impact planner

The implementation repository already owns DatasetConfig dependencies. The framework now uses that graph to calculate the exact contaminated subgraph.

```python
from fabric_data_framework.contracts.rebuild_impact import RepairIssueOrigin
from fabric_data_framework.recovery.rebuild_impact import build_rebuild_impact_plan

plan = build_rebuild_impact_plan(
    deployed_configs,
    root_dataset_ids=("silver.customer",),
    issue_origin=RepairIssueOrigin.TARGET_LOGIC,
)
```

Example topology:

```text
bronze.customer
      |
      v
silver.customer
      |\
      | +----> gold.customer_metrics
      v
gold.customer

bronze.product
      |
      v
silver.product
```

If `silver.customer` logic is wrong, the plan is:

```text
wave 1: silver.customer
wave 2: gold.customer, gold.customer_metrics
```

It does **not** include `bronze.customer`, `bronze.product` or `silver.product`.

If `bronze.customer` captured data is wrong, the plan becomes:

```text
wave 1: bronze.customer                CAPTURE_AND_TARGET
wave 2: silver.customer                TARGET_ONLY
wave 3: gold.customer                  TARGET_ONLY
        gold.customer_metrics          TARGET_ONLY
```

The root gets the scope required by the first trust failure. Downstream descendants default to `TARGET_ONLY`: rebuild their target from corrected authoritative upstream facts without moving their own capture state. A project may explicitly widen a descendant scope if its retained capture cannot support that rebuild.

The planner fails closed on:

```text
unknown dependencies
cycles
duplicate dataset IDs
scope overrides outside the affected subgraph
root scope narrower than the issue requires
```

Disabled but contaminated datasets remain visible in `disabled_affected_dataset_ids`; disabling scheduling does not make historical bad data trustworthy.

## 4. Prefer v2 beside v1 for material logic changes

For important Silver/Gold logic changes, do not destroy the current production version first.

Recommended pattern:

```text
trusted upstream
      |
      +---- old logic ----> customer_v1  <--- currently active
      |
      +---- new logic ----> customer_v2  <--- candidate
                               |
                               v
                       DQ + reconciliation
                               |
                               v
                       UAT / consumer validation
                               |
                               v
                           approval
                               |
                               v
                         logical cutover
```

The framework models one physical candidate with `TargetVersionSpec`:

```python
from fabric_data_framework.contracts.target_version import TargetVersionSpec

candidate = TargetVersionSpec(
    dataset_id="silver.customer",
    layer="silver",
    logical_object="customer",
    physical_object="customer_v2",
    version="v2",
)
```

The implementation repository owns the actual physical naming and provider-specific binding implementation.

## 5. Keep consumers on a stable logical object

Prefer this:

```text
consumer -> silver.customer
                    |
                    +--> customer_v1   before cutover
                    +--> customer_v2   after cutover
```

instead of forcing every consumer to change from `customer_v1` to `customer_v2`.

The stable logical binding may be implemented by an environment-specific view, alias, semantic binding or other project adapter. The framework owns the **cutover safety contract**, not one universal provider-specific alias mechanism.

## 6. Cutover is fail-closed

A production logical binding may move only after all of these are true:

```text
candidate physical target built
AND reconciliation passed
AND consumer/UAT validation passed
AND approval reference matches the cutover request
```

Example:

```python
from fabric_data_framework.contracts.target_version import (
    TargetCutoverGate,
    TargetCutoverRequest,
)
from fabric_data_framework.recovery.target_cutover import execute_target_cutover

request = TargetCutoverRequest(
    dataset_id="silver.customer",
    environment="PROD",
    logical_object="customer",
    from_version="v1",
    to_version="v2",
    requested_by="data-ops",
    reason="UAT approved corrected SCD2 logic",
    approval_reference="CAB-2026-0908-001",
)

gate = TargetCutoverGate(
    candidate_built=True,
    reconciliation_passed=True,
    consumer_validation_passed=True,
    validation_reference="uat://customer/v2/pass",
    approval_reference="CAB-2026-0908-001",
)

result = execute_target_cutover(
    request=request,
    candidate=candidate,
    gate=gate,
    adapter=project_cutover_adapter,
)
```

The cutover uses optimistic generation/state checks and a stable `cutover_request_id`. Repeating the same successful request is idempotent. A stale request that still expects v1 after another promotion fails closed.

## 7. The old v1 is deliberately not deleted

Promotion changes the logical consumer binding only.

```text
before:
logical customer -> customer_v1

cutover:
logical customer -> customer_v2

retained:
customer_v1 still exists
```

This gives an explicit rollback window and preserves evidence while the new version settles.

After the retention/rollback window, a human may remove v1 under the project's normal governance process. The framework does not automate permanent business-data purge.

## 8. UAT-to-PROD flow for a Silver logic change

Example: Bronze is correct, but customer SCD2 logic is wrong or the business asks for new semantics.

```text
1. fix mapping/logic in Git
2. impact plan root = silver.customer, origin = TARGET_LOGIC
3. build silver.customer_v2 from trusted Bronze
4. build affected Gold v2 candidates where their values/contract depend on corrected Silver
5. run DQ + reconciliation
6. expose v2 chain in UAT
7. obtain consumer/business approval reference
8. deploy the same approved project change to PROD
9. build PROD v2 candidates
10. prove PROD reconciliation
11. cut stable logical bindings to v2 in dependency order
12. monitor
13. keep v1 for rollback window
14. manually delete v1 later if desired
```

Do not promote a different unvalidated transformation simply because UAT used the same version label.

## 9. Does Gold also need v2 when Silver changes?

Not because Gold is Delta. Storage format does not decide version propagation.

The decision is semantic dependency:

```text
Silver change affects a value/column/history contract used by Gold
    -> Gold output is contaminated/stale
    -> rebuild Gold

Silver change has no effect on Gold inputs/semantics
    -> Gold does not require rebuild
```

For high-value production chains, if Gold must be rebuilt because of the Silver change, prefer `gold_x_v2` beside `gold_x_v1` so UAT and cutover can validate the full consumer path.

Example:

```text
bronze.customer
      |
      +--> silver.customer_v1 --> gold.dim_customer_v1 --> report v1
      |
      +--> silver.customer_v2 --> gold.dim_customer_v2 --> UAT report
```

After approval, cut the stable Silver/Gold consumer bindings to v2. Delete v1 manually later.

## 10. If Bronze is wrong, rebuild the contaminated downstream chain

A bad Bronze does not mean every table in the platform must be rebuilt. It means every descendant that consumed those wrong facts is potentially wrong.

Example:

```text
bronze.customer  BAD
      |
      +--> silver.customer
      |       +--> gold.dim_customer
      |       +--> gold.customer_segment
      |
      +--> silver.customer_address
              +--> gold.region_customer

bronze.product   GOOD
      |
      +--> silver.product
              +--> gold.product_sales
```

Repair `bronze.customer` and its customer descendants. Do not touch the independent product branch.

If the bad Bronze came from a bad filter/dedup/window while WATERMARK remains WATERMARK, use root `CAPTURE_AND_TARGET`.

If the capture contract itself changes, for example WATERMARK becomes CDC, use root `AUTHORITATIVE_RESET`.

## 11. Rebuild scopes and checkpoint behavior

| Scope | Typical root | Data rebuilt | Runtime checkpoint rule |
|---|---|---|---|
| `TARGET_ONLY` | Silver/Gold logic | target only | capture/runtime state must remain exactly unchanged |
| `CAPTURE_AND_TARGET` | Bronze/captured facts | capture/Bronze + target | checkpoint/boundary may change; progress kind may not |
| `AUTHORITATIVE_RESET` | capture semantics | required data layers + runtime state | explicit new state required; progress kind may change |

The framework never clears a checkpoint first and then hopes the rebuild succeeds.

```text
preserve old state
-> build candidate/rebuild data
-> prove target commit
-> reconciliation PASS
-> only then install new runtime state if the scope permits it
```

For current projections, authoritative SCD2 history remains the rebuild source. A
`DELTA_PROJECTION` with no checkpoint must bootstrap by rebuilding from a complete
history snapshot at one frozen Delta version. Retention-gap recovery may rebuild at a
newer frozen version and advance the same semantic checkpoint, but it may not rewind
progress. A source/key/projected-schema change or a transition into/out of Mode 3 needs
an audited physical-object and checkpoint-reset coordinator. That coordinator is not
implemented in the current package, so metadata deployment blocks the transition while
state exists instead of deleting state optimistically.

## 12. Rollback after a v2 cutover

Because v1 is retained, rollback is another explicit cutover, not a destructive restore.

```text
logical customer -> v2
        |
        | issue discovered
        v
validate retained v1 is still safe
        |
        v
approved cutover request v2 -> v1
```

Use a new approval/cutover request. Do not silently mutate the active binding behind the framework's generation checks.

## 13. When not to create v2

A new physical version is not mandatory for every tiny fix.

Use in-place repair when all of these are true:

```text
bounded blast radius
well-proven idempotent correction
no consumer contract/history change
rollback is not materially improved by parallel versions
```

Prefer v2/blue-green when any of these are true:

```text
business logic/history semantics changed
large/full rebuild required
multiple downstream consumers are affected
UAT/business signoff is required
rollback safety matters
```

## 14. Pause and retirement are not repair

If upstream sends 40 tables and only 10 are useful:

```text
temporary pause
-> RuntimeOverride enabled=false

source-controlled stop
-> DatasetConfig enabled=false
```

Do not invent a rebuild just to stop ingestion. Permanent hard deletion of Bronze/Silver/Gold remains manual.

## 15. Practical incident checklist

```text
1. identify the first untrustworthy dataset/layer
2. classify TARGET_LOGIC / CAPTURE_DATA / CAPTURE_SEMANTICS
3. build RebuildImpactPlan
4. review affected descendants and disabled contaminated datasets
5. choose the smallest safe scope; widen only where retained facts are insufficient
6. decide in-place repair vs versioned v2
7. build corrected candidates in dependency order
8. run DQ + reconciliation
9. validate downstream consumer behavior/UAT
10. retain an approval reference
11. cut logical bindings in dependency order
12. verify production outputs and checkpoints
13. keep v1 for rollback
14. manually clean old versions later if approved
```

## 16. Code ownership

```text
contracts/rebuild.py
  FULL_REBUILD scope/state contract

contracts/rebuild_impact.py
  issue-origin + immutable impact-plan contract

recovery/rebuild.py
  per-dataset FULL_REBUILD coordinator

recovery/rebuild_impact.py
  dependency-aware contaminated-subgraph planner

contracts/target_version.py
  versioned physical target + cutover request/gate/result

recovery/target_cutover.py
  fail-closed logical consumer cutover coordinator

implementation/domain repo
  physical v1/v2 table names
  real mapping/business logic
  UAT evidence
  provider-specific logical-binding adapter
  manual old-version deletion
```

The framework coordinates safety and impact. The implementation project owns the actual business transformation and environment-specific physical mutation.
