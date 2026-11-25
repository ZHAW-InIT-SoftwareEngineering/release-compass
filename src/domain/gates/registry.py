"""Supported gate types and the measurements each stores (ADR 0012).

Every store keeps exactly the measurements scoring can request, so adapters
read them from here instead of knowing individual gates.
"""

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from src.domain.gates.gate import Gate
from src.domain.gates.performance import measurements as performance
from src.domain.gates.performance.performance_gate import PerformanceGate
from src.domain.scoring import Measure, Measurement


@dataclass(frozen=True)
class GateKind:
    name: str
    measure: Callable[[Any], Measure]
    # Metric -> statistics a target may name.
    supported: Mapping[str, tuple[str, ...]]


GATE_KINDS: dict[type[Gate], GateKind] = {
    PerformanceGate: GateKind(
        performance.GATE_TYPE, performance.performance_measure, performance.SUPPORTED
    ),
}


def gate_kind(gate: Gate) -> GateKind:
    try:
        return GATE_KINDS[type(gate)]
    except KeyError:
        raise ValueError(f"Unsupported gate type {type(gate).__name__}") from None


def gate_measurements(gate: Gate) -> Iterator[tuple[str, str, Measurement]]:
    """Yield (metric, statistic, measurement) for every supported statistic."""
    kind = gate_kind(gate)
    measure = kind.measure(gate)
    for metric, statistics in kind.supported.items():
        for statistic in statistics:
            for measurement in measure(metric, statistic):
                yield metric, statistic, measurement
