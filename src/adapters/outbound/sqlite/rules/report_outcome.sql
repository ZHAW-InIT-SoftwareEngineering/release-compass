-- The outcomes of a report's gates in the open assessment version, 'unknown'
-- for an unassessed gate (ADR 0005). Combined into the report outcome with
-- missing required gates in Python (combine_outcomes).
-- Bindings: :report_id, :version (assessment version).
SELECT g.gate_type, COALESCE(a.outcome, 'unknown')
FROM gates g
LEFT JOIN gate_assessments a ON a.version = :version
    AND a.report_id = g.report_id AND a.gate_type = g.gate_type
WHERE g.report_id = :report_id
