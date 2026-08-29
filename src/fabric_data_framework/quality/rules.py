"""Reusable validation and row-quarantine primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, ConfigDict

from ..bronze import BronzeRecord


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


@dataclass(frozen=True)
class RowRule:
    code: str
    message: str
    predicate: Callable[[dict], bool]


class QuarantinedRecord(FrozenModel):
    record: BronzeRecord
    reason_codes: tuple[str, ...]
    reason_messages: tuple[str, ...]


class ValidationOutcome(FrozenModel):
    accepted: tuple[BronzeRecord, ...]
    quarantined: tuple[QuarantinedRecord, ...]


def validate_records(
    records: tuple[BronzeRecord, ...],
    rules: tuple[RowRule, ...],
) -> ValidationOutcome:
    accepted: list[BronzeRecord] = []
    quarantined: list[QuarantinedRecord] = []
    for record in records:
        failures = [rule for rule in rules if not rule.predicate(record.data)]
        if failures:
            quarantined.append(
                QuarantinedRecord(
                    record=record,
                    reason_codes=tuple(rule.code for rule in failures),
                    reason_messages=tuple(rule.message for rule in failures),
                )
            )
        else:
            accepted.append(record)
    return ValidationOutcome(accepted=tuple(accepted), quarantined=tuple(quarantined))
