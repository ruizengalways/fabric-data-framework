# Provider-Native Downstream Recovery

Status: canonical provider recovery contract for unreleased `0.4.0`

## Purpose

The framework owns semantic progress. Provider runtimes own transport/native execution details.

This distinction matters after partial failure:

```text
source/provider read
    -> Bronze / normalized CDC
    -> target mutation
    -> reconciliation
    -> framework watermark/checkpoint commit
    -> optional provider transport cursor commit
```

A provider cursor, notebook run ID, Kafka consumer-group offset or submitted Warehouse statement is useful evidence, but it must not silently replace the framework's downstream-applied state.

This runbook defines the portable contracts required before real Fabric/Kafka/Delta transports can be certified.

---

## 1. Kafka / Debezium cursor coordination

### Two different meanings

For Debezium consumed from Kafka, keep these concepts separate:

| State | Meaning | Authority |
|---|---|---|
| framework `CDCCheckpoint` | last Kafka record offset durably applied downstream | semantic source of truth |
| Kafka consumer-group committed offset | next record Kafka will deliver to that group | transport cursor only |

Example:

```text
framework checkpoint says partition 0 offset 100 is applied
therefore next required record is 101

Kafka group offset = 110
```

The Kafka group is **ahead** of downstream truth. This can happen when source consumption progressed but target apply/checkpoint commit failed. Starting at 110 would lose offsets 101..109.

The framework therefore rewinds the provider cursor to 101.

The reverse is also possible:

```text
framework next required = 101
Kafka group offset = 95
```

The group is **behind**. The framework seeks directly to 101 instead of replaying already-applied source records merely because the external group cursor is stale.

### Planning API

```python
from fabric_data_framework.adapters.cdc import (
    plan_debezium_kafka_cursor_coordination,
)

plan = plan_debezium_kafka_cursor_coordination(
    topic="dbserver1.inventory.customers",
    committed_checkpoint=framework_checkpoint,
    earliest_offsets={0: 90, 1: 40},
    latest_offsets={0: 120, 1: 70},
    consumer_group_next_offsets={0: 110, 1: 45},
)
```

The result contains:

```text
plan.resume.partitions
    bounded inclusive Kafka record ranges to read

plan.seek_offsets
    provider seeks required before reading

plan.commit_next_offsets_after_downstream_success
    Kafka next-offset cursors that may be committed only after downstream success
```

### Correct execution order

```text
1. Read framework CDC checkpoint.
2. Read provider earliest/latest offsets.
3. Read current consumer-group next offsets.
4. plan_debezium_kafka_cursor_coordination(...).
5. Seek every partition in plan.seek_offsets.
6. Consume only through plan.resume upper offsets.
7. Normalize Debezium records to canonical CDC.
8. Apply target mutation using target-operation idempotency.
9. Reconcile/data-quality checks.
10. Commit framework CDC checkpoint.
11. Only now commit Kafka group offsets from
    plan.commit_next_offsets_after_downstream_success.
```

Step 11 is transport optimization/operability. If it fails, downstream truth is still the framework checkpoint and the next run will realign the group again.

### Kafka retention gap

If the framework says offset `100` is applied, the next required offset is `101`.

If Kafka's earliest available offset is now `102`, the framework raises `DebeziumKafkaResumeGapError`.

It must not silently jump to `102`, because offset `101` may contain an unapplied change.

A retention gap requires a governed recovery path such as:

- authoritative full rebuild / new bootstrap;
- source-native resnapshot with a new CDC handoff fence;
- approved manual recovery when another durable copy proves the missing event set.

Do not edit the framework checkpoint merely to make the error disappear.

### Kafka repartitioning

A partition set change after a framework checkpoint is committed is rejected by default. `allow_new_partitions=True` makes the addition explicit, but a production provider implementation still needs to prove the source/topic semantics of that change.

---

## 2. Delta Change Data Feed retention-safe resume

### Version meaning

The framework's Delta CDF checkpoint means an entire Delta commit version is durably applied downstream.

If version `100` is committed, the next required version is `101`.

The provider/runtime must expose retention evidence before the bounded CDF read:

```text
earliest_available_version
latest_available_version
```

Then use:

```python
from fabric_data_framework.adapters.cdc import plan_delta_cdf_resume

plan = plan_delta_cdf_resume(
    table_reference="lakehouse.customer",
    lower_committed_version=100,
    earliest_available_version=101,
    latest_available_version=120,
    requested_upper_version=110,
)
```

Result:

```text
start_version = 101
upper_version = 110
lower_checkpoint = version 100
upper_checkpoint = version 110
```

### Retention gap rule

```text
next_required = lower_committed_version + 1

if earliest_available_version > next_required:
    FAIL CLOSED
```

For example:

```text
lower committed = 100
earliest available = 102
```

Version 101 is no longer covered by provider CDF retention, so `DeltaCDFRetentionGapError` is raised.

The framework must not silently change `start_version` to 102.

### Empty CDF versions are not automatically gaps

A Delta commit/version may be available even if the table produces no row changes for the requested semantic scope. Therefore retention safety is determined by provider **version availability evidence**, not simply by whether a CDF query returned rows.

The provider implementation must freeze the requested upper version and prove the read is complete through that boundary before the framework advances its checkpoint.

### Correct execution order

```text
1. Read framework lower CDF checkpoint.
2. Discover provider earliest/latest available versions.
3. plan_delta_cdf_resume(...).
4. Freeze plan.upper_version.
5. Read CDF start_version..upper_version.
6. Normalize with complete_through_upper=True only when the provider read is complete.
7. Apply target mutation through target-operation idempotency.
8. Reconcile/data-quality checks.
9. Commit framework upper checkpoint.
```

A real Fabric Lakehouse adapter still needs retained evidence for how earliest/latest CDF availability is discovered and how retention-gap recovery behaves in the approved workspace.

---

## 3. Target-native ambiguous-commit probe

The durable target-operation journal prevents blind retry, but a provider adapter must still answer the physical question:

> Did the previously submitted target mutation commit?

Possible native evidence includes:

- Fabric Warehouse statement/transaction history;
- an atomic audit marker written with the business mutation;
- a Delta commit/version or transaction marker;
- a Spark/native job result linked to an atomic target-side marker;
- another provider API that can prove the exact operation key committed or did not commit.

### Standard probe contract

Implement `TargetCommitProbe`:

```python
from fabric_data_framework.contracts.recovery import UnknownOutcomeResolution
from fabric_data_framework.recovery import (
    TargetCommitProbeEvidence,
)

class WarehouseCommitProbe:
    def probe(self, request):
        native = lookup_statement_or_marker(request.operation_key)

        if native.proves_committed:
            return TargetCommitProbeEvidence(
                provider="fabric_warehouse",
                resolution=UnknownOutcomeResolution.COMMITTED,
                native_operation_id=native.statement_id,
                evidence_reference=native.audit_reference,
            )

        if native.proves_not_committed:
            return TargetCommitProbeEvidence(
                provider="fabric_warehouse",
                resolution=UnknownOutcomeResolution.NOT_COMMITTED,
                evidence_reference=native.audit_reference,
            )

        return TargetCommitProbeEvidence(
            provider="fabric_warehouse",
            resolution=UnknownOutcomeResolution.UNRESOLVED,
            detail="provider evidence cannot prove outcome",
        )
```

Then reconcile durably:

```python
from fabric_data_framework.recovery import probe_and_reconcile_target_operation

result = probe_and_reconcile_target_operation(
    engine,
    operation_key=operation_key,
    dataset_run_id=retry_dataset_run_id,
    attempt=retry_attempt,
    probe=WarehouseCommitProbe(...),
)
```

### Resolution semantics

| Probe result | Durable operation state | May mutate target again? |
|---|---|---:|
| `COMMITTED` | `SUCCEEDED` | No; later claims skip |
| `NOT_COMMITTED` | `NOT_COMMITTED` | Yes, but only after the next CAS claim returns `EXECUTE` |
| `UNRESOLVED` | `UNKNOWN` | No |
| probe raises/transport fails | `UNKNOWN` with error detail | No |

Provider lookup failures are deliberately converted to durable `UNRESOLVED`. A flaky history API must never accidentally become permission to re-execute an SCD2, APPEND or MERGE mutation.

### Evidence requirement

A resolved `COMMITTED` or `NOT_COMMITTED` probe must include a native operation ID or evidence reference. `UNRESOLVED` may lack a proof reference because its meaning is specifically that the provider cannot prove an outcome.

---

## 4. Unified downstream-failure model

The three contracts work together:

```text
framework source checkpoint
        |
        v
provider resume plan
        |
        v
bounded source read
        |
        v
target-operation claim
        |
        +-- SKIP_SUCCEEDED -----------------------+
        |                                         |
        +-- RECONCILE_REQUIRED -> native probe ---+
        |                    |                    |
        |                    +-> COMMITTED -------+
        |                    +-> NOT_COMMITTED -> future EXECUTE
        |                    +-> UNRESOLVED -> STOP
        |
        +-- EXECUTE -> target mutation
                         |
                         v
                   reconcile / DQ
                         |
                         v
                framework source checkpoint
                         |
                         v
               optional provider cursor commit
```

The framework's goal is not to pretend every external system supports distributed exactly-once transactions. The goal is to make every uncertain boundary explicit and fail closed whenever the available evidence cannot prove safe progress.

---

## 5. Provider implementation checklist

Before certifying a real provider/profile, retain evidence for all applicable items:

- how earliest/latest source positions are discovered;
- how a bounded upper position/version is frozen;
- how partitions/shards are enumerated and changes detected;
- how the runtime seeks/rewinds to framework-derived progress;
- whether the provider cursor represents last-consumed or next-to-consume;
- when provider cursor commit happens relative to framework downstream checkpoint commit;
- how retention gaps are detected;
- what governed action handles an unrecoverable retention gap;
- how target-native operation IDs/markers are captured;
- how `COMMITTED`, `NOT_COMMITTED`, and `UNRESOLVED` are proven;
- how authentication/network/API failures are represented;
- how framework run IDs correlate to provider-native evidence.

Do not label a provider `FABRIC PROVEN` or production certified from fake-transport/reference tests alone.

---

## 6. What CI proves vs what it does not

Deterministic CI can prove:

- external Kafka group offsets never override framework checkpoints;
- ahead/behind/missing Kafka cursors produce deterministic seek plans;
- provider group commits are calculated as next-to-consume offsets and are explicitly deferred until downstream success;
- Kafka retention gaps fail closed;
- Delta CDF retention gaps fail closed;
- bounded Delta CDF resume versions/checkpoints are deterministic;
- target probe outcomes persist through the durable operation journal;
- provider probe exceptions remain `UNKNOWN` and block blind retry.

CI does **not** prove:

- a live Kafka broker accepts the planned seek/commit calls;
- rebalance behavior and group ownership are correct in the chosen Kafka client;
- Fabric Lakehouse exposes the required CDF availability evidence under the chosen runtime;
- Fabric Warehouse/Delta/Spark provides a native target marker sufficient to resolve every ambiguous commit;
- credentials, network policy, throttling, capacity or retention settings in an enterprise workspace.

Those remain real-provider integration evidence gates for `0.4.0`.
