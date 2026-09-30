from dataclasses import dataclass


@dataclass
class Gate:
    run_id: str | None = None
    baseline_run_id: str | None = None
