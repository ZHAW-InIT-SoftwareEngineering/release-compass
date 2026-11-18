-- Latest stored report time and highest ingestion sequence (ADR 0008).
-- Returns one row of NULLs when no report is stored.
SELECT MAX(generated_at), MAX(ingestion_sequence) FROM reports
