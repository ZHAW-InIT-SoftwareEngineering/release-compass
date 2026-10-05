"""Configuration for deterministic Performance Gate acceptance."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class MetricAcceptanceThreshold(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator: Literal[">="]
    score: float = Field(ge=0, le=1)


class PerformanceMetricThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_time: MetricAcceptanceThreshold
    throughput: MetricAcceptanceThreshold
    request_outcomes: MetricAcceptanceThreshold
    transaction_nfr_status: MetricAcceptanceThreshold
    cpu: MetricAcceptanceThreshold
    memory: MetricAcceptanceThreshold


class PerformanceGateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: PerformanceMetricThresholds


def load_performance_gate_config(path: Path) -> PerformanceGateConfig:
    with path.open(encoding="utf-8") as config_file:
        config_data = yaml.safe_load(config_file)

    return PerformanceGateConfig.model_validate(config_data)
