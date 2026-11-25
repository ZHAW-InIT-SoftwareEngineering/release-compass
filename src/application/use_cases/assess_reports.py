"""Assess stored reports under one versioned configuration (ADR 0012, ADR 0013)."""

import json
from dataclasses import asdict
from hashlib import sha256
from uuid import UUID

from src.application.ports.outbound.report_repository import ReportRepository
from src.domain.assessment import GateDefinition
from src.domain.scoring import Measure, score_gate


class AssessmentService:
    """Score each new report's gates, then let the store derive the rest.

    Gate outcomes come from Python scoring; the previous report, the report
    outcome and the baselines come from the store's rules.
    """

    def __init__(self, repository: ReportRepository, gates: list[GateDefinition]):
        self.repository = repository
        self.gates = {gate.gate_type: gate for gate in gates}
        if not gates or len(self.gates) != len(gates):
            raise ValueError("Gate definitions must be nonempty and uniquely named")
        self.configuration = {
            name: {
                "policy_version": gate.policy_version,
                "targets": {
                    metric: asdict(target) for metric, target in gate.targets.items()
                },
            }
            for name, gate in self.gates.items()
        }
        encoded = json.dumps(self.configuration, sort_keys=True, separators=(",", ":"))
        # A changed configuration is a new version; older results stay as they are.
        self.version = sha256(encoded.encode()).hexdigest()

    def prepare(self) -> None:
        """Assess every report not yet assessed in this version, oldest first."""
        self.repository.open_assessment(self.version)
        for report_id in self.repository.unassessed_reports():
            present = self.repository.gate_types(report_id)
            for gate in self.gates.values():
                if gate.gate_type in present:
                    acceptance = score_gate(
                        gate.targets, self._measure(report_id, gate)
                    )
                    self.repository.add_gate_assessment(
                        report_id,
                        gate.gate_type,
                        acceptance,
                        gate.targets,
                        gate.policy_version,
                    )
            self.repository.apply_rules(report_id, self.gates.keys())
        self.repository.save()

    def _measure(self, report_id: UUID, gate: GateDefinition) -> Measure:
        def measure(metric: str, statistic: str):
            return self.repository.measurements(
                report_id, gate.gate_type, metric, statistic
            )

        return measure
