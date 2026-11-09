from typing import Protocol

from src.domain.targets import MetricTarget


class TargetSource(Protocol):
    """Supplies one gate's targets, e.g. from configuration or a knowledge base."""

    def targets(self) -> dict[str, MetricTarget]: ...
