-- The stored report with the given source fingerprint.
-- Binding: :fingerprint (SHA-256 of the source HTML bytes).
SELECT report_id, generated_at, ingestion_sequence FROM reports
WHERE source_fingerprint = :fingerprint
