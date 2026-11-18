-- Q6: the per-source results a metric assessment is based on, with the
-- measured value of the target's statistic.
-- Bindings: :report_id, :gate_type, :name (target name), :metric,
-- :statistic (target aggregation), :version (assessment version).
SELECT s.source, x.value, s.meets_target, s.excluded, s.reason
FROM source_assessments s
LEFT JOIN measurements x ON x.report_id = s.report_id
    AND x.gate_type = s.gate_type AND x.metric = :metric
    AND x.statistic = :statistic AND x.source = s.source
WHERE s.version = :version AND s.report_id = :report_id
    AND s.gate_type = :gate_type AND s.name = :name
ORDER BY s.source
