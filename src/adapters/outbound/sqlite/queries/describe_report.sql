-- Q1/Q2: a report's facts and, in the open assessment version, its outcome and
-- predecessor (NULL when not assessed). No row for an unknown report.
-- Source paths and gate types: source_paths.sql, gate_types.sql.
-- Bindings: :report_id, :version (assessment version).
SELECT r.generated_at, r.ingestion_sequence,
       a.outcome, a.is_root, a.previous_report_id
FROM reports r
LEFT JOIN report_assessments a
    ON a.version = :version AND a.report_id = r.report_id
WHERE r.report_id = :report_id
