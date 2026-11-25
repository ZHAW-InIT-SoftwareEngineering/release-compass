"""Read a gate's metric targets from its YAML configuration."""

from pathlib import Path
from typing import Any

import yaml

from src.domain.targets import MetricTarget, TargetRange

DEFAULT_SECTION = "metrics"
_TARGET_KEYS = ("aggregation", "unit", "min", "max")


class YamlTargetSource:
    def __init__(self, path: Path, section: str = DEFAULT_SECTION):
        self.path = path
        self.section = section

    def targets(self) -> dict[str, MetricTarget]:
        raw = yaml.safe_load(Path(self.path).read_text(encoding="utf-8")) or {}
        metrics = raw.get(self.section)
        if not isinstance(metrics, dict) or not metrics:
            raise ValueError(f"{self.path}: section '{self.section}' is missing or empty")
        return {
            name: self._metric_target(name, metric) for name, metric in metrics.items()
        }

    def _metric_target(self, name: str, metric: Any) -> MetricTarget:
        where = f"{self.path}: {self.section}.{name}"
        if not isinstance(metric, dict) or "target" not in metric or "score" not in metric:
            raise ValueError(f"{where} needs 'target' and 'score'")
        target, score = metric["target"], metric["score"]
        missing = [key for key in _TARGET_KEYS if key not in target]
        if missing:
            raise ValueError(f"{where}.target is missing {missing}")
        if not 0 <= score <= 1:
            raise ValueError(f"{where}.score must be between 0 and 1, got {score}")
        return MetricTarget(
            name,
            target["aggregation"],
            target["unit"],
            TargetRange(target["min"], target["max"]),
            score,
        )
