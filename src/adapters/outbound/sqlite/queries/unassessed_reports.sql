-- Reports without an outcome in the open assessment version, oldest first
-- (generated-at, then ingestion sequence; ADR 0006).
-- Binding: :version (assessment version).
SELECT report_id FROM reports r
WHERE NOT EXISTS (
    SELECT 1 FROM report_assessments a
    WHERE a.version = :version AND a.report_id = r.report_id)
ORDER BY generated_at, ingestion_sequence
