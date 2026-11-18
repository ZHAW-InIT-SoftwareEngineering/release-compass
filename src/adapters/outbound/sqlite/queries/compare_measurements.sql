-- Q4/Q5: a statistic of a report against its baseline report, per source both
-- reports share. The difference is NULL when the units differ.
-- Bindings: :report_id, :baseline_report_id, :gate_type, :metric, :statistic.
SELECT c.source, c.unit, b.unit, c.value, b.value,
       CASE WHEN c.unit = b.unit THEN c.value - b.value END
FROM measurements c
JOIN measurements b
    ON b.report_id = :baseline_report_id AND b.gate_type = c.gate_type
    AND b.metric = c.metric AND b.statistic = c.statistic
    AND b.source = c.source
WHERE c.report_id = :report_id AND c.gate_type = :gate_type
    AND c.metric = :metric AND c.statistic = :statistic
ORDER BY c.source
