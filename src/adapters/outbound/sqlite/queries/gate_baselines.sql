-- Q3: per gate, the baseline gate's report and the scoring policy version in
-- the open assessment version (ADR 0006). One row per gate.
-- Bindings: :report_id, :version (assessment version).
SELECT g.gate_type, a.baseline_report_id,
       (SELECT MIN(m.policy_version) FROM metric_assessments m
        WHERE m.version = a.version AND m.report_id = g.report_id
            AND m.gate_type = g.gate_type)
FROM gates g
LEFT JOIN gate_assessments a ON a.version = :version
    AND a.report_id = g.report_id AND a.gate_type = g.gate_type
WHERE g.report_id = :report_id
ORDER BY g.gate_type
