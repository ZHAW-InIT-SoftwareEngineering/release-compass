"""Immutable assessment records with shallow history and baseline references."""

from dataclasses import dataclass, fields, is_dataclass
from math import isfinite
from typing import Any
from uuid import UUID

from src.domain.assessment import GateAcceptance, Outcome


def json_value(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: json_value(getattr(value, item.name)) for item in fields(value)
        }
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, float) and not isfinite(value):
        return {"invalid_numeric": str(value)}
    return value


def tool_evidence(pack: EvidencePack) -> dict[str, Any]:
    """Keep full stored series addressable without repeating them in model context."""
    series_fields = {
        "timeseries",
        "linear_trend",
        "linear_trend_timeseries",
        "per_minute",
        "buckets",
        "violation_windows",
        "counted_violation_windows",
    }

    def compact(value: Any, path: list[str]) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    {
                        "evidence_reference": {
                            "evidence_pack_id": str(pack.evidence_pack_id),
                            "path": [*path, key],
                        },
                        "item_count": len(item),
                        **({"preview": item[:8]} if key == "violation_periods" else {}),
                    }
                    if (key in series_fields and isinstance(item, (dict, list)))
                    or (
                        key == "violation_periods"
                        and isinstance(item, list)
                        and len(item) > 8
                    )
                    else compact(item, [*path, key])
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                compact(item, [*path, str(index)]) for index, item in enumerate(value)
            ]
        return value

    return compact(json_value(pack), [])


@dataclass(frozen=True)
class GateEvidence:
    gate_type: str
    current_report_id: UUID
    baseline_report_id: UUID | None
    baseline_evidence_pack_id: UUID | None
    acceptance: GateAcceptance
    baseline_acceptance: GateAcceptance | None
    comparisons: dict[str, Any]


@dataclass(frozen=True)
class EvidencePack:
    evidence_pack_id: UUID
    report_id: UUID
    assessment_version: str
    previous_report_id: UUID | None
    previous_evidence_pack_id: UUID | None
    is_root: bool
    baseline_report_id: UUID | None
    baseline_evidence_pack_id: UUID | None
    outcome: Outcome
    gates: dict[str, GateEvidence]
    snapshots: dict[str, dict[str, Any]]
    configuration: dict[str, Any]
