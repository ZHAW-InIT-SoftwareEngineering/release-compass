-- The gate types a report contains, sorted.
-- Binding: :report_id.
SELECT gate_type FROM gates WHERE report_id = :report_id ORDER BY gate_type
