"""Gate-agnostic targets, modelled after the ontology's ``ai2core:Target``."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TargetRange:
    """Inclusive bounds; ``None`` leaves that side unbounded."""

    min: float | None
    max: float | None

    def __post_init__(self):
        if self.min is None and self.max is None:
            raise ValueError("A target range needs at least one bound")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("Target min must not exceed max")

    def contains(self, value: float) -> bool:
        return (self.min is None or value >= self.min) and (
            self.max is None or value <= self.max
        )


@dataclass(frozen=True)
class MetricTarget:
    metric: str
    aggregation: str
    unit: str
    range: TargetRange
    min_score: float

    def __post_init__(self):
        if not 0 <= self.min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")


def check_targets(
    targets: Mapping[str, MetricTarget],
    supported: Mapping[str, Sequence[str]],
) -> None:
    """Require one target per supported metric, using a supported aggregation."""
    missing = supported.keys() - targets.keys()
    unexpected = targets.keys() - supported.keys()
    if missing or unexpected:
        raise ValueError(
            f"Targets must cover exactly {sorted(supported)}; "
            f"missing {sorted(missing)}, unexpected {sorted(unexpected)}"
        )
    for name, target in targets.items():
        if target.metric != name:
            raise ValueError(f"Target {name!r} names metric {target.metric!r}")
        if target.aggregation not in supported[name]:
            raise ValueError(
                f"{name} cannot aggregate on {target.aggregation!r}; "
                f"use one of {', '.join(supported[name])}"
            )
