-- A report's source paths, sorted.
-- Binding: :report_id.
SELECT path FROM source_paths WHERE report_id = :report_id ORDER BY path
