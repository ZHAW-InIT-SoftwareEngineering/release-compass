-- One statistic of one metric of a report's gate, one row per source.
-- Bindings: :report_id, :gate_type, :metric, :statistic.
SELECT source, field_path, value, unit, weight FROM measurements
WHERE report_id = :report_id AND gate_type = :gate_type
    AND metric = :metric AND statistic = :statistic
ORDER BY source
