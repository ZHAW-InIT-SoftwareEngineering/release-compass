-- Q6: a gate's metric assessments with their targets and scores.
-- Sources: source_results.sql.
-- Bindings: :report_id, :gate_type, :version (assessment version).
SELECT m.name, t.metric, t.aggregation, t.unit, t.min, t.max,
       t.min_score, m.score, m.outcome, m.reason, m.policy_version
FROM metric_assessments m
JOIN targets t ON t.version = m.version AND t.name = m.name
WHERE m.version = :version AND m.report_id = :report_id
    AND m.gate_type = :gate_type
ORDER BY t.metric
