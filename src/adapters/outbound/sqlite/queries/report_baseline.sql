-- Q3: the report baseline in the open assessment version (ADR 0006).
-- Bindings: :report_id, :version (assessment version).
SELECT baseline_report_id FROM report_assessments
WHERE version = :version AND report_id = :report_id
