"""Configuration of a quality gate's metric targets (ADR 0012).

Every key is required; a ``null`` bound leaves that side unbounded. Which
metrics and aggregations a gate supports is checked against the gate's
domain rules when the targets are wired.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TargetConfig(_Strict):
    aggregation: str
    unit: str
    min: float | None
    max: float | None


class MetricConfig(_Strict):
    target: TargetConfig
    score: float = Field(ge=0, le=1)


class GateTargetsConfig(_Strict):
    metrics: dict[str, MetricConfig]


def load_gate_targets_config(path: Path) -> GateTargetsConfig:
    with path.open(encoding="utf-8") as config_file:
        config_data = yaml.safe_load(config_file)
    return GateTargetsConfig.model_validate(config_data)
