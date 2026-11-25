-- The chronologically preceding report, including failed and unknown ones;
-- a report without one is the root (ADR 0006, ADR 0008).
-- Order: generated-at, then ingestion sequence.
-- Binding: :report_id.
SELECT p.report_id
FROM reports r
JOIN reports p ON (p.generated_at, p.ingestion_sequence)
                  < (r.generated_at, r.ingestion_sequence)
WHERE r.report_id = :report_id
ORDER BY p.generated_at DESC, p.ingestion_sequence DESC
LIMIT 1
