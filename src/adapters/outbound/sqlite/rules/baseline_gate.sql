-- Per gate of a report, the latest earlier report whose gate of the same type
-- passed in the open assessment version (ADR 0006).
-- Order: generated-at, then ingestion sequence.
-- Bindings: :report_id, :version (assessment version).
UPDATE gate_assessments AS g
SET baseline_report_id = (
    SELECT p.report_id
    FROM reports r
    JOIN reports p ON (p.generated_at, p.ingestion_sequence)
                      < (r.generated_at, r.ingestion_sequence)
    JOIN gate_assessments a ON a.version = g.version
        AND a.report_id = p.report_id AND a.gate_type = g.gate_type
    WHERE r.report_id = g.report_id AND a.outcome = 'pass'
    ORDER BY p.generated_at DESC, p.ingestion_sequence DESC
    LIMIT 1)
WHERE g.version = :version AND g.report_id = :report_id
