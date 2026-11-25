"""Compare one metric statistic of two gate runs, source by source (ADR 0015)."""

from dataclasses import dataclass

from src.domain.scoring import Measurement


@dataclass(frozen=True)
class MeasurementChange:
    """Q5: one source measured in both reports; delta only with equal units."""

    source: str
    unit: str | None
    baseline_unit: str | None
    current: float | None
    baseline: float | None
    delta: float | None


def compare_measurements(
    current: list[Measurement], baseline: list[Measurement]
) -> list[MeasurementChange]:
    """Sources present in both runs, ordered by source.

    The delta is current minus baseline; it is None when a value is missing or
    the units differ (ADR 0003).
    """
    baseline_by_source = {measurement.source: measurement for measurement in baseline}
    changes = []
    for measurement in sorted(current, key=lambda item: item.source):
        previous = baseline_by_source.get(measurement.source)
        if previous is None:
            continue
        current_value, baseline_value = measurement.value, previous.value
        delta = None
        if (
            measurement.unit is not None
            and measurement.unit == previous.unit
            and current_value is not None
            and baseline_value is not None
        ):
            delta = current_value - baseline_value
        changes.append(
            MeasurementChange(
                source=measurement.source,
                unit=measurement.unit,
                baseline_unit=previous.unit,
                current=current_value,
                baseline=baseline_value,
                delta=delta,
            )
        )
    return changes
