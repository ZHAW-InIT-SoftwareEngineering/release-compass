"""Read a gate's metric targets from its YAML configuration."""

from pathlib import Path

from src.configs.gates.targets import load_gate_targets_config
from src.domain.targets import MetricTarget, TargetRange


class YamlTargetSource:
    def __init__(self, path: Path):
        self.path = path

    def targets(self) -> dict[str, MetricTarget]:
        config = load_gate_targets_config(self.path)
        return {
            name: MetricTarget(
                name,
                metric.target.aggregation,
                metric.target.unit,
                TargetRange(metric.target.min, metric.target.max),
                metric.score,
            )
            for name, metric in config.metrics.items()
        }
