-- The latest earlier report that passed in the open assessment version
-- (ADR 0006). Order: generated-at, then ingestion sequence.
-- Bindings: :report_id, :version (assessment version).
SELECT p.report_id
FROM reports r
JOIN reports p ON (p.generated_at, p.ingestion_sequence)
                  < (r.generated_at, r.ingestion_sequence)
JOIN report_assessments a
    ON a.version = :version AND a.report_id = p.report_id
WHERE r.report_id = :report_id AND a.outcome = 'pass'
ORDER BY p.generated_at DESC, p.ingestion_sequence DESC
LIMIT 1
