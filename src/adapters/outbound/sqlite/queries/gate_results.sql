-- Q6: each gate's outcome in the open assessment version (NULL when not
-- assessed). Metrics: metric_results.sql.
-- Bindings: :report_id, :version (assessment version).
SELECT g.gate_type, a.outcome
FROM gates g
LEFT JOIN gate_assessments a ON a.version = :version
    AND a.report_id = g.report_id AND a.gate_type = g.gate_type
WHERE g.report_id = :report_id
ORDER BY g.gate_type
