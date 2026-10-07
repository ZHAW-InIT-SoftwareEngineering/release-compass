"""Prepare versioned assessments and serve their evidence to clients."""

import json
from dataclasses import dataclass, field
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from src.application.ports.outbound.report_history import ReportHistory
from src.application.use_cases.compare_gate import ReportNotFoundError
from src.configs.gates.performance.performance_gate import PerformanceGateConfig
from src.domain.assessment import (
    POLICY_VERSION,
    GateAcceptance,
    GateDefinition,
    Outcome,
    assess_performance,
    combine_outcomes,
    compare_acceptance_scores,
)
from src.domain.deltas.performance_comparison import compare_performance_values
from src.domain.evidence import EvidencePack, GateEvidence, json_value
from src.domain.gates.gate import Gate
from src.domain.gates.performance.performance_gate import PerformanceGate
from src.domain.history import latest_passing, report_order
from src.domain.report import Report


class EvidenceUnavailableError(LookupError):
    """A report exists but has not been assessed in this session's version."""


@dataclass
class _PreparationState:
    previous_reports: list[Report] = field(default_factory=list)
    packs: dict[UUID, EvidencePack] = field(default_factory=dict)


class AssessmentService:
    def __init__(
        self,
        repository: ReportHistory,
        config: PerformanceGateConfig,
        gate_definitions: list[GateDefinition] | None = None,
    ):
        self.repository = repository
        self.thresholds = {
            name: value.score for name, value in vars(config.metrics).items()
        }

        def performance_assessor(gate: Gate) -> GateAcceptance:
            if not isinstance(gate, PerformanceGate):
                raise TypeError("Expected PerformanceGate")
            return assess_performance(gate, self.thresholds)

        def performance_comparison(current: Gate, baseline: Gate | None) -> dict:
            if not isinstance(current, PerformanceGate) or (
                baseline is not None and not isinstance(baseline, PerformanceGate)
            ):
                raise TypeError("Expected PerformanceGate")
            return compare_performance_values(current, baseline)

        definitions = (
            gate_definitions
            if gate_definitions is not None
            else [
                GateDefinition(
                    PerformanceGate,
                    performance_assessor,
                    performance_comparison,
                    POLICY_VERSION,
                ),
            ]
        )
        self.definitions = {item.gate_type.__name__: item for item in definitions}
        if not definitions or len(self.definitions) != len(definitions):
            raise ValueError("Gate definitions must be nonempty and uniquely named")
        self.configuration = {
            "performance": config.model_dump(),
            "policy_version": POLICY_VERSION,
            "required_gates": sorted(self.definitions),
            "gate_policy_versions": {
                name: item.policy_version for name, item in self.definitions.items()
            },
        }
        encoded = json.dumps(self.configuration, sort_keys=True, separators=(",", ":"))
        self.version = sha256(encoded.encode()).hexdigest()

    def prepare(self) -> None:
        reports = sorted(self.repository.list_reports(), key=report_order)
        state = _PreparationState()
        for report in reports:
            self._prepare_report(report, state)

    def _prepare_report(self, report: Report, state: _PreparationState) -> None:
        stored = self.repository.get_evidence(report.report_id, self.version)
        if stored is not None:
            state.packs[report.report_id] = stored
            state.previous_reports.append(report)
            return

        report_baseline = latest_passing(state.previous_reports, state.packs)
        snapshots = self._current_snapshots(report, report_baseline, state)
        gates = self._assess_report_gates(report, snapshots, state)
        outcome = combine_outcomes(
            [item.acceptance.outcome for item in gates.values()]
        )
        snapshots[str(report.report_id)]["acceptance"] = {
            "outcome": outcome,
            "gates": {
                name: json_value(item.acceptance) for name, item in gates.items()
            },
        }
        pack = self._build_evidence_pack(
            report, report_baseline, outcome, gates, snapshots, state
        )
        self.repository.save_evidence(pack)
        state.packs[report.report_id] = pack
        state.previous_reports.append(report)

    def _current_snapshots(
        self,
        report: Report,
        report_baseline: Report | None,
        state: _PreparationState,
    ) -> dict[str, dict]:
        current_snapshot = {"report": json_value(report)}
        current_snapshot["report"]["gates"] = [
            {"gate_type": type(gate).__name__, **json_value(gate)}
            for gate in report.gates
        ]
        snapshots = {str(report.report_id): current_snapshot}
        if report_baseline:
            snapshots[str(report_baseline.report_id)] = state.packs[
                report_baseline.report_id
            ].snapshots[str(report_baseline.report_id)]
        return snapshots

    def _assess_report_gates(
        self,
        report: Report,
        snapshots: dict[str, dict],
        state: _PreparationState,
    ) -> dict[str, GateEvidence]:
        grouped: dict[str, list[Gate]] = {}
        for gate in report.gates:
            grouped.setdefault(type(gate).__name__, []).append(gate)
        return {
            name: self._assess_gate(
                name, grouped.get(name, []), report, snapshots, state
            )
            for name in sorted(grouped.keys() | self.definitions.keys())
        }

    def _assess_gate(
        self,
        name: str,
        gates: list[Gate],
        report: Report,
        snapshots: dict[str, dict],
        state: _PreparationState,
    ) -> GateEvidence:
        definition = self.definitions.get(name)
        if (
            definition is None
            or len(gates) != 1
            or type(gates[0]) is not definition.gate_type
        ):
            acceptance = GateAcceptance(
                "unknown", reason="Missing, duplicate, or unsupported required gate"
            )
            baseline = None
            comparisons = {}
        else:
            acceptance = definition.assess(gates[0])
            baseline = latest_passing(state.previous_reports, state.packs, name)
            baseline_gate = self._baseline_gate(baseline, definition.gate_type)
            comparisons = definition.compare(gates[0], baseline_gate)

        baseline_pack = state.packs[baseline.report_id] if baseline else None
        baseline_acceptance = (
            baseline_pack.gates[name].acceptance if baseline_pack else None
        )
        comparisons["acceptance_scores"] = compare_acceptance_scores(
            acceptance, baseline_acceptance
        )
        if baseline_pack and baseline:
            snapshots[str(baseline.report_id)] = baseline_pack.snapshots[
                str(baseline.report_id)
            ]
        return GateEvidence(
            name,
            report.report_id,
            baseline.report_id if baseline else None,
            baseline_pack.evidence_pack_id if baseline_pack else None,
            acceptance,
            baseline_acceptance,
            comparisons,
        )

    @staticmethod
    def _baseline_gate(baseline: Report | None, gate_type: type[Gate]) -> Gate | None:
        if baseline is None:
            return None
        return next(
            (gate for gate in baseline.gates if type(gate) is gate_type), None
        )

    def _build_evidence_pack(
        self,
        report: Report,
        report_baseline: Report | None,
        outcome: Outcome,
        gates: dict[str, GateEvidence],
        snapshots: dict[str, dict],
        state: _PreparationState,
    ) -> EvidencePack:
        predecessor = (
            state.previous_reports[-1] if state.previous_reports else None
        )
        predecessor_pack = (
            state.packs[predecessor.report_id] if predecessor else None
        )
        report_baseline_pack = (
            state.packs[report_baseline.report_id] if report_baseline else None
        )
        return EvidencePack(
            uuid5(NAMESPACE_URL, f"release-compass:{report.report_id}:{self.version}"),
            report.report_id,
            self.version,
            predecessor.report_id if predecessor else None,
            predecessor_pack.evidence_pack_id if predecessor_pack else None,
            predecessor is None,
            report_baseline.report_id if report_baseline else None,
            report_baseline_pack.evidence_pack_id if report_baseline_pack else None,
            outcome,
            gates,
            snapshots,
            self.configuration,
        )

    def get_evidence(self, report_id: UUID) -> EvidencePack:
        if self.repository.get_by_id(report_id) is None:
            raise ReportNotFoundError(f"Report {report_id} was not found")
        evidence = self.repository.get_evidence(report_id, self.version)
        if evidence is None:
            raise EvidenceUnavailableError(
                f"Report {report_id} has no prepared evidence for assessment version {self.version}",
            )
        return evidence

    def get_previous_report(self, report_id: UUID) -> dict:
        current = self.get_evidence(report_id)
        if current.previous_report_id is None:
            return {
                "report_id": str(report_id),
                "history_end": True,
                "previous_report": None,
            }
        return {
            "report_id": str(report_id),
            "history_end": False,
            "previous_report": json_value(
                self.get_evidence(current.previous_report_id)
            ),
        }
